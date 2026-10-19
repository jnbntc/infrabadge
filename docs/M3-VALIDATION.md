# M3 validation — software and Fedora host evidence

Validated locally on 2026-10-19. This report contains allowlisted outcomes and
synthetic examples, not notebook inventory, private snapshots, credentials or USB
logs. M3 branch: `feat/m3-fedora-monitoring`, based on integrated main19a9a00.

## Executed checks

| Check | Result | Scope |
| --- | --- | --- |
| Collector + gateway + integration | **144 passed** | Deterministic fixtures, pytest root config, Python3.14 host venv |
| CPU/memory/load/uptime parsing and deltas | PASS | Guest accounting, decrease/hotplug/gap/warmup, MemAvailable/fallback, invalid/missing/read failures |
| Disk and hwmon | PASS | statvfs fixture, supported/absent/faulted/unreliable CPU channels; no runner sensor dependency |
| Authentication and strict ingress | PASS | Role/node isolation, malformed/duplicate/oversize/NaN, range/consistency, UTC, replay/out-of-order, rate spacing |
| Policy and cache | PASS | CPU confirmation/hysteresis, RAM/disk precedence/recovery, explicit temperature opt-in, UNKNOWN/stale/recovery, expiry before304 |
| Actual loopback TLS integration | PASS | Fixture acquisition through collector transport, CA/SAN/date checks, M2 contract/304; expired and wrong-host certs rejected |
| Package and staging | PASS | Byte-reproducible ZIP, isolated Python execution, temporary-home installation, no enable/overwrite, private config preparation |
| Full state filesystem | PASS | ENOSPC on lock creation or cache write still delivers available disk-alarm metrics; no private exception details logged |
| Static/format | PASS | Ruff0.14.2, hash-pinned in tools/m3/style.lock; M3/newly modified Python scope |
| Protocol references | PASS | Existing four M2 fixtures/schema unchanged; six new synthetic M3 wire fixtures |
| C/sanitizers/visuals | PASS | Existing core/HAL/panel/UI/timer/TLS adapter tests; ASan/UBSan; six M3 actual C decoder/render references; unchanged M2 pixels |
| NVS cache regression | PASS | Production store with fake NVS rejects version1 even with valid CRC, preserves REAL/SIM in version2 and rejects corruption |
| All seven ESP-IDF profiles | PASS | M0 display/sensors/sleep, M1 UI, M1.1 timer, normal M2 and autonomous M2; ESP32-S3/8MB, security options checked |
| systemd unit syntax | PASS | systemd-analyze verify, both user units; **not** a real service activation test |
| Rootless Quadlet generation | PASS | Isolated QUADLET_UNIT_DIRS, generator --user --dryrun; expected read-only/loopback unit generated, nothing installed/started |
| Real Fedora acquisition → ephemeral HTTPS | PASS | Actual host CPU/RAM/disk/uptime; compatible CPU sensor available; authenticated ingest, M2/304 and wrong-role401 |
| Real Fedora → rootless container HTTPS | PASS | Non-root read-only container, explicit CA/SAN, localhost-only random port, no collector secret mounted; removed at exit |

One existing Starlette/httpx TestClient deprecation warning is emitted. It does
not fail tests; dependency migration is outside this M3 feature. Existing gateway
hash lock was preserved. CI extends the existing pinned-action/pinned-image
workflow with the full Python suite, fixture checks, Ruff and ZIP/unit validation.
CI state belongs to the **exact PR head checks**, not a permanently copied green
badge or the older M2 run. Local results above are not asserted to be GitHub CI.

## Local firmware artifacts (not installed)

Firmware change isolated in commit `5600c99`. The full local seven-profile build
ran after that commit. Later changes are Python/deployment/documentation; they do
not change these firmware sources. SDK commit remains
`b774170ff46c393eeb5e495ea37936038d3f4f4f`.

| Image | Bytes | SHA-256 |
| --- | ---: | --- |
| Normal connectivity app | 863472 | `9311046ba985e95a285404b6824ab3c9ec8da1eebe2003fa007656b4d75debcc` |
| Autonomous diagnostic app (regression only) | 880160 | `946b1f8255993b6c646f2bafa5b4bf9cdbadf1c39ab392f8ad4bda397377fcc7` |

Normal app partition remains 0x100000 bytes at0x10000, with185104 bytes free
(17.7%). Autonomous regression has168416 bytes free (16.1%). The existing table
hash remains `7f00b6c042a89b15b0cac534f82ed988caf29278ff5700b0c511eb1b5bb7c820`.
No OTA layout/implementation is added; future OTA needs separate space/layout/
rollback design. Local app hashes identify these exact builds, not a promise of
byte identity with CI metadata or another checkout path.

Private local results directories, all reporting passed/no hardware I/O:
`m0-build-20261019T144823Z-5RAMJA`, `m1-build-20261019T144915Z-DLB5dM`,
`m11-build-20261019T144934Z-kbJKsv`, `m2-build-20261019T144952Z-C9Z7Sk`,
`m2-auto-build-20261019T145023Z-1k5gFp`. Keep their raw logs out of Git.

Rootless gateway build used the official Python base digest fixed in Containerfile
and pip --require-hashes. A transient instance was tested against actual host
metrics and removed. That transient test did not install units or change host
configuration; the later authorized deployment is reported below. The image remains
local for review; nothing was pushed to a container registry.

## Reproduction

Use [Fedora setup](M3-FEDORA-SETUP.md) for isolated Python commands. Firmware:

```sh
bash tools/build-m2-auto.sh --all
# Inside pinned SDK, to inspect deliberate renderer changes:
python3 tools/simulate_m3.py --check
```

The optional rootless-container variant of the host test is explicitly opt-in:

```sh
podman build -f deploy/m3/Containerfile -t localhost/infrabadge-gateway:m3 .
/PATH/TO/LOCKED/VENV/bin/python tools/m3/check_host.py --container-image localhost/infrabadge-gateway:m3
```

This temporary test publishes only a random localhost port and removes its
container/ephemeral files. That smoke test does not install services. All screenshots under
`docs/m3-ui/` use **synthetic** metrics, even though their source indicator is REAL
to exercise that wire/display mode. They are not captures of the physical screen.

## Acceptance and remaining work

The software path and actual Fedora-to-local-gateway path are exercised. Functional
readiness also requires green checks on the current PR head. Draft status is
intentional: review and later operator deployment are separate decisions.

Initially not executed: actual user timer activation and installed Quadlet lifecycle;
these were subsequently verified in the explicitly authorized session below.
At that earlier stage, Wi-Fi LAN and ESP32 validation were pending; the
authorized first physical trial below supersedes those pending items for the
first real-data query and optical observation only. Suspend/logout, sustained
resource measurements, new M3 timer return and electrical measurements remain
pending. No host stress, erase/eFuse/security change, factory restoration or PR
merge has been performed. The board now runs the M3 normal application. Follow
[M3 physical plan](M3-PHYSICAL.md) only after explicit authorization.

## Authorized installed-host validation — 2026-10-19

The operator explicitly authorized creating/activating the collector user timer
and local rootless gateway, with new private M3 files. Original M2 configuration,
certificates, factory backup and frozen rollback packs were preserved. Execution
occurred only after that specific approval, extending the earlier no-install scope.

Installed application source38a1f35, collector ZIP SHA-256
`70c73eddf129a7a0cbc5f3f7e1b61fff557b754ea05295c8930dc0d458229f5c`;
gateway local image `e5d259e53be7c309920ca5a549a10c053e53a639718bd46887e8457cdb7f4c8e`.
The timer unit includes correction245fe2e: initial trigger uses OnActiveSec=30s
instead of an already elapsed OnStartupSec. This avoids a second rapid sample
after the documented manual first run. Container start is not HTTPS readiness:
an initial submission failed before the server was ready; after verified TLS
readiness the collector succeeded. This transient remains in the private journal.

| Installed-host check | Result |
| --- | --- |
| Actual scheduled collector sends | PASS, two successive scheduled samples, measured interval60s |
| Verified TLS, explicit private CA, real metrics and REAL source | PASS |
| Identical snapshot / If-None-Match | PASS304, no TTL extension |
| Collector credential on device endpoint / device credential on ingress | Both rejected401 |
| Stop only collector; wait actual180s sample TTL | PASS, UNKNOWN200 instead of stale304, DATOS CADUCADOS, no current old metrics |
| Resume collector after the gap | PASS, fresh samples accepted and complete CPU metrics recovered |
| Restart only installed M3 gateway | PASS, process memory reset gives UNKNOWN/SIN MUESTRA until next sample |
| Scheduled recovery after gateway restart | PASS |
| Rootless restrictions | UID10001, read-only root filesystem, no-new-privileges, CapEff/CapBnd/CapAmb zero |
| Host port publication | Only127.0.0.1:8443, no LAN/Internet listener |
| Final unit state | Gateway and timer active; collector timer enabled |
| Existing linger | Disabled, unchanged |

Private execution evidence: `results/m3-host-install-20261019T152220Z/`, with
`validation/result.json`, and `results/m3-board-preflight-20261019T152644Z/`.
Do not publish private deployment metadata, certificates, credentials, systemd
journals, raw snapshots or backup contents. This report contains only allowlisted
outcomes, not notebook capacity, sensor inventory or identifiers.

The new laboratory TLS certificate expires **2026-11-18 15:22:20 UTC**. The CA
signing key was not persisted; renewal/CA rotation is a reviewed operation and
future ESP32 trust changes require explicit provisioning authorization. This is
not automatic production certificate management. Secrets remain outside Git;
only the gateway's dedicated directory was SELinux-labeled for its read-only mount.

The normal M3 app was frozen and rechecked at863472 bytes, SHA9311046b (full hash
above), offset0x10000. Matching partition layout, historical M2/M1.1 rollback
artifacts and the private8MiB factory backup were verified **read-only**. No USB
port was opened and no board write occurred. The operator explicitly chose to
leave the ESP32 test pending because current Wi-Fi/LAN availability is uncertain.

A collector pause exercises missing-data semantics and CPU gap recovery; it is
**not evidence of real suspend/resume, logout or device deep sleep**. Those checks
remain separate. No Wi-Fi/VLAN/VPN/DNS/firewall changes, linger activation, host
stress, layered RPM installation or firmware operations were performed.

## Physical preparation resumed — 2026-10-19

Pre-trial firmware/source revision ad052cc has all four checks successful: push workflow39279014223
and PR workflow39279019615, each gateway and seven-profile firmware jobs.
The reviewed application remains the frozen normal-profile SHA9311046b above;
no firmware source change was made for the physical runner.

The operator explicitly approved one M3 app-only load, private provisioning and
maximum20min selected-Wi-Fi publication/exact reply-route exception, followed by
restoration to localhost. Current Wi-Fi/private-config match, interface-specific
mDNS, certificate SAN/dates, synchronized host UTC, existing firewall port range,
rollback packs and factory backup were checked read-only. The initial global
resolver check selected another interface; the per-Wi-Fi Avahi check resolves the
selected address without changing DNS. Tailscale return routing still requires
the approved narrow temporary exception. No physical PASS follows from preflight.

The local trial runner passed Python syntax checks, nine serial-event allowlist
checks, and two deterministic route-cleanup tests (normal exit and wrong-route
failure). Those tests used mocks and did not add routes, start a LAN listener,
open USB, provision or flash. See M3-PHYSICAL for the explicit one-use scope and
operator procedure. The subsequent execution and optical result are recorded
below; the new timer return remains unconfirmed. Energy/autonomy remain DEFERRED.

## First controlled ESP32 trial — 2026-10-19

The explicitly authorized one-use trial loaded normal M3 SHA9311046b once and
received IBPROV_OK. Actual device events then recorded HTTPS200 (transport/TLS
errors zero), an OK cycle and drawn/live/clocked display callback. These are
physical ESP32 transport/callback observations, distinct from host requests and
fixture tests. The operator explicitly confirmed M3/REAL, CPU/RAM/disk, verified
clock and expiry on the screen. Exact simultaneous numeric agreement was not
measured. The new timer return was not confirmed: the serial observer stopped with SerialException after the first
sleep request. No repeated flash, automatic restoration or additional provisioning
was performed. M3 remains installed; the raw trial stays partial.

The agent closed the waiting parent to trigger authorized cleanup; its
KeyboardInterrupt is explained separately from the SDK observer failure and must
not be blamed on the operator. Independent checks confirmed priority5100 absent,
loopback-only published port, active gateway and active collector timer. Per-case
records: [M3-PHYSICAL](M3-PHYSICAL.md) and the allowlisted
[machine-readable index](m3-physical-results.json). Electrical measurements remain
DEFERRED. No new physical timer, no-transfer, stale/recovery or state-transition
PASS is inferred from the first query.

## Autonomous observation tooling — host/fixture validation only

The first physical application/query/screen remains confirmed, while its next
reset/wake cause remains unconfirmed. New lab tools avoid reopening serial during
wake; the installed firmware, collector ZIP, gateway image and localhost units
were not replaced. See [M3-LAB](M3-LAB.md) for scope and commands.

The complete Python suite now passes199 tests (55 new), with pinned Ruff checks
and format. Real upstream TLS tests reject expired/wrong-SAN certificates; the
actual installed-gateway test verifies TLS on both localhost hops, fresh REAL200,
ETag304, authentication401 and an unknown CA. The latter checks the certificate
verification cause, so a connection refusal cannot count as TLS rejection. No
hardware or selected LAN listener was used for these new tests.

Synthetic tests cover bounded private records, redirects/oversize/expired/foreign
payload rejection, role isolation, total request deadline, one TX after USB READY,
no uncertain retry, exact route selectors and independent cleanup despite a failed
collector/observer restoration. The planned physical parent uses a separate7min
collector recovery guard; this was tested with mocks, not triggered on Fedora.

[m3-observer-results.json](m3-observer-results.json) is the public installed-host
summary. The original physical partial report and operator confirmation remain
unchanged. New autonomous requests, stale/recovery screens and exact wake cause
are not claimed until a separately approved session supplies the matching evidence.
Electrical measurements remain DEFERRED; no dependency upgrade was performed for
the existing non-failing Starlette TestClient deprecation warning.
