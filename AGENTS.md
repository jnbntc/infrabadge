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
- M1 and M1.1 are published together on feat/m1-ui. PR #1 was merged externally
  during consolidation at 17:40:59 Argentina time, with M1 head 62b0556 only;
  M1.1 is not in that merge. The user authorized publication, not another merge
  or any device operation. The user chose complementary evidence in #1 and changes
  left on the branch; do not open a continuation PR without a new request.
- docs/M1-M11-VALIDATION.md is the consolidated evidence/limitations index; older
  milestone reports and build manifests keep their original validation scope.

## M1 UI

- Work on feat/m1-ui; M0 physical baseline is local commit 910bf9f.
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
