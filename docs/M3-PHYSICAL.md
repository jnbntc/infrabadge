# M3 — future physical validation (NOT executed)

M3 host metrics and loopback tests do not establish ESP32 TLS, LAN reachability,
optical output, wake behavior or power consumption. The board retains the frozen
M2 autonomous diagnostic terminal. Do not touch USB, reset, provision or flash
from the software validation tools. Electrical/autonomy measurements remain
deferred as requested by the user.

Update2026-10-19: the user authorized the installed host services, bound only to
localhost, and explicitly deferred the ESP32 trial. Wi-Fi is software-blocked and
the notebook now uses wired VLANs; do not change those connections or assume the
M2 Wi-Fi/return-route setup is still applicable. A normal M3 app pack and the
original M2/M1.1/factory backups were verified without opening USB or writing the
board. The physical gate remains closed until a future explicit authorization
and a new network inspection. No phone/client test is requested.

## Gates before any board write

1. Review the draft PR and exact source SHA; CI and seven-profile regression pass.
2. Approve a real Fedora installation separately, then observe user timer and
   rootless gateway for several samples, stop/recover collector and confirm TTL.
3. Check selected LAN hostname DNS/mDNS from the Wi-Fi context, TLS CA/SAN/dates,
   private token-role separation, firewall/client isolation and return routes.
   Localhost success is not evidence of LAN/ESP32 success.
4. Preserve original factory backup, frozen M1.1 and M2 app manifests, partition
   hash and private provisioning data. Do not overwrite originals.
5. Build normal connectivity profile, not autonomous diagnostic. The former
   now supports real data; the installed historical binary rejects simulated=false.
6. Present a concrete app hash/size/offset and configuration plan, including
   trusted UTC seed and selected device/node binding. Obtain **new explicit
   authorization** before app write or provisioning. M2 historical consent does
   not authorize a M3 board write.

No automatic flashing command is provided here. Use the controlled existing
M2 app-only procedure after review, never erase_flash, full-flash restore, eFuse,
security-feature changes or a different partition layout. Preserve normal NVS
configuration; version1 snapshot cache is intentionally ignored by the new app.
M2 diagnostic namespace is separate. A cold reset still needs trusted UTC as in M2;
the external RTC2056 is not a valid clock source.

## Acceptance matrix after authorization

| Test | Expected | Required evidence |
| --- | --- | --- |
| Initial real sample | Logical node, REAL, CPU/RAM/disk, identified CPU temp or UNKNOWN, sample UTC/expiry | Operator optical observation + sanitized gateway event |
| No changed pixels | No panel transfer | Existing diff diagnostic/counter and optical observation; a 304 alone is insufficient |
| State policy | HEALTHY/WARNING/CRITICAL follow configured windows | Synthetic private ingress fixtures on separate lab node/token, no host stress or changed real thresholds |
| Collector stops | After sample TTL, UNKNOWN/OFFLINE, DATOS CADUCADOS, no old live values | Controlled timer stop with operator approval, gateway timestamps, optical check |
| Collector recovers | New real sample accepted, health updates, expiry tied to input | Sanitized POST/GET and optical check |
| Gateway/network failure | CONSULTA NO VALIDA with network error, historical data not current | Authorized bounded lab fault; distinct from collector stale state |
| Sleep/wake | Radio stop and autonomous timer query, no reset/clock loss | Proper retained journal/reset/wake evidence; disappearing USB/retained e-paper is insufficient |
| Unchanged M0/M1/M1.1 behavior | No regressions introduced | Existing software regression plus targeted future physical checks if needed |

No short-term numeric screen accuracy or new M3 deep-sleep cycle is physically
validated yet. With per-sample timestamps the image may change each successful
sample even when rounded values match; no continuous refresh is added, and
identical frames are still suppressed. The 180 s TTL can shorten sleep and affects
unmeasured energy use. Do not infer battery life from its nominal 400 mAh.

## Rollback

Stop only the new host services with separate operator approval. Keep original
M2 gateway/private files for restart. For a future board rollback, compare the
exact approved M2 app artifact and partition compatibility, then request explicit
permission for that app-only write. No automatic restoration or erase. A legacy
firmware ignores the newer snapshot-cache version but retains normal config.
NVS is plaintext; removing the collector or rolling back firmware does not revoke
its token. Revoke the collector digest in the gateway as a separate reviewed step.
