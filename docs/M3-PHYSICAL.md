# M3 — controlled physical validation

M3 host metrics and loopback tests do not establish ESP32 TLS, LAN reachability,
optical output, wake behavior or power consumption. The historical frozen M2
diagnostic was replaced by the explicitly authorized normal M3 app during the
controlled trial reported below. Do not touch USB, reset, provision or flash from
the software validation tools. Electrical/autonomy measurements remain deferred
as requested by the user.

Earlier on2026-10-19: the user authorized the installed host services, bound only to
localhost, and explicitly deferred the ESP32 trial. At that stage Wi-Fi was
software-blocked and the notebook used wired VLANs. That historical network
state was not reused for the subsequent trial; the Wi-Fi was inspected again. A normal M3 app pack and the
original M2/M1.1/factory backups were verified without opening USB or writing the
board. The physical gate stayed closed until the explicit authorization and new
network inspection recorded below. No phone/client test is requested.

## Current authorized preparation — 2026-10-19

The operator has now resumed the physical trial and explicitly approved the
concrete plan below. Electrical measurements remain **DEFERRED**. Authorization
and preparation are not evidence that the application was loaded or the ESP32
successfully connected.

- App only: **863472 bytes**, offset **0x10000**, SHA-256
  `9311046ba985e95a285404b6824ab3c9ec8da1eebe2003fa007656b4d75debcc`.
  Normal connectivity profile, not the old autonomous diagnostic. No bootloader,
  partition-table, whole-flash or eFuse write, no security-option changes.
- Matching partition tables, M2/M1.1 rollback packs and the private factory backup
  were rechecked without USB access. Existing backups are preserved.
- The Wi-Fi is now connected and matches the original private device configuration.
  Interface-specific Avahi resolution returns the selected Wi-Fi IPv4 and the
  existing M3 certificate covers the hostname with valid dates. The global host
  resolver can instead select another local interface; no global DNS override
  is added. Host resolution still does not prove ESP32 mDNS success.
- The Wi-Fi firewall zone already allows TCP8443 via its existing port range;
  no firewall modification is part of this plan. The return lookup still selects
  Tailscale. A temporary exact source/subnet/TCP8443 rule at priority5100 may
  select the main connected Wi-Fi route for a maximum20min.
- Temporarily add only the selected Wi-Fi address to the rootless gateway,
  preserving localhost publication. Restore the original Quadlet and verify
  loopback-only publication at completion. A separate transient user timer bounds
  LAN publication even if the parent terminates; no persistent timer or linger.
- Provision once over trusted USB with the M3 CA, retained individual device token,
  existing Wi-Fi credentials and fresh synchronized host UTC. Collector credential
  stays separate. Preserve NVS namespaces; normal configuration is intentionally
  updated. NVS snapshot-cache version1 is ignored by the new app.

Private preparation index: `results/m3-physical-preparation-20261019T211456Z/`.
The current private plan pointer is `results/m3-physical-plan-active.json`.
Configuration, selected addresses, identifiers and raw flash output stay private;
only closed-enum/numeric serial events may be exported. The one-use execution
marker must never be deleted to retry an uncertain write.

### Controlled execution and observations

1. Start the reviewed local runner in a normal terminal, without sudo in front.
   Keep USB connected and other monitors closed. Sleep inhibition is temporary.
   Sudo is requested only by the bounded route helper; SDK/USB runs as the user.
2. The runner checks TLS and a fresh real collector sample before accessing the
   board. It performs the single app-only write. A failed/uncertain write stops;
   no automatic rewrite, reset loop or factory restoration.
3. Retained normal NVS may initially produce CLOCK after the cold load. Wait for
   the explicit **LISTO BOOT** instruction, then hold BOOT for3s and release.
   This requests a setup wake, which must never count as a confirmed timer wake. BOOT must not be
   held during a reset. The private configuration is sent once after IBPROV_READY;
   require IBPROV_OK before claiming provisioning success.
4. Observe the actual display when prompted: M3, REAL, logical node, CPU/RAM/disk,
   a supported CPU temperature or unavailable indication, HORA VERIFICADA and
   VENCE. Actual health may legitimately be WARNING/CRITICAL; do not force load
   or edit thresholds merely to obtain HEALTHY. Record unobserved items as pending.
5. Leave buttons/USB untouched. A subsequent successful cycle with reset8/wake4
   is required for timer-return evidence. The collector continues every60s; the
   real sample TTL may shorten the normal900s interval to <=180s. The monitor
   keeps DTR/RTS false, compares the USB identity privately and stops on unexpected
   reset. If the boot line is missed, a successful query alone does not prove its
   wake cause. USB disappearance is not a power measurement.
6. At completion remove the exact rule and temporary LAN listener, verify localhost
   TLS readiness and preserve every result. The M3 application stays installed;
   after LAN cleanup its next query can legitimately become OFFLINE. This is a
   bounded trial, not authorization for permanent LAN deployment.

A callback marked unchanged is not an optical measurement; HTTP304 alone is not
proof of no panel transfer. The first trial does not force synthetic states,
collector outages, notebook suspend/logout or gateway faults on the physical
screen. Host/fixture results for those cases remain distinct. Obtain additional
controlled observations where required instead of inferring them from this run.

## Executed trial — partial evidence, 2026-10-19

Current machine-readable index: [m3-physical-results.json](m3-physical-results.json).
Private evidence directory: `results/m3-physical-20261019T212131Z/`.
The exact normal M3 application above was loaded once and provisioning returned
IBPROV_OK. The board now runs M3; neither M2 nor factory firmware was restored.

| Observation | Result |
| --- | --- |
| App-only write, unchanged partition layout | Completed, esptool success; no bootloader/table/full-flash/eFuse command |
| Fresh private USB provisioning | IBPROV_OK |
| Actual ESP32 HTTPS | HTTP200, transport/TLS error fields zero |
| Application cycle | OK |
| Display callback | drawn, live=1, clock=1 |
| Operator optical observation | Confirmed by explicit operator reply and terminal s: M3, REAL, CPU/RAM/disk, HORA VERIFICADA, VENCE |
| Subsequent M3 timer return | Not confirmed |
| Serial observer | Stopped with SerialException after the first sleep request; do not attribute this alone to a board or TLS defect |
| Route / gateway cleanup | Priority5100 absent; only127.0.0.1:8443 published; independently checked |
| Collector / gateway after cleanup | Both active |
| Electrical / autonomy | DEFERRED |

The cold-load CLOCK screen was expected until fresh UTC provisioning. The
successful provisioned cycle requested174s sleep, which is scheduling metadata,
not a current measurement or completed timer-return proof. No reset8/wake4 return
was captured. The raw `board.json` remains partial with SerialException. The
controller was subsequently stopped by the agent to run its cleanup while its
terminal optical response had not yet been persisted; its parent record therefore
says KeyboardInterrupt. This is not evidence that the operator interrupted USB or the
trial. The original records were retained, with a separate controller-closeout
annotation, rather than rewriting their failure reasons. The operator subsequently
confirmed the physical display explicitly; `operator-observation.json` records
that separate evidence without changing the original partial capture.

The private host references use separate host HTTPS requests; they must not be
counted as ESP32 requests. Actual physical HTTP200 evidence comes from the
allowlisted device transport event. The operator confirmed the real labels/values
were visible. Exact numeric agreement with a simultaneous sample was not
independently measured. No unchanged-pixel/no-transfer, physical threshold/failure
transition, stale-data recovery, new M3 deep-sleep return,
suspend/logout, energy or battery-life PASS is claimed. Existing M2 and fixture
results retain their own scopes. A new controlled follow-up must reuse the installed
app where possible, preserve this consumed plan and obtain approval for any new
provisioning/window; never repeat this app load merely because observation stopped.

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

Numeric screen accuracy and a new M3 deep-sleep return remain unconfirmed.
The first actual HTTPS200/live draw is recorded above; it does not establish them.
With per-sample timestamps the image may change each successful sample even when
rounded values match; no continuous refresh is added, and
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

## Next observation path prepared — no new physical result

[M3-LAB](M3-LAB.md) now defines a separate no-flash session using the installed
application. The observer records authenticated requests at the gateway and keeps
USB closed after one separately authorized UTC provisioning. It can exercise
actual stale-data/recovery with a bounded collector pause. Its localhost path was
verified against installed real metrics; this is not a new ESP32 result.

The user selected the previous Wi-Fi. Its saved profile was activated once without
editing it; the actual SSID/mDNS/TLS match was rechecked. A different Fedora profile
alias does not itself require Wi-Fi reprovisioning. New NVS provisioning and the
new LAN/routing window still require the concrete session approval, since the
previous one-use authorization is consumed. No additional flash was performed.
