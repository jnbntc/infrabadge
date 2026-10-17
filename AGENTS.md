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

## M1 UI

- Work on feat/m1-ui; M0 physical baseline is local commit 910bf9f.
- Keep M0 main/HAL/panel protocol unchanged unless a demonstrated fix is necessary.
- M1 is offline and uses simulated infrastructure AND device diagnostics.
- Do not trust the advancing RTC as wall time; always show unsynchronized state.
- UI model/render/input and display caching are portable C. Power stays separate.
- Only full refreshes through the M0 epaper driver; no assumed partial update support.
- Run tools/build-m1.sh --all, native tests and tools/simulate_ui.py --check.
- Review the 12 visual references before deliberate --update changes.
- M1 firmware has no physical validation or flashing authorization yet.
- docs/M1-PHYSICAL.md contains the future manual procedure; never run it as build.
