# Current PR consolidation (2026-10-23)

- User explicitly authorizes ready/merge of technically prepared PR8, then PR9,
  then scoped PR7, respecting main protections. Preserve branches/backups and
  traceability; this supersedes historical no-merge instructions below.
- PR8 integrated as c24b0dc, post-merge CI passed. PR9 retargeted to main;
  its branch merges that base without rewriting history. Verify exact-HEAD CI.
- After integration prepare permanent-edge software/artifacts only. No real
  services/SSH administration, firewall/DNS/routes/Grants, credentials, firmware,
  NVS, suspend/roaming tests or host restarts without concrete new approval.
- M3.3 D/E/F are historical real evidence; G/H/I remain future operational tests.

# Historical M3.6 implementation before consolidation (2026-10-23)

- Work feat/m3.6-multisite-roaming, stacked on unmerged PR8/a4d6c05.
  Draft PR base feat/m3.5-esp32-preparation; never merge or change PR7.
- New ninth profile only: mobile_policy and CONFIG_IB_M36_ROAMING, two fixed
  SSIDs/HTTPS bindings, no CA/auth fallback. Separate ib_m36 bundle; never open
  ib_m2 or migrate/erase its keys from new provisioning code.
- Night is opt-in,00–08 Buenos Aires UTC-3; keep legacy3600s clock lease and
  <=3600s Power Manager timer. A bounded fixed-deadline retained permit checks
  ESP continuity against read-only PCF relative advance (2056 is NOT UTC).
  No radio/render on valid night wakes; morning invalidates cache then verifies
  TLS/server time before fresh data. Invalid clock/RTC cancels long-sleep trust.
- Tests/mock TLS listeners are loopback only; no real services, USB/NVS/flash,
  PKI/credentials, LAN listeners, SSH/network/Grants changes or physical tests.
- tools/build-m36.sh --all: nine profiles plus native app/policy ASan/UBSan,
  night PNG and previous visual regressions. Root pytest.ini and Ruff remain.

# Current closeout / M3.6 scope (2026-10-23)

- User requests M3.5 stale-recovery fix/review on PR8, then independent M3.6
  branch/draft PR with bounded roaming and configurable night sleep.
- No board/USB access, provision/flash, real services/listeners/network/PKI,
  SSH/deployments or merges. Prior deployment permissions are not reused.
- Preserve legacy ib_m2 NVS layout/config; future new settings use a separate
  namespace and explicit provisioning. PCF85063 date2056 is not trusted UTC.
- Night settings must not enter PR8; keep M3.6 dependency on unmerged PR8 explicit.
- Do not repeat completed physical tests; electrical/audio/mic remain deferred.

# Current M3.5 deployment pilot (2026-10-23)

- The user subsequently authorized deployment. Core M3.5 and a rootless Fedora
  edge are deployed; Fedora uses only the selected wired LAN, with Wi-Fi
  disconnected but its profile retained. Preserve Core collectors, SQLite,
  unrelated network/firewall/VPN settings and M3.3/PR7.
- Installed app:885376B at0x10000, SHA902645be8f1d5f7ce3049f8620edee42c19108b832bb5fb0179a6204506cf1d3.
  One application write; bootloader/table/factory backup unchanged. Do not reuse
  consumed plans. Later host/docs commits do not identify a different installed app.
- Initial provision timeout20000ms was rejected by the firmware parser. Corrected
  config15000ms was accepted. A subsequent UTC renewal had explicit separate
  authorization after auto-review blocked it; that renewal is now consumed.
  No automatic reset/provision/flash retry; preserve all partial evidence.
- Device HTTPS200, a second query75s later without reopening serial (USB connected), real summary/clock and
  navigation and return to live WARNING after expiry were observed. A host check
  identified a RAM alert with three fresh nodes; no threshold changes. Consult
  docs/M3.5-PHYSICAL-RESULTS.md for remaining optical/negative-test limits. No all-hardware, electrical or battery PASS.
- Host provisioning now rejects numeric limits before opening serial. Preserve
  TLS/name/date checks and trusted USB UTC/checked RTC continuity; USB observation
  captured reset11/CLOCK and must not be counted as a timer8/wake4 return.
- The edge guard owns only its narrow8443 rules/return rule. Fail closed on approved
  address/profile/interface changes; never broaden it or change DHCP/DNS to avoid
  a failure. Physical credentials, board identifiers and raw logs stay outside Git.
- Publish this branch and draft PR8 only; never merge or modify historical branches.

# Current scope: functional M3.5 implementation (2026-10-23)

- User explicitly requests functional firmware, v2 presentation API, adapted edge,
  tests/eight SDK profiles and draft PR on feat/m3.5-esp32-preparation.
- Supersedes preparation-only source/build restrictions below. Preserve v1,
  HAL/power/e-paper/clock/TLS invariants. No audio/mic/touch/OTA in this phase.
- Use synthetic scoped fixtures; temporary loopback TLS test servers are tests,
  not deployment. No real board, NVS, services, host network or Core/NAS changes.
- Publish this branch and draft PR, never merge or modify M3.3/PR7.
- Functional v2 is /api/v2/devices/{id}/status, opt-in on device and edge;
  max3 sites/6 nodes/4 alerts/4096B. v1 remains separate. Source model/C/fixtures
  must agree. SDK source SHA pinned; use tools/build-m35.sh --all.
- M3.5 retains snapshot/view/framebuffer only across checked deep sleep. Cold
  boot offers a 10s explicit IBPROV1 host window; no BOOT provision gesture.
  Do not send any provision transaction or access real USB in software tests.
- No real PKI/credentials, LAN deployment, flashing or provision without their
  specific future authorization. Existing USB/rollback preflight is complete.

# Historical M3.5 follow-up: authorized connection/rollback preflight completed (2026-10-23)

- Operator said "autorizo todo, procede" after the concrete preflight proposal.
  Do not request the same connection/rollback inspection permission again.
- One 303a:1001 USB/ttyACM was observed, R/W without sudo; alias absent but existing
  detector has real-port fallback. Metadata only: NO serial open/readback/reset/
  provision/NVS/flash. Operator later confirmed short BOOT; do not infer wake cause.
- Factory 8 MiB hash, historical normal M3 app 9311046b/863472 B, table MD5/compatibility
  and build security settings verified. Factory remains private behind 0700 parent.
  New inert app rollback packet outside Git; old consumed plans never reused.
- Application slot 0x10000/1 MiB leaves 185104 B. Candidate M3.5 firmware is NOT built;
  Python prototype is not flashable. Verify actual binary/plan before any write.
- Collector timer active; old M3 localhost gateway still failed/protocol, untouched.
  A stored firmware rollback does not prove HTTPS delivery rollback functional.
- See docs/M3.5-PREFLIGHT-RESULTS.md. New peripheral/edge-LAN/menu validation remains
  pending. No host services/network/udev, Core/NAS, firmware or credential changes.

# Historical scope: M3.5 preparation and peripheral audit (2026-10-23)

- Work feat/m3.5-esp32-preparation from main da4a3ff; no M3.3 commits or PR7 edits.
- User confirmed non-touch Waveshare ESP32-S3-ePaper-1.54 V2/N8R8. No touch
  research, controller/dependency, GPIO allocation or new peripheral drivers.
- Preparation only: schematic/firmware audit, offline synthetic UI fixtures,
  proposed ESP32-edge-core/TLS and independent physical test/rollback plans.
- Preserve components/, main/, SDK/CMake, v1 wire, HAL/power/framebuffer diff.
  Prototype Python uses M1 font/PNG codec but is NOT production C or firmware.
- No USB/serial, flash/NVS/eFuses/provision, listeners, services, host network,
  firewall/Tailscale/DNS changes, SSH or credentials/PKI generation. No merge.
- Current v1 is aggregate+two alerts, not per-site/node inventory. New rich
  display API/decoder requires separate version/security review and commits.
- Audio rail42 enables shared ES8311/I2C; amplifier control46 is separate and
  not initialized in current HAL. Do not optimize away validated I2C sequencing.
- PWR retains electrical/wake role. BOOT navigation is a host-only proposal;
  startup provisioning/strapping conflict must be resolved before firmware.
- docs/M3.5-PREPARATION.md indexes evidence and pending permissions. Energy,
  work-site onboarding and physical peripheral validation remain pending.

# Current M3.2 integration consolidation (2026-10-22)

- The user requests audit/consolidation of PR6, not new monitoring features.
- Existing private pilot reports are evidence: native ARM64 systemd core plus local
  and remote collectors, application b2ae0de; socket/credential adaptations were
  deployed separately. Version only generic inert copies, no private inventory.
- No host access is needed for this consolidation: review existing evidence;
  never restart, install, reprovision, change network or update deployed services.
- Preserve root/0440 credential rejection; stage owned0600 per oneshot as in pilot.
  MemoryMax is ineffective without memory controller; LimitAS is NOT a RAM cap.
- Historical collector failure has generic code only. Early timer/min-interval is
  a supported hypothesis, not proven429 or a solved cause. Test timing semantics.
- External backup, spare card, DR and long stability remain operator-deferred;
  do not turn them into new gates for the validated pilot or software integration.
- Update PR6 with exact-HEAD CI, may mark Ready after checks/review; merge requires
  explicit new user authorization. Prepare PR5 closure comment only; no posting,
  closure, merge or branch deletion without authorization. Roadmap only M3.3–M3.5.

# Current M3.2 scope (supersedes historical branch and database restrictions)

- User explicitly requested feat/m3.2-distributed-core from updated main df11e98.
  PR #5 remains draft at9fbe3b0; do not modify, merge or duplicate its history.
- Implement distributed core, SQLite versioned persistence, scoped identities,
  local HTTPS edge, Linux collectors and inert ARM64/rootless deployment artifacts.
- Reuse M3 metrics/health and M2 wire contract. No firmware changes unless proven
  essential. No SSH, real service installation, network/Tailscale/firewall/DNS/NM
  changes, board writes, secrets or private inventory publication. Draft PR only.
- Real requested inventory must stay outside Git. Use explicitly synthetic test
  fixtures; work nodes disabled until organizational approval. No invented IPs.
- Validate SQLite migration/recovery/replay/expiry, multisite isolation, HTTPS and
  ARM64 build in CI. Keep physical/deployment/energy evidence separate.

# InfraBadge development instructions

## Current M3 scope (supersedes historical M2-only restrictions below)

- Main includes merged M1.1 #2 and M2 #3. Work M3 on
  feat/m3-fedora-monitoring, branched from updated main19a9a00.
- Implement only the authorized Fedora host collector and FastAPI integration,
  preserving the M2 endpoint/schema and separate collector/device credentials.
  No MQTT, unrelated collectors, database or distrobox-stack changes.
- The user explicitly authorized installation/activation of the M3 collector
  timer and rootless gateway on2026-10-19, HTTPS bound to localhost:8443 only.
  New private M3 configuration/certificates and bounded stop/recovery tests of
  these new services are authorized. Preserve original M2 files/backups.
- On2026-10-19 the user resumed and explicitly authorized the concrete M3
  physical plan: one863472B app-only load at0x10000 (SHA9311046b, full hash in
  M3-PHYSICAL), private provisioning with new M3 CA/fresh trusted UTC, and a
  temporary selected Wi-Fi IPv4 gateway listener. The matching private plan is
  referenced by results/m3-physical-plan-active.json; never retry a consumed plan.
- The only authorized routing exception is priority5100, exact gatewayLAN/32
  to its connected Wi-Fi subnet, TCP source8443, lookup main, maximum20min with
  exact cleanup. Restore the original loopback Quadlet after the trial; independent
  user watchdog bounds LAN publication. No persistent network/VLAN/VPN/DNS/firewall
  changes or linger. The user authorized the closing audit and marking PR #4 Ready after a
  satisfactory review. Merge still needs a new explicit authorization. Only after
  that merge may feat/m3.1-lan-deployment start. Do not change the installed board,
  gateway or host configuration during this audit. Real suspend/logout remains
  unauthorized.
- The authorized run m3-physical-20261019T212131Z loaded the normal M3 app
  SHA9311046b, provisioned once and observed physical HTTPS200 plus a live/clocked
  draw callback and OK cycle. No restoration was performed: M3 is installed.
  The operator explicitly confirmed the real metrics/clock/expiry on screen.
  The USB observer stopped with SerialException; a new M3 timer return remains
  unconfirmed. Do not turn this partial capture into a full physical-suite PASS.
  Exact route removal, loopback-only gateway and active collector were verified.
  See docs/m3-physical-results.json. No extra write/retry is authorized by the
  consumed plan; retain its execution marker and private results.
  Preserve M0/M1, HAL, Power Manager, TLS and framebuffer diff.
- Follow-up lab tools are opt-in: tools/m3/{prepare_observer,check_observer,
  observe_gateway,provision_session,physical_session}.py and docs/M3-LAB.md.
  Localhost observer verified,199 Python tests passed. The separately approved
  no-flash session224036Z stopped before any TX (SerialException); cleanup passed.
  See docs/m3-observation-attempt.json. Its linked continuation224512Z completed
  one TX/ACK, autonomous real polling, stale UNKNOWN and fresh recovery. Operator
  confirmed the corresponding screens with no intervention. Both approvals/
  markers are now consumed: no further provision or reuse. Preserve both records.
  See docs/m3-observation-results.json. Independent cleanup passed.
  A zero-TX continuation must verify no TX/ACK and unchanged scope; never
  continue an uncertain TX automatically.
  The user approved one UTC provisioning and bounded
  LAN/route/collector pause; no firmware write path exists. Do not reuse the old
  execution marker. Keep USB closed during autonomous observations. Gateway
  request metadata cannot establish exact reset8/wake4 or electrical sleep.

- Collector runs on the host with stdlib only; never claim container proc/sys/mounts
  are host metrics. No identifiers/private data in public fixtures/reports.
- M3 docs: M3-ARCHITECTURE, M3-VALIDATION, M3-FEDORA-SETUP and M3-PHYSICAL.
  Run root pytest.ini (collector+gateway+TLS integration), pinned Ruff via
  tools/m3/check_style.sh, protocol/M3 fixture checks and all seven SDK profiles.
- Preserve the distinction between deterministic fixtures, real Fedora localhost
  checks, rootless container smoke, installed user timer, LAN and physical ESP32.
  Do not substitute CI/host tests for the latter stages. Energy remains deferred.

## Scope and safety

- Work only in `jnbntc/infrabadge`; confirm Git root/origin before edits.
  `distrobox-stack` manages environments and stays outside this firmware repo.
- Target Waveshare ESP32-S3-ePaper-1.54 V2, ESP-IDF5.5.5 locked at
  b774170ff46c393eeb5e495ea37936038d3f4f4f. Read docs/HARDWARE.md and
  docs/upstream.json before assigning GPIOs. Preserve licenses/dependency locks.
- Separate HAL, device protocols, rendering, application and Power Manager.
  Reuse validated M0 drivers. Full panel refresh only; no assumed partial update.
- Never run erase_flash, whole-flash restoration, eFuse writes, Secure Boot or
  Flash Encryption changes. Preserve the private factory backup and M1.1 rollback.
- Secrets/configs/keys, board identifiers and raw USB/flash logs stay outside
  Git/CI. Private folders0700/files0600; export allowlisted summaries only.
  NVS is plaintext, not protection against physical extraction.
- Builds/tests must never open USB, provision or flash. Keep CI, simulation,
  driver callback counters, optical observations and electrical measurements distinct.
- Do not merge, rewrite/delete historical branches or replace backups automatically.
  Do not add MQTT, databases or unrelated platform changes.

## Historical M2 branches and evidence

- Work M2 on feat/m2-connectivity, based on M1.1 b2dcf7a. PR #2 proposes
  feat/m1.1-integration into main; PR #3 targets that integration branch.
  Preserve feat/m1-ui and historical M1/M1.1 commits. No automatic merges.
- M0 physically validated. M1 UI/button/sleep validation over USB and M1.1 three
  timer wakes solely on battery are recorded in docs/M1-M11-VALIDATION.md and
  docs/POWER-BASELINE.md. Those results do not imply M2 electrical measurements.
- Current installed app is corrected autonomous diagnostic SHA10037379 (879920B at0x10000).
  Exact identity: docs/m2-tlsfix-build-manifest.json. The image is frozen locally;
  CI rebuild metadata/hashes need not equal that physical binary.
- docs/M2-PHYSICAL-RESULTS.md is the physical evidence index. Other trial reports
  retain their original scopes. Software/CI: docs/M2-VALIDATION.md. Never convert
  a historical partial result to PASS based only on later fixtures.

## Build and tests

- Use the existing rootless iot-dev launcher; no host SDK installations.
  Gateway uses its separately locked venv, never SDK pip.
- `tools/build-m2-auto.sh --all` builds all7 profiles: M0 display/sensors/sleep,
  M1 UI, M1.1 timer, M2 connectivity and autonomous diagnostic. Run native C,
  ASan/UBSan, visual references and protocol checks; verify ELF/config/security.
- `tools/m2/host_checks.py` executes protocol/Python tests without hardware.
  Its legacy --build option still covers6 profiles. build_auto_watch.py freezes
  seven-profile outputs and source hashes; use that pack for diagnostic execution.
- CI uses the pinned image, no network/devices during firmware build, and a
  separate gateway job. Never upload private results directories as CI artifacts.
- M0/M1 remain offline. Wi-Fi links only in the M2 profiles. M1 UI has12 visual
  references, timer6 and M2 connectivity6; inspect before deliberate updates.

## Connectivity and clock rules

- STA plus verified CA, hostname and certificate dates; MBEDTLS_HAVE_TIME_DATE=y.
  No TLS bypass, redirects carrying bearer, insecure time bootstrap or RTC2056.
- Runtime provisioning through trusted physical USB, never secrets in argv/code/
  Kconfig/logs. A fresh synchronized host UTC seed starts trust. Only valid
  deep-sleep RTC continuity preserves it; no NVS timestamp as now after reset.
- M2 mock health is simulated; M3-bound devices use explicit REAL data/UNKNOWN.
  Invalid/expired query is OFFLINE with historical
  labels, not a current old HEALTHY/CRITICAL. Respect version/ranges/TTL/identity.
- Bounded timeouts/backoff, explicit Wi-Fi stop before sleep, conditional render
  and framebuffer cancellation. Do not infer radio current from stop callbacks.
- Diagnostic uses NVS ib_m2_auto; preserve normal ib_m2 config/snapshot. Journal
  CRC/run/armed sleep and reset8/wake4 are required for timer returns. Unexpected
  reset/RTC loss invalidates the group. USB monitoring can reset the MCU.
- Diagnostic fixtures have3600s TTL so the >30min group does not hit a legitimate
  shortened sleep near expiry. Normal gateway default remains1800s. Expired-data
  negative remains expired; do not change firmware TTL guards, clock lease or TLS.

## Authorization and current physical run

- The user explicitly authorized all necessary work to finish M2, including
  bounded follow-up resets/provisioning/routing, fixes and repository/PR updates.
  Do not ask again for each necessary reversible M2 step. This supersedes earlier
  per-run approval requests; preserve their consumed markers/evidence nonetheless.
- Prefer setup-only runs on the installed diagnostic, not another flash. Review
  a concrete manifest before any needed write; never retry an uncertain write
  automatically or delete execution.json to bypass guards. Each new attempt gets
  separate scope, record and private artifacts. No irreversible operations/merges.
- The narrow host return rule is temporary: priority5100, exact gatewayLAN/32 to
  connected Wi-Fi subnet, TCP source8443–8474, main table, max50min with watchdog
  and exact-selector cleanup. No persistent VPN/DNS/firewall changes. Passwords
  are entered locally; inability to sudo is an execution limitation, not consent.
- The first run m2-auto-physical-20261018T140230Z-m0k3p41s was interrupted after
  accidental USB disconnect/Ctrl+C. Journal:2 records, one reset8/wake4 return,
  next query HTTP/status0. Cleanup confirmed; incomplete, not complete-group PASS.
- The second m2-auto-physical-20261018T141551Z-yygtf_rx was stopped proactively
  for the lab TTL correction. Seven recorded cases accepted, including304 with
  UNCHANGED/zero transfers, states and503. Final INVALID/WAKE after interruption/
  USB read; no25-wake PASS. Cleanup confirmed and journal preserved.
- TTL-corrected run m2-auto-physical-20261018T142731Z-c7m7ih7r stopped at case8:401
  was classified HTTP instead ofAUTH. Nine events/eight timer returns; no group PASS.
  Exact cleanup and export confirmed. Its app was still d4e7b93c.
  Read progress.json/gateway-events.json without USB; they are host progress, not
  final case acceptance. Do not open serial or touch buttons during the group.
  Read the terminal journal only after notification, then verify CRC/run,26 cases,
  25 real timer returns, expected errors, clock/display and route/server cleanup.
- The runner leaves the diagnostic installed and restores only the host gateway.
  Any retry/follow-up must preserve prior results, and respect the user's
  current broad M2 authorization without requesting duplicate confirmations.
- The user explicitly deferred consumption/energy/battery/autonomy measurements.
  Mark DEFERRED, never PASS or estimate from400mAh. External phone/client test was
  explicitly omitted; do not request it again or infer it from loopback testing.

- Fixed the401 NOT_SUPPORTED adapter path with error precedence preserved; new
  image93277e2e (879920B) compiled/verified in7 profiles. Full-adapter native test
  with simulated IDF transport fails on old source and passes on fixed source with
  ASan/UBSan. See docs/m2-authfix-build-manifest.json; no new GPIO/driver changes.
  User broad M2 consent authorizes the needed one app-only corrected load/setup
  and bounded50min trial. Private plan m2-auto-authfix-20261018 is prepared.
  It was subsequently loaded/provisioned successfully in
  m2-auto-physical-20261018T144846Z-oi1a2ccu, now INVALID at case16.
  Journal recovered in m2-auto-journal-recovery-uxvszpyl:17 records,16 accepted,
  16 timers, cleanup confirmed. Preserve it.

## TLS propagation correction validated

- IDF5.5.5 async connect omits copying TLS errors to transport; sync copies them.
  HTTPS now uses sync mode with the same CA/SAN/date and timeout/deadline guard.
- New10037379/879920B passed7 builds, ASan/UBSan and85 Python tests, and is installed.
  Manifest docs/m2-tlsfix-build-manifest.json; final physical result accepted26/25.
- Broad M2 authorization covers the necessary corrected load/setup/bounded trial;
  sudo password must be entered in the normal user terminal, not in chat.
- Collector waits passively up to15s for terminal USB readiness before export.
  No reset/write retry added. Historical partial results remain partial; the
  completed10037379 run below is the accepted26/25 group.

## M2 functional closeout

- m2-auto-physical-20261018T154427Z-173109xf:COMPLETE/fault0,26 accepted cases,
  25 reset8/wake4 returns, CRC/run and independent exact-route cleanup verified.
  docs/M2-CLOSEOUT.md and docs/m2-autonomous-results.json are the current index.
- CIeae50f9 passed push39140175608 and PR39140172101. Final documentation does
  not change the frozen app identity. Historical partial attempts stay partial.
- Board remains10037379 terminal; no normal-M2/factory restoration. Consumption,
  energy/battery/autonomy deferred, externalclient omitted, optical per-cycle,
  physical cold-reset/NVS cuts and production/OTA exclusions remain.
