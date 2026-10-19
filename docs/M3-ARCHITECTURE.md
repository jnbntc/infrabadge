# M3 — Fedora Atomic monitoring

## Scope and decisions

M3 starts from integrated `main` 19a9a00 (M1.1 #2 and M2 #3 merged). The actual
backend is `gateway/infrabadge_gateway`, with a synchronous M2 status endpoint,
strict Pydantic models and an in-memory mock cache. It had no collector ingress,
database or scheduler. M3 extends that architecture; it does not replace it.

```
Fedora host /proc, statvfs, /sys/class/hwmon (read only)
  -> collector acquisition / normalization
  -> one bounded, authenticated HTTPS POST
  -> FastAPI validation / per-node health evaluation / last valid sample
  -> unchanged GET /api/v1/devices/{device_id}/status, status-v1 JSON + ETag
  -> existing ESP32 HTTPS cycle / framebuffer diff / Power Manager
```

The collector is a stdlib-only Python 3.11+ oneshot. It runs **on the host**,
never inside Distrobox/Podman: container `/proc`, sysfs and mount namespaces may
describe the container. Known container markers and root execution are refused.
This is a guard, not a namespace attestation mechanism. No process/socket inventory,
recursive disk scanning, shell commands, Podman socket or personal files are read.

The rootless gateway is a separate resident process/container. It uses one worker
and bounded in-memory state for configured nodes; no database. Restart loses
samples, hysteresis and replay history and produces UNKNOWN until a new valid
sample arrives. Do not deploy multiple workers/replicas without a shared store.

## Acquisition and wire model

`collector/fedora/infrabadge_collector/acquire.py` performs bounded reads and pure
parsing. `runtime.py` owns private configuration/CPU-baseline I/O; `transport.py`
owns one POST. Only the CPU counters, CPU count and uptime are persisted. The
lock prevents overlapping collectors. State is stored before transport: a network
failure does not make the next delta span several minutes unintentionally.
If a full/read-only filesystem prevents writing that cache, available metrics are
still sent with a sanitized warning. If even the lock cannot be created, CPU
starts as unknown without a shared baseline, while a known disk/RAM alarm can
still be delivered. An overlapping locked collector is refused normally.

POST `/api/v1/collectors/{node_id}/metrics` accepts exactly:

| Field | Meaning |
| --- | --- |
| schema_version, node_id, collector_version | Version 1, configured logical name, semantic collector version |
| collected_at | Integer UTC epoch seconds, 2020–2100 |
| cpu | Nullable utilization %, logical CPUs, three load averages |
| memory | Total/available/used bytes, used %, explicit fallback-estimation flag |
| disk | Logical mount label, total/available bytes, used % |
| temperature | Nullable Celsius and allowlisted CPU sensor class |
| uptime_seconds | Nullable nonnegative uptime |
| errors | Bounded list of public acquisition error codes |

CPU utilization uses deltas of the first eight aggregate `/proc/stat` fields,
counting idle+iowait as idle and excluding guest fields already included in
user/nice. Counter decrease (including legitimate iowait decrease), reboot,
hotplug, zero delta or a gap over three configured intervals invalidates that CPU
sample. The first scheduled run warms up and can yield UNKNOWN. Load averages
are descriptive, not percentages or health triggers.

RAM uses MemAvailable. On older kernels only, a labeled approximation uses
MemFree+Buffers+Cached+SReclaimable-Shmem, clamped to total. Used is total minus
available. Disk uses statvfs f_bavail for the unprivileged user; reserved blocks
therefore count as unavailable. No claim that filesystem capacity equals physical
device capacity or that this detects disk I/O health.

Temperature selection accepts coretemp package labels, then core labels; AMD
k10temp/zenpower requires explicit Tdie. Within a priority the hottest valid
channel wins. Faulted/disabled channels and values outside -40…150 C are ignored.
ACPI, GPU, NVMe and unlabeled/Tctl-only channels are not guessed to be CPU die.
Unsupported/absent sensors yield null, never a fabricated value.

No hostname, username, serial, MAC, machine/boot UUID, exact mount path or raw
sensor path is transmitted. Logical names are operator-selected; do not choose
personal names. Raw metrics still reveal workload and capacity: they require the
same confidentiality as other lab monitoring data.

## Authentication and ingress

Device tokens and collector tokens are separate, scoped to their configured
identity and endpoint. Store high-entropy URL-safe tokens outside Git, with
0700 folders/0600 files. Gateway stores SHA-256 digests, supports two digests for
rotation, and refuses digest reuse across identities/roles. Comparisons use hmac.
Knowing a collector token never grants access to a device status endpoint or
another node. The client cannot submit a status, alert string or command.

Authenticate before reading JSON. Limit body to 8192 bytes, ten-second body
deadline, identity content encoding and application/json. Reject extra/duplicate
keys, nonfinite/out-of-range values, incoherent percentages/bytes, foreign node,
future or expired samples. Validation errors do not echo inputs. Responses:
202 accepted, 401 authentication, 409 duplicate/older timestamp, 413 size,
415 media/encoding, 422 invalid/old/future sample, 429 interval too short.
Replay protection is within process lifetime; a gateway restart is not a durable
replay barrier. Authenticated compromised collectors can lie about their own
metrics; M3 provides no remote attestation or protection against compromise of
the same Unix user, root, CA or gateway.

Collector HTTPS requires explicit CA, hostname/SAN and valid certificate dates,
minimum TLS1.2. No proxy environment, redirects, retries or TLS bypass. A Linux
main-thread signal deadline bounds DNS/connect/TLS/body together; systemd adds a
20-second process deadline. Acquisition failures produce nullable metrics and
error codes. Transport failure logs a generic structured code, with no response
body, tracebacks, token, URL, path or payload. Access logs are disabled at gateway.

## Health policy

Policies belong to the server-side collector configuration. Defaults:

| Metric | WARNING | CRITICAL | Confirmation |
| --- | --- | --- | --- |
| CPU utilization | >=85% | >=95% | 3 consecutive accepted samples for each threshold |
| RAM availability | <=15% | <=5% | 1 sample |
| Disk availability | <=15% | <=5% | 1 sample |
| CPU temperature | disabled | disabled | Explicit reliable sensor and both configured thresholds required |

All thresholds are configurable. Recovery requires two consecutive samples
strictly beyond hysteresis: CPU five percentage points below threshold,
RAM/disk three points above, temperature three Celsius below. Warning and critical
latches are independent, so alternating 86/96/86 still confirms a warning. A single
CPU spike cannot trip an alarm. Default minimum sample spacing is 30 s and maximum
gap 120 s; gaps or uptime reversal reset evidence. Missing metric observations
clear that metric's latch and cannot perpetuate an old critical result.

For fresh samples: **CRITICAL > WARNING > UNKNOWN > HEALTHY**. Missing CPU
utilization/load, memory, disk or uptime causes UNKNOWN unless another available
metric confirms a warning/critical condition. Missing temperature is optional
unless explicitly enabled for health. An estimated memory fallback is identified
in the ingress model; current Fedora MemAvailable is preferred. No attempt is
made to force load, fill disk/RAM or heat the notebook for tests.

TTL defaults to 180 s from **collected_at**. At expiry, absent data or clock
reversal, state becomes UNKNOWN and metric values disappear from the public
snapshot. Last accepted input remains in memory for ordering/recovery only.
Collector failure and sleeping/powered-off notebook cannot be distinguished from
each other by missing samples. They are distinct from ESP32 Wi-Fi/DNS/TLS failure.

## M2 contract, cache and UI compatibility

GET path, identity, schema version, bounded counts/alerts, server UTC header,
strong ETag and If-None-Match remain unchanged. An unchanged representation
returns 304 without extending expiry. Fresh real snapshot expiry is always sample
timestamp+TTL. Expiry is checked before ETag; an old healthy tag receives a new
UNKNOWN 200, never a stale healthy 304. UNKNOWN is a valid authenticated control
response with its own short TTL and **no current metric claim**.

For late but still fresh recovery, representation generated_at is floored at the
previous control representation time to honor the firmware's anti-backwards
guard. This never extends sample expiry; the actual sample UTC is in MUESTRA.
New accepted samples change timestamps and ETag even if rounded values match.
Frame diff still suppresses identical pixel frames; no live ticking clock or
continuous refresh loop was introduced. Default real TTL can shorten existing
900-second polling sleeps to <=180 s: freshness wins over an unmeasured battery
estimate. Frequent sample labels can cause more full refreshes; energy/autonomy
remain uncharacterized.

Inspection found two hard M2 restrictions: parser required simulated=true and
renderer unconditionally printed SIM. Commit 5600c99 isolates the necessary
firmware change: accept a strict boolean, preserve source, reuse M1 alert geometry
for node/CPU/RAM/disk/temperature/sample UTC, show REAL and expiry. Mock SIM pixels
remain unchanged. M0/M1/HAL/Power Manager/radio/TLS are preserved.
The installed frozen M2 diagnostic **does not support real snapshots**; it is not
silently upgraded. New firmware is compiled only, not loaded.

Snapshot NVS format is version2 to avoid interpreting legacy padding as REAL.
Version1 snapshot cache is refused even with a valid CRC; normal configuration
format/namespace is retained. Downgrading similarly refuses version2 cache. No
partition, factory backup or provisioning is changed. No automatic erase.

## Deployment and limits

Collector: reproducible zipapp, /usr/bin/python3 -I, user oneshot + monotonic
timer. Gateway: pinned Python image and hash-locked existing gateway dependencies,
non-root read-only container, dropped capabilities, explicit loopback/LAN port,
no Podman socket. The current image reuses the complete existing Python lock,
including test/lab dependencies; runtime dependency splitting is future work.
Same-user access and plaintext private files are the security boundary, not
encryption at rest. Never automatically expose Internet ports, change firewall/
Tailscale/DNS, enable linger or install layered RPMs.

Primary references: [Linux proc](https://www.kernel.org/doc/html/latest/filesystems/proc.html),
[hwmon ABI](https://docs.kernel.org/hwmon/sysfs-interface.html),
[coretemp](https://docs.kernel.org/hwmon/coretemp.html),
[k10temp](https://docs.kernel.org/hwmon/k10temp.html),
[systemd timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html),
[credentials](https://systemd.io/CREDENTIALS/),
[rootless Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html).
