# M3 validation — software and Fedora host evidence

Validated locally on 2026-10-19. This report contains allowlisted outcomes and
synthetic examples, not notebook inventory, private snapshots, credentials or USB
logs. M3 branch: `feat/m3-fedora-monitoring`, based on integrated main19a9a00.

## Executed checks

| Check | Result | Scope |
| --- | --- | --- |
| Collector + gateway + integration | **142 passed** | Deterministic fixtures, pytest root config, Python3.14 host venv |
| CPU/memory/load/uptime parsing and deltas | PASS | Guest accounting, decrease/hotplug/gap/warmup, MemAvailable/fallback, invalid/missing/read failures |
| Disk and hwmon | PASS | statvfs fixture, supported/absent/faulted/unreliable CPU channels; no runner sensor dependency |
| Authentication and strict ingress | PASS | Role/node isolation, malformed/duplicate/oversize/NaN, range/consistency, UTC, replay/out-of-order, rate spacing |
| Policy and cache | PASS | CPU confirmation/hysteresis, RAM/disk precedence/recovery, explicit temperature opt-in, UNKNOWN/stale/recovery, expiry before304 |
| Actual loopback TLS integration | PASS | Fixture acquisition through collector transport, CA/SAN/date checks, M2 contract/304; expired and wrong-host certs rejected |
| Package and staging | PASS | Byte-reproducible ZIP, isolated Python execution, temporary-home installation, no enable/overwrite, private config preparation |
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
metrics and removed. No unit, persistent listener, LAN exposure, firewall/route/
DNS setting, linger or host RPM was installed/changed. The built image remains
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
container/ephemeral files. No systemd service is installed. All screenshots under
`docs/m3-ui/` use **synthetic** metrics, even though their source indicator is REAL
to exercise that wire/display mode. They are not captures of the physical screen.

## Acceptance and remaining work

The software path and actual Fedora-to-local-gateway path are exercised. Functional
readiness also requires green checks on the current PR head. Draft status is
intentional: review and later operator deployment are separate decisions.

Not executed: actual user timer activation, suspend/logout/linger scenarios,
installed Quadlet lifecycle, sustained resource measurements, selected Wi-Fi LAN
DNS/routing/firewall, real notebook data on ESP32, M3 optical/sleep validation or
electrical measurements. No host stress, board write, provisioning, reset,
erase/eFuse/security change, factory restoration or PR merge was performed.
The board still has the M2 terminal diagnostic. Follow
[M3 physical plan](M3-PHYSICAL.md) only after explicit authorization.
