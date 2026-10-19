# InfraBadge development instructions

## Current M3 scope (supersedes historical M2-only restrictions below)

- Main includes merged M1.1 #2 and M2 #3. Work M3 on
  feat/m3-fedora-monitoring, branched from updated main19a9a00.
- Implement only the authorized Fedora host collector and FastAPI integration,
  preserving the M2 endpoint/schema and separate collector/device credentials.
  No MQTT, unrelated collectors, database or distrobox-stack changes.
- Do not install/enable user services, change real host networking/configuration,
  enable linger, provision, reset or flash the board. Host read-only metrics and
  temporary localhost HTTPS software tests are allowed. Draft PR only; no merge.
- The physical board remains the frozen M2 diagnostic. M3 REAL support is a
  separately committed minimal parser/source/render update, not physically loaded.
  Preserve M0/M1, HAL, Power Manager, TLS and framebuffer diff.
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
