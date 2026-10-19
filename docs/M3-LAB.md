# M3 — bounded lab observation without a new firmware load

## Why this path

The first normal-M3 application query and REAL screen were physically confirmed.
The serial observer then stopped with SerialException. That partial capture does
not prove an ESP32 defect, successful timer return or a power measurement. Opening
USB around wake can disturb reset/time trust, and enumeration can race port
readiness. Preserve the original records; do not repeat their consumed load plan.

The new optional lab path reuses the installed application and installed collector
and gateway. It does not modify production endpoints or their configuration:

```
Fedora collector -> existing rootless gateway on localhost:8443
                     -> temporary verified HTTPS observer on selected Wi-Fi:8443
                          -> existing ESP32 status-v1 client
```

The observer is a temporary lab front end, not a new permanent service or a
replacement gateway. Both HTTPS hops verify CA, SAN and dates. It accepts only one
configured device GET, authenticates with that device's existing digest and refuses
collector ingress, foreign paths, queries, request bodies, redirects and arbitrary
header forwarding. Its upstream is fixed to localhost. Response bytes, ETag,
server UTC and validity are preserved; it creates no health values or cache.

Limits: eight concurrent front connections, four upstream connections, an eight
second total request deadline, at most2048 response bytes, and maximum20min server
lifetime. Wildcard, loopback, link-local, multicast and global listen addresses are
refused in LAN mode. IPv4 selection still needs the private Wi-Fi preflight.

## Evidence and confidentiality

Only bounded enums/counters/timestamps are recorded: sequence, HTTP status,
conditional request, normalized health, fresh/stale/absent control and fixed outcome.
The private journal retains64 events (hard maximum128), atomically with0600 files
under0700. It contains no IP/MAC, URL, node/device name, token, header, ETag, raw
snapshot, capacity, sensor inventory or original exception text. Authentication
failures never reach the upstream. TLS handshake probes do not count as device GETs.

The observer terminates TLS locally, so the same Unix user/process can access
payloads and credentials in memory. This is trusted local lab software, not
attestation or isolation from a compromised user/root. The collector code and its
separate credential are unchanged. Do not publish private client/provisioning inputs.

Successful observations identify requests authorized with the device token; the
operator must keep other clients from using it. They establish autonomous polling
only with the accompanying no-buttons/no-reset/no-monitor observation. They do
**not** expose the ESP32 reset/wake registers. Exact reset8/wake4, electrical sleep,
framebuffer transfers and optical accuracy cannot be inferred from them.

## Reproducible preparation and localhost check

Use the existing locked gateway Python environment. Replace the private paths
locally; no credential value is passed in command arguments:

```sh
python tools/m3/prepare_observer.py \
  --deployment /PRIVATE/M3-HOST-DEPLOYMENT \
  --device-config /PRIVATE/EXISTING-M3/device.json \
  --output "$HOME/.local/share/infrabadge-lab/m3-session-NEW"
```

This makes new private inputs and checks device/gateway token binding, existing
M3 CA/certificate, trusted host UTC, actual SSID, interface-specific mDNS and reply
routing. The actual SSID is compared independently of Fedora's connection alias.
It never changes a connection/profile, requests a password, opens USB, binds LAN
or starts units. Existing folders are refused. For a host-only check when Wi-Fi is
unavailable or different, add `--loopback-only`; that plan cannot be executed as a
physical session and does not copy Wi-Fi credentials.

```sh
python tools/m3/check_observer.py --private /PRIVATE/NEW-SESSION
python tools/m3/physical_session.py --private /PRIVATE/NEW-PHYSICAL-SESSION
```

The first command uses a temporary random localhost TLS port against the installed
gateway: fresh REAL200, ETag304, authentication401 and rejection of an unknown CA,
then complete cleanup. A plain connection failure cannot count as CA rejection.
A second invocation requires a new folder; old evidence is not deleted. The
second command is preview only without its explicit execution flag.

## Physical execution after new explicit approval

The previous M3 flash/provision plan is consumed. This separate plan permits **no
firmware write**. Before running, obtain approval for one new private USB UTC
provisioning, maximum20min selected-Wi-Fi HTTPS/reply-route window, and bounded
collector pause/recovery. Keep USB connected, only the Waveshare present, other
serial monitors closed and no other clients using the device token.

```sh
systemd-inhibit --what=sleep --mode=block --who=InfraBadge \
  --why='M3 observation' python tools/m3/physical_session.py \
  --private /PRIVATE/NEW-PHYSICAL-SESSION --authorized-m3-observation
```

Start without sudo. Only the precise routing child may request sudo, with
priority5100, exact gatewayLAN/32 to the connected Wi-Fi subnet, TCP source8443,
main table. Its independent maximum20min lifetime and exact-selector deletion do
not change VPN, DNS, firewall, VLAN, persistent profiles or linger. If the existing
route is already correct, no privileged child is needed.

The original gateway remains bound to localhost throughout, with no restart or
image change. A separate host observer briefly listens on the selected Wi-Fi IP.
The session consumes its new execution marker once; never remove it to retry.

1. Follow the one LISTO BOOT instruction to open the existing normal firmware's
   provisioning window. One private frame is sent only after IBPROV_READY; require
   IBPROV_OK. No esptool, automatic reset, firmware load or erase is available.
   Existing Wi-Fi, token and CA stay the same; host UTC is freshly seeded.
2. The helper waits for USB disappearance and closes the handle. USB is **never
   reopened** during autonomous queries. Its disappearance is not a sleep/current
   proof. Uncertain provisioning stops without retry.
3. Observe the first real response and a later request without button/reset/monitor
   intervention. The observer makes no synthetic HTTP readiness requests.
4. Pause only the collector timer/service and wait for actual sample TTL expiry.
   Observe `stale_response_delivered_observe_screen`: gateway UNKNOWN maps to
   **OFFLINE / REAL / DATOS CADUCADOS** on the existing UI, with no old live metric
   values. This differs from CONSULTA NO VALIDA due to ESP32 network/TLS failure.
5. Resume the original timer and await a new real sample/query. Observe
   `recovery_response_delivered_observe_screen`: CPU/RAM/disk and REAL return.
   WARNING/CRITICAL may be legitimate; no host stress or threshold edits are used.
6. Stop the observer and remove its exact route. Keep the original collector active.
   A transient user guard restores the collector after at most7min from pause even
   if the parent dies. It is removed after confirmed restoration. No persistent
   service/timer is installed. Optical confirmations are collected separately in
   chat/evidence; a terminal question cannot block critical cleanup.

The script publishes progress/results in a new ignored private results folder.
Request/TTL observations and operator screen confirmations remain separate. A
completed host graph is not a full physical-suite PASS or an exact timer-cause
proof. Any cleanup failure is explicitly incomplete. Electrical/battery/autonomy
remain DEFERRED. After cleanup the next board query can become OFFLINE because
permanent LAN deployment is outside this bounded approval.

## Validation performed

- 199 Python tests passed, including55 new observer/session cases: role/path
  isolation, duplicate auth, fixed upstream/header forwarding, malformed/oversized/
  expired/foreign/simulated replies, ETag/304 and TTL, total timeout, CA/SAN/dates,
  wildcard rejection, private bounded journal, one configuration TX, SSID-versus-
  alias, and independent cleanup after failures.
- Pinned Ruff checks/format passed. No new runtime dependency or firmware change.
- Actual installed Fedora gateway through a temporary localhost HTTPS observer:
  REAL200,304,401 and unknown-CA rejection passed with both TLS hops verified.
  Public allowlisted summary: [m3-observer-results.json](m3-observer-results.json).
- The explicitly authorized observation session stopped before sending any
  configuration: serial open succeeded, then SerialException occurred before
  READY. All three cleanup checks passed. No autonomous query or new screen
  evidence was collected; see [attempt index](m3-observation-attempt.json).
- The helper now tolerates up to four connection failures within60s only before
  its first TX, binding the same hardware identity privately in memory. After any
  TX, an exception stops without reopening/resending. Four additional tests cover
  pre-TX reconnect, changed identity, bounds, and post-TX refusal. No firmware
  change was needed.

USB disappearance during deep sleep is documented by [Espressif](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/api-guides/usb-serial-jtag-console.html).
The failed open/read alone does not establish its cause; the bounded pre-TX
reconnection handles enumeration loss without claiming a reset or hardware fault.

A zero-TX continuation uses a new private folder linked by `continuation_of` and
an exclusive parent `continuation.json`. The runner rechecks the prior attempt
has `attempted=false`, `ack=false`, no firmware write, completed cleanup and the
same interface/address/network/port/time/provisioning scope. Any prior TX/ACK or
changed scope is rejected. It never removes or reuses an execution marker. Four
additional tests cover this guard, including refusal after an uncertain TX.

## Physical result

The linked continuation224512Z completed one UTC provision without flashing,
then observed autonomous REAL queries, stale UNKNOWN after collector pause and
fresh HEALTHY after restoration. The operator confirmed all three screen stages
and no intervention. Independent route/listener/collector cleanup passed.
See [M3-PHYSICAL](M3-PHYSICAL.md#completed-autonomous-observation--2026-10-19)
and [the separate sanitized index](m3-observation-results.json). Exact wake
registers, physical304/no-transfer and electrical consumption remain unverified.
Both execution markers are consumed; this result is not permission to rerun.
