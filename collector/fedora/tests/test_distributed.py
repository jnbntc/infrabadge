"""Linux ARM thermal and bounded delivery fixtures; no physical sensors/network."""

import contextlib
import ssl

import pytest
from infrabadge_collector import transport
from infrabadge_collector.acquire import cpu_temperature


@pytest.mark.parametrize(
    "driver,temperature,expected",
    [("cpu_thermal", "42123", 42.123), ("gpu", "42123", None), ("cpu_thermal", "999999", None)],
)
def test_explicit_arm_cpu_thermal_only(tmp_path, driver, temperature, expected):
    chip = tmp_path / "hwmon0"
    chip.mkdir()
    (chip / "name").write_text(driver)
    (chip / "temp1_input").write_text(temperature)
    result = cpu_temperature(tmp_path)
    assert (result["celsius"] if result else None) == expected


@pytest.mark.parametrize(
    "failure,attempts", [("reset", 2), ("certificate", 1), ("deadline", 1), ("http", 1)]
)
def test_opt_in_second_attempt_has_same_bytes_one_deadline_and_no_tls_retry(
    tmp_path, monkeypatch, failure, attempts
):
    token = tmp_path / "token"
    token.write_text("x" * 40)
    token.chmod(0o600)
    sent = []
    deadlines = []

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method, path, body, headers):
            sent.append(body)
            if len(sent) == 1:
                if failure == "reset":
                    raise ConnectionResetError("private")
                if failure == "certificate":
                    raise ssl.SSLCertVerificationError("private")
                if failure == "deadline":
                    raise TimeoutError("private")

        def getresponse(self):
            class Response:
                status = 401 if failure == "http" else 202

                def read(self, size):
                    return b'{"accepted":true}'

            return Response()

        def close(self):
            pass

    @contextlib.contextmanager
    def deadline(seconds):
        deadlines.append(seconds)
        yield

    monkeypatch.setattr(transport.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(transport, "deadline", deadline)
    monkeypatch.setattr(
        transport.ssl,
        "create_default_context",
        lambda **kw: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
    )
    config = dict(
        gateway_url="https://central.test:9443",
        node_id="synthetic",
        ca_file="unused",
        timeout_seconds=5,
        delivery_attempts=2,
    )
    if failure == "reset":
        transport.submit(config, token, {"node_id": "synthetic"})
    else:
        with pytest.raises((OSError, ValueError)):
            transport.submit(config, token, {"node_id": "synthetic"})
    assert len(sent) == attempts and len(set(sent)) == 1 and deadlines == [5]
