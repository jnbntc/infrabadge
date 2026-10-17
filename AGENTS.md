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
- M2 has no hardware authorization. The board retains the physically validated
  terminal M1.1 diagnostic. Never run provisioning/flash/monitor hardware as part
  of builds or tests. Follow docs/M2-PHYSICAL.md only after new authorization.
- No production collectors, MQTT, database, eFuses or irreversible security changes.
