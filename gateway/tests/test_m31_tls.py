"""Actual loopback TLS against both candidate entrances; synthetic metrics only."""

import asyncio
import datetime as dt
import signal
import socket
import ssl

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from infrabadge_gateway.app import create_app
from infrabadge_gateway.lan_edge import LanEntrance
from infrabadge_gateway.lan_server import serve, tls_config, validate_tls
from infrabadge_gateway.lan_telemetry import Telemetry
from m31_fixtures import COLLECTOR, DEVICE, NOW, configuration, policy, sample


def certificates(folder, kind="valid"):
    now = dt.datetime.now(dt.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic M3.1 CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=2))
        .not_valid_after(now + dt.timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False), True
        )
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    names = [
        x509.DNSName("localhost"),
        x509.DNSName(policy().hostname if kind != "wronghost" else "wrong.test"),
    ]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic M3.1 server")]))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=2))
        .not_valid_after(
            now - dt.timedelta(days=1) if kind == "expired" else now + dt.timedelta(days=3)
        )
        .add_extension(x509.SubjectAlternativeName(names), False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False
        )
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, False, False, False, False), True
        )
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .sign(ca_key, hashes.SHA256())
    )
    paths = tuple(folder / n for n in ("ca.pem", "server.pem", "server.key"))
    for path, data in zip(
        paths,
        (
            ca.public_bytes(serialization.Encoding.PEM),
            cert.public_bytes(serialization.Encoding.PEM),
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        ),
    ):
        path.write_bytes(data)
        path.chmod(0o600)
    return paths


@pytest.mark.parametrize("kind", ["valid", "expired", "wronghost"])
def test_startup_offline_tls_validation_checks_both_sans_dates_and_ca(tmp_path, kind):
    ca, cert, key = certificates(tmp_path, kind)
    if kind == "valid":
        validate_tls(cert, key, ca, policy().hostname)
    else:
        with pytest.raises(ssl.SSLCertVerificationError):
            validate_tls(cert, key, ca, policy().hostname)


def free_port():
    with socket.socket() as channel:
        channel.bind(("127.0.0.1", 0))
        return channel.getsockname()[1]


def certificate_error(error):
    pending, seen = [error], set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, ssl.SSLCertVerificationError):
            return True
        if isinstance(item, BaseException):
            pending.extend(
                v
                for v in (item.__cause__, item.__context__, *item.args)
                if isinstance(v, BaseException)
            )
    return False


def test_two_real_tls_entrances_share_data_reject_ca_and_clean_up(tmp_path):
    ca, cert, key = certificates(tmp_path)
    original = signal.getsignal(signal.SIGINT)
    context = ssl.create_default_context(cafile=str(ca))
    telemetry = Telemetry()
    configured = configuration()
    local = create_app(configured, clock=lambda: NOW, events=telemetry.emit)
    p = policy(device_burst=10)
    authorized = [True]
    lan = LanEntrance(local, configured, p, lambda: authorized[0], telemetry)
    ports = [free_port(), free_port()]
    assert ports[0] != ports[1]
    configs = [tls_config(app, port, cert, key) for app, port in zip((local, lan), ports)]
    for cfg in configs:
        cfg.host = "127.0.0.1"  # Fixtures NEVER bind the selected LAN or wildcard.
        assert cfg.ssl.minimum_version >= ssl.TLSVersion.TLSv1_2 and not cfg.proxy_headers

    async def scenario():
        task = asyncio.create_task(serve(configs))
        try:
            for _ in range(100):
                try:
                    reader, writer = await asyncio.open_connection(
                        "127.0.0.1", ports[1], ssl=context, server_hostname="localhost"
                    )
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    if task.done():
                        task.result()
                    await asyncio.sleep(0.02)
            else:
                raise AssertionError("Fixture server did not start")
            async with httpx.AsyncClient(verify=context, trust_env=False, timeout=3) as client:
                local_url = "https://localhost:" + str(ports[0])
                lan_url = "https://localhost:" + str(ports[1])
                accepted = await client.post(
                    local_url + "/api/v1/collectors/workstation/metrics",
                    json=sample(),
                    headers={"Authorization": "Bearer " + COLLECTOR},
                )
                assert accepted.status_code == 202
                headers = {"Authorization": "Bearer " + DEVICE, "Host": p.hostname + ":8443"}
                response = await client.get(
                    lan_url + "/api/v1/devices/badge/status", headers=headers
                )
                assert response.status_code == 200 and response.json()["simulated"] is False
                direct = await client.get(
                    local_url + "/api/v1/devices/badge/status",
                    headers={"Authorization": "Bearer " + DEVICE},
                )
                assert (
                    direct.content == response.content
                    and direct.headers["etag"] == response.headers["etag"]
                )
                cached = await client.get(
                    lan_url + "/api/v1/devices/badge/status",
                    headers=headers | {"If-None-Match": response.headers["etag"]},
                )
                assert cached.status_code == 304 and not cached.content
                assert (
                    await client.post(
                        lan_url + "/api/v1/collectors/workstation/metrics",
                        json=sample(),
                        headers=headers,
                    )
                ).status_code == 404
                authorized[0] = False
                assert (
                    await client.get(lan_url + "/api/v1/devices/badge/status", headers=headers)
                ).status_code == 503
                authorized[0] = True
                assert (
                    await client.get(lan_url + "/api/v1/devices/badge/status", headers=headers)
                ).status_code == 200
                async with httpx.AsyncClient(trust_env=False, timeout=3) as unknown_ca:
                    with pytest.raises(httpx.ConnectError) as error:
                        await unknown_ca.get(
                            lan_url + "/api/v1/devices/badge/status", headers=headers
                        )
                    assert certificate_error(error.value)  # Refused TCP is not a TLS PASS.
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        async with httpx.AsyncClient(verify=context, trust_env=False, timeout=1) as client:
            with pytest.raises(httpx.ConnectError):
                await client.get("https://localhost:" + str(ports[0]))

    asyncio.run(scenario())
    assert signal.getsignal(signal.SIGINT) == original
    assert telemetry.state["counts"]["collector_accepted"] == 1


def test_supervisor_does_not_leave_first_socket_when_second_bind_fails(tmp_path):
    ca, cert, key = certificates(tmp_path)
    first_port = free_port()
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        ports = [first_port, occupied.getsockname()[1]]
        configs = [tls_config(create_app(configuration()), p, cert, key) for p in ports]
        for cfg in configs:
            cfg.host = "127.0.0.1"
        with pytest.raises(OSError):
            asyncio.run(serve(configs))
    with socket.socket() as reusable:
        reusable.bind(("127.0.0.1", first_port))
