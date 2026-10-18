# InfraBadge development instructions

- Work only in this repository, `jnbntc/infrabadge`. Confirm Git root and origin.
- Keep distrobox-stack dedicated to environment management; do not edit it here.
- Target Waveshare ESP32-S3-ePaper-1.54 V2 only, ESP-IDF v5.5.5 at the locked commit.
- Check docs/HARDWARE.md and docs/upstream.json before assigning any GPIO.
- Separate board HAL, device protocols, rendering and application orchestration.
- M0 has no Wi-Fi, Bluetooth, gateway, MQTT, Prometheus or credentials.
- Never flash hardware automatically. No erase_flash, eFuse writes, Secure Boot
  or Flash Encryption changes. Factory backups stay private and outside Git/CI.
- Compile all three profiles using tools/build.sh all in the prepared container.
  Run tools/test.sh for hardware-free checks. Never report an unexecuted check as passed.
- Keep third-party notices and pin SDK/dependency versions. Avoid broad driver bundles.
- Physical success, battery calibration, sleep current and wakeup remain unverified
  until a human performs the documented checks on the actual board.
- Do not run git push, create a release or merge without user authorization.
- Current M2 request authorizes a separate M1.1 integration proposal and a draft M2
  PR. feat/m1.1-integration preserves b2dcf7a in draft PR #2, base main. Work M2 on
  feat/m2-connectivity, based on that commit; stack the M2 PR on the integration
  branch while #2 remains unmerged. Do not rewrite/delete feat/m1-ui or merge PRs.
- docs/M1-M11-VALIDATION.md is the consolidated evidence/limitations index; older
  milestone reports and build manifests keep their original validation scope.

## M1 UI

- Historical M1 branch is feat/m1-ui; M0 physical baseline is local commit 910bf9f.
- Keep M0 main/HAL/panel protocol unchanged unless a demonstrated fix is necessary.
- M1 is offline and uses simulated infrastructure AND device diagnostics.
- Do not trust the advancing RTC as wall time; always show unsynchronized state.
- UI model/render/input and display caching are portable C. Power stays separate.
- Only full refreshes through the M0 epaper driver; no assumed partial update support.
- Run tools/build-m1.sh --all, native tests and tools/simulate_ui.py --check.
- Review the 12 visual references before deliberate --update changes.
- One M1 load was explicitly authorized and performed on 2026-10-17. Physical
  functional validation over USB is complete: see docs/M1-PHYSICAL-RESULTS.md.
  Consumption, battery-only operation, targeted identical-frame cancellation and
  other listed checks remain pending. Never reflash automatically.
- docs/M1-PHYSICAL.md contains the future manual procedure; never run it as build.

## M1.1 timer diagnostic

- M1.1 originated on feat/m1.1-timer-diag and is now published on feat/m1-ui,
  outside the merged PR #1 snapshot;
  keep normal M1 UI behavior and M0 HAL unchanged.
- Build the separate timer profile with tools/build-timer.sh --all (five profiles).
- Run native tests with sanitizers and tools/simulate_timer.py --check; inspect the
  six synthetic references before deliberately updating them.
- Require valid RTC record, armed sleep, deep-sleep reset and TIMER wake for each
  increment. Three 60-second cycles only, no fourth sleep after terminal PASS.
- The manual BOOT start is required after physically disconnecting USB. Firmware
  does not establish the power source; simulated PASS never proves physical success.
- On 2026-10-17 the user authorized proceeding with the M1.1 physical test. This
  covers one controlled load of the approved diagnostic and the battery-only
  observations. The one load completed; the operator confirmed a fresh 0/3 through
  PASS 3/3 sequence exclusively on battery, USB removed and no intervention.
  Functional timer validation is closed; current, autonomy and timer accuracy
  remain unmeasured. The board retains the terminal M1.1 diagnostic.
  Do not repeat a load or restore firmware automatically. Check
  docs/POWER-BASELINE.md for the recorded result.
- Track procedure, limits and physical results in docs/POWER-BASELINE.md; keep raw
  board logs and private backups outside Git/CI.

## M2 connectivity

- M0/M1/M1.1 remain separate profiles. Reuse their HAL, panel, renderer and Power
  Manager without source changes unless evidence requires a fix.
- Run tools/build-m2.sh --all (six profiles), sanitizer/native/visual tests, locked
  gateway pytest and tools/m2/generate_protocol.py --check. Backend uses a separate
  venv, never SDK pip. CI tests are not physical Wi-Fi/TLS/sleep/current evidence.
- Require verified CA, hostname AND certificate dates (MBEDTLS_HAVE_TIME_DATE=y).
  Never permit TLS bypass or redirects with a device bearer. Explicit lab CA only.
- Provision secrets at runtime through physical trusted USB. No secrets in code,
  Kconfig, argv, fixtures, logs, commits or CI. Private configs/keys outside Git,
  mode0600; NVS remains plaintext and outside physical extraction protection.
- External RTC2056 is not trusted. A fresh UTC seed comes from the trusted host;
  only valid deep-sleep RTC continuity preserves the lease. Fail closed after
  unexpected reset/lease expiry; no old NVS timestamp as now, no insecure SNTP.
- Show all gateway data as simulated. A failed query/expired snapshot is OFFLINE,
  never a current historical CRITICAL/HEALTHY. Persist only last validated data.
- Bounded retries and explicit Wi-Fi shutdown precede sleep. No continuous refresh
  loops. Keep exact-frame cancellation across trusted RTC continuation.
- On 2026-10-17 the user authorized starting the first M2 physical trial after
  approving an application-only load and one trusted USB provisioning. This covers
  only app SHA0553e5bb at0x10000 and the current private lab/fresh UTC, interval900s.
  The one write and IBPROV_OK completed; M2 remains installed. The first screen
  showed HTTP/OFFLINE; no physical PASS. See docs/M2-PHYSICAL-RESULTS.md.
  Never run hardware as part of builds/tests; no automatic retry or restoration.
- No production collectors, MQTT, database, eFuses or irreversible security changes.

## M2 physical phase A

- Current request permits host build, private lab TLS/credentials and an authorized
  external client on the same Wi-Fi when requested. The user later explicitly
  chose only the current notebook and omitted the external check. The phase
  explicitly forbids flash and USB provisioning. Do not open the board port
  during this preparation.
- The phase A/first installed firmware matched CI9c5ef57. Subsequent local logging
  corrections have a new build identity and are not covered by that CI approval.
  Do not change firmware to hide a lab problem. Preserve approved M1.1 artifacts/backup.
- Keep private directory and phone-client.zip outside Git; the client has a
  separate token and must never receive device.json, Wi-Fi password or server key.
- Host .local NSS currently selects Tailscale; route diagnostics retain full
  TLS verification and do not prove external DNS. Require normal DNS from the external client
  and an authenticated external report to claim external validation. The current
  local-only closeout records its omission, never an external PASS. No global DNS changes.
- See docs/M2-PHASE-A.md for NVS retention, monitor effects, OTA and acceptance.
  Stop and request new explicit authorization before any firmware write or
  provisioning; an external-client PASS never means physical M2 validation.

## M2 first physical trial

- The subsequent user instruction "iniciemos el ensayo fisico" authorizes the
  prepared one app load and one provisioning described above; do not ask again.
- Use tools/m2/physical_first.py --authorized-m2-first from a normal host terminal,
  never sudo. It enters the existing iot-dev and preserves bootloader/table/NVS.
- The initial trial records the first query/display and requested sleep. It does
  not certify the following timer wake, ETag304, battery operation or consumption.
- Preserve private backup/rollback. Keep raw flash logs ignored/private and never
  record provisioning TX. Export only allowlisted serial events, no identifiers.
- If a write was attempted, stop rather than running the load again. A diagnostic
  result requires inspecting evidence and resuming with the installed firmware.
- The first trial completed the write/provisioning and collected HTTP/OFFLINE.
  INFO messages were compiled out at maximum WARN; do not infer reset/wake from
  their absence. Compile/test the logging correction without hardware; another
  load/provision requires a new explicit authorization on the new binary.
- Diagnostic app SHA733f7b9b (863152 B) passed six-profile local builds and the
  compiled-event checks; it is frozen under the new supervisor result. The user
  explicitly authorized one load/provision; both completed in the second trial,
  m2-physical-diagnostic-20261018T014635Z-y7ofz23s. That authorization is consumed.
  The board retains this diagnostic image. See docs/M2-DIAGNOSTIC-TRIAL.md.
- physical_diagnostic.py prepares a separate single attempt, preserves NVS and
  guides one manual BOOT setup wake after CLOCK if needed. A setup wake is not
  physical timer validation. Never invoke its authorized flag before new consent.
- Second trial: Wi-Fi phase completed, TRANSFER timed out at5.18s with status0
  and no TLS error recorded; no HTTP request reached the gateway. This is not TLS
  validation or a certificate diagnosis. Setup boot reset11/wake0 is USB reset,
  not deep-sleep return. Do not reopen serial to observe a timer without reviewing
  this measured reset effect; fresh provisioning succeeded after the setup reset.
- Next diagnostic is observe_network.py on the host:120s, no USB/firmware/NVS.
  Start as normal user; only its filtered AF_PACKET reader needs sudo. No install,
  promiscuous mode, raw packet files, identifiers or payload exports. Parse target
  mDNS and gateway TCP metadata only; keep unrelated traffic out of results.
- Network capture saw incoming mDNS queries and TCP SYNs to the gateway. Its old
  ETH_P_IP socket did not support outgoing conclusions; corrected ETH_P_ALL plus
  IPv4 cBPF filtering preserves privacy. FIB independently selects tailscale0 for
  gateway TCP replies to Wi-Fi LAN despite a connected main-table route.
- try_local_route.py --plan verified a proposed priority5100 rule: source gateway
  LAN/32, destination connected Wi-Fi subnet, TCP sport8443 only, lookup main.
  The user explicitly authorized this120s temporary rule/capture trial with
  "si autorizo"; it completed in m2-route-check-20261018T025235Z-d_tzltp8.
  No VPN/persistent changes or firmware. Exact rule cleanup was confirmed in
  results and independently by checking priority5100 is absent.
  Privileged child owns bounded capture and exact-selector cleanup. See
  docs/M2-ROUTING-DIAGNOSIS.md; reject stale USB seed before starting the test.
- The last diagnostic UTC seed no longer leaves room for the120s trial. The
  route authorization did not itself authorize another provisioning.
  The user subsequently said "continua por favor" in direct response to the
  concrete request for ONE USB reprovisioning of the same private config/fresh
  UTC (clears stored snapshot), then the authorized route trial. This renewal
  completed with ACK in m2-utc-renew-20261018T025223Z-8o4xvbnm; consent is consumed.
  No firmware load/reset command or automatic retry. A recorded TX attempt blocks
  another invocation even without an ACK; inspect results before any further write.
- The route trial recorded mDNS with expected LAN answer, bidirectional TCP/data
  and one authenticated HTTP200, conditional_request=false, external_unattributed.
  The operator answered "si" to display HEALTHY/SIM/HORA VERIFICADA/VENCE and no
  other token clients during the trial. First HTTPS200/display transaction is
  functionally confirmed. Do not infer timer,304, battery/current, full M2 PASS
  or install a permanent route; the temporary exception has been removed.
- Prepared observe_next_cycle.py/docs/M2-NEXT-CYCLE.md for a separate maximum
  20min host return-rule window. The user explicitly authorized this window:
  "Sí, autorizar la ventana temporal de 20 minutos". It completed in
  m2-next-cycle-20261018T025959Z-rl4mialg; this one-window consent is consumed.
  No USB/provisioning/firmware performed. Exact cleanup and independent absence
  of priority5100 confirmed. Gateway recorded conditional304 then unconditional200;
  operator confirmed no intervention/other clients and visible refresh around20min.
  Autonomous conditional304 query is functionally confirmed; refresh is not tied
  to the304 and does not establish frame cancellation. Both route trials ended.
  Conditional304 plus operator exclusivity supports an autonomous query; without
  reset/wake metadata do not declare timer cause or frame cancellation validated.
- Prepared scenario_session.py/docs/M2-SCENARIOS.md: one NEW maximum10min route
  window, temporary same-cert gateway with in-memory scenarios, seven manual
  BOOT wakes/screens including503/recovery. User explicitly said "autorizo,
  continua por favor.. hazlo lo mas autonomo posible"; this prepared session is
  complete in m2-scenarios-20261018T033315Z-yumfm07o. Seven screens and no other
  token clients confirmed, statuses200/200/200/200/200/503/304. No new
  flash/provision/interval changes or raw capture. Current session cannot sudo
  due no-new-privs, so launch from the user's normal terminal.
  The helper now restores the original saved gateway automatically after the
  temporary instance stops, to reduce user work. The first start failed with
  EADDRINUSE before result/rule creation: the old gateway was still running in
  this chat's managed exec45261. It was stopped gracefully through that session
  and8443 was verified free. The subsequent successful window consumed consent.
  Script now explains an occupied port explicitly; no arbitrary process control
  or private config edits. Restore keeps the terminal running as before.
  Prior120s/20min windows are consumed. Recovery may be304 on a still-valid cache.
- Scenario closeout independently confirmed priority5100 absent, original gateway
  TLS1.2 with exact saved certificate/CA/SAN/date, HEALTHY/no faults, device
  interval900 and frozen firmware/rollback intact. Extra304 sequence4 between
  selected stages is recorded without assigning a wake cause. No open permission
  for another route window/provision/load; physical TLS negatives, exact wake,
  frame cancellation, battery/current and other documented cases remain pending.
- User asked how to automate full M2, then explicitly said "Deja las mediciones
  pendientes". Power/current/battery measurements are DEFERRED, never passed.
  docs/M2-AUTOMATION.md and docs/M2-AUTO-DIAGNOSTIC.md now describe an implemented,
  separately compiled journal profile and bounded host runner. Seven profiles and
  native sanitizers passed in m2-auto-supervised-20261018T042715Z-9wpefanz; Python
  software tests pass separately. New app SHA d4e7b93c (879840 B) was subsequently loaded; see interrupted trial below.
  Preserve normal ib_m2 NVS; diagnostic config/journal use ib_m2_auto. Require a
  concrete new manifest approval for one app write/setup/export and a maximum50min
  scoped TCP8443-8474 return-route window. Old consents are consumed. The runner
  leaves the diagnostic installed, restores only the host gateway and removes the
  exact route. Full M2, optical verification, reset/UTC loss and consumption remain
  outside an automated PASS. Do not execute the physical runner before consent.

- The user subsequently explicitly authorized "Autorizo cargar y ejecutar" for
  the prepared M2 autonomous manifest: app d4e7b93c (879840 B,0x10000), one
  diagnostic setup/final export and the maximum50min TCP8443-8474 return rule.
  Consent is now granted; do not ask again for the same bounded run. As of the
  preflight no write/setup/route was attempted: sudo needs host authentication
  and zero303a:1001 USB candidates were visible. The unchanged sealed package is
  staged privately in the normal lab home. Require the user's normal terminal
  for sudo, with the one connected/woken board, then inspect execution records
  before doing anything else. Existing no-retry guards still apply.

- Autonomous trial m2-auto-physical-20261018T140230Z-m0k3p41s completed the ONE
  approved app write/setup, got HTTPS200 slot0, then the user reported accidental
  USB disconnect and interrupted the host. Exact rule removal/test gateway stop
  confirmed; priority5100 independently absent. Second execute was blocked before
  new hardware actions. Keep run INCOMPLETE, no timer/whole-group PASS inferred.
  Installed app is d4e7b93c; preserve execution marker and original journal.
  The authorized final read-only export completed: valid CRC/run, INVALID/RESULT,
  count2/timer_returns1; case0 HTTP200,case1 reset8/wake4 HTTP/status0. This confirms
  one actual timer return, not the complete group or identical-frame suppression.
  No further setup/route/load is authorized by this interruption.
  Prefer a separately approved setup-only retry using the installed app.

- Prepared a separate setup_existing manifest after preserving the terminal
  journal:0 app writes,1 USB HardReset,1 diagnostic setup with fresh UTC,1 final
  export and maximum50min scoped return rule. auto_sdk must never call flash in
  this mode and must reject a different installed journal run. New plan requires
  explicit approval; do not delete original execution markers or overwrite its
  private evidence. No firmware source or binary changed for host-only recovery.

- The user now explicitly authorizes all necessary work to finish M2, including
  the prepared setup-only retry and bounded follow-up diagnostics/fixes. This
  supersedes earlier per-run requests for new approval: do not ask the user again
  for each necessary reversible M2 step. Preserve previous evidence and use new
  bounded manifests/attempt records instead of deleting consumed guards. Current
  restart manifest m2-auto-restart-20261018T140828Z is approved, not executed yet.
  No irreversible operations, whole-flash erase, eFuse/security changes, factory
  backup replacement or automatic merges. Measurements stay DEFERRED. Passwords
  must be entered locally; the host sudo prompt is a practical execution need,
  not missing consent. Prefer the installed diagnostic and avoid another flash.
