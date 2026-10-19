# M3 — Fedora Atomic setup (explicit operator activation)

Development/build/test commands do not install units or flash the board. The
operator subsequently authorized the local M3 user services on2026-10-19;
the installed deployment and its limits are tracked in M3-VALIDATION.md.
The following procedure remains opt-in for other installations, run as the normal
user, never sudo. Commands assume a checkout at `~/Proyectos/infrabadge`.

## Software validation without installation

```sh
cd ~/Proyectos/infrabadge
python3 -m venv /tmp/infrabadge-m3-check
/tmp/infrabadge-m3-check/bin/python -m pip install --require-hashes -r gateway/requirements.lock
/tmp/infrabadge-m3-check/bin/python -m pip install --require-hashes -r tools/m3/style.lock
/tmp/infrabadge-m3-check/bin/python -m pytest -c pytest.ini
PATH="/tmp/infrabadge-m3-check/bin:$PATH" bash tools/m3/check_style.sh
/tmp/infrabadge-m3-check/bin/python tools/m3/generate_fixtures.py --check
/tmp/infrabadge-m3-check/bin/python tools/m3/check_host.py
```

The last command reads two real host samples one second apart, creates a private
temporary CA/tokens and localhost HTTPS server, sends metrics, verifies M2 JSON,
304 and credential separation, then closes/deletes its own temporary lab. It
prints only allowlisted outcomes. It is not a LAN, installed-timer, ESP32 or
battery test. Do not run it in a container. `--output /NEW/PATH.json` optionally
writes a sanitized report, refusing to overwrite an existing file.

For local inspection only (prints actual metrics to your terminal):

```sh
python3 tools/m3/build_collector.py --output /tmp/infrabadge-collector.pyz
python3 -I /tmp/infrabadge-collector.pyz --sample
```

## Private inputs

Reuse the existing lab CA/server certificate/key and device **digest** only if
valid, still trusted and SAN matches the intended gateway URL. Keep original M2
files and backups unchanged. No new Wi-Fi provisioning is needed for host-only
M3 tests. A different CA/URL later requires a separately authorized board update.

The optional preparer makes new files outside Git and never starts anything:

```sh
/tmp/infrabadge-m3-check/bin/python tools/m3/prepare_config.py \
  --output "$HOME/.local/share/infrabadge-lab/m3-new" \
  --source-gateway /ABSOLUTE/PRIVATE/M2/gateway.json \
  --ca-file /ABSOLUTE/PRIVATE/M2/ca.pem \
  --gateway-url https://GATEWAY-SAN-NAME:8443 \
  --device-id badge-lab
```

Substitute private paths and the actual logical device ID locally. This generates
a **new collector token**, a collector config and a copied M3 gateway config.
It preserves the device digest, disables faults, and never reads the device's
Wi-Fi password or raw token. Token is never shown or passed in command arguments.
Do not publish outputs, inventories or raw snapshots. Config examples with
REPLACE/ABSOLUTE/invalid hostname intentionally cannot run as real configuration.

## Collector user installation

Review `deploy/m3/infrabadge-collector.service` and `.timer`, then:

```sh
python3 tools/m3/install_collector.py          # preview only
python3 tools/m3/install_collector.py --install
```

The installer refuses existing application/unit targets and non-private own
directories. It writes only the ZIP, SHA, two user units, example and empty state
directory. It does not enable units, modify existing configs or install packages.
No pip is needed for the collector; dependencies are Python stdlib only. The
zipapp is byte-reproducible across repeated builds of the same source.

After reviewing the newly prepared private files, copy collector.json and
collector.token into `~/.config/infrabadge/`, using 0600 permissions. The config
CA path may refer to the new private lab CA copy. `state_file` defaults to
`~/.local/state/infrabadge-collector/cpu.json` (0700 parent). Edit only the local
config if a different filesystem than `/var/home` should be monitored. Public
payload contains only its logical label HOME, not the path.

The unit uses LoadCredential to make the token available through `%d`, no token
environment variable/argv. It deliberately avoids alternative mount/proc
namespaces so statvfs/proc/sys describe the host. Read-only acquisition is enforced
by program behavior and normal Unix permissions, not an absolute filesystem
security sandbox. Same-user compromise can read private files. Nice/idle I/O,
NoNewPrivileges, UMask0077 and a 20 s timeout reduce privilege/resource footprint.

Only after configuration and gateway TLS work:

```sh
systemd-analyze --user verify ~/.config/systemd/user/infrabadge-collector.service ~/.config/systemd/user/infrabadge-collector.timer
systemctl --user daemon-reload
systemctl --user start infrabadge-collector.service
journalctl --user -u infrabadge-collector.service --since '-5 min' --no-pager
systemctl --user enable --now infrabadge-collector.timer
systemctl --user list-timers infrabadge-collector.timer
```

First run can be UNKNOWN because CPU needs a previous counter sample. The initial
trigger waits 30s from timer activation (OnActiveSec), so a preceding manual check
does not collide with the gateway's minimum sample spacing. Wait for verified
HTTPS readiness before that manual check: container start is not HTTP readiness.
The timer waits 60 s **after completion** with up to 5 s coalescing, not exact wall-minute
alignment. Changing `interval_seconds` also requires changing OnUnitInactiveSec
and gateway policy (minimum spacing/gap/TTL). It does not itself reschedule systemd.
Persistent=false is explicit; persistence affects calendar timers, while this one
uses monotonic time. WakeSystem=false does not wake the notebook. No backlog is
replayed after suspension; long gaps invalidate CPU continuity. Samples expire
while the notebook sleeps. User services normally depend on the login session;
linger can keep the user manager running after logout but cannot prevent suspend
or power-off. M3 does **not** enable `loginctl enable-linger`.

## Gateway rootless container

```sh
podman build -f deploy/m3/Containerfile -t localhost/infrabadge-gateway:m3 .
```

Python base is fixed by registry digest; pip uses existing hash-locked versions.
For deployment record the built image ID and pin the Quadlet Image to that local
immutable ID/digest rather than relying on a mutable tag. No image publication
is part of M3. The image runs UID10001, one Uvicorn worker and no access logs.

Prepare a **dedicated** `~/.config/infrabadge/gateway/` (0700) containing reviewed
gateway.json, server.pem and server.key (0600). Copy, do not move original M2 lab
files. `UserNS=keep-id:uid=10001,gid=10001` maps private files to the non-root
container user. The `:Z` relabel applies only to this dedicated directory, never
the whole home or original M2 backup. SELinux stays enabled.

`deploy/m3/infrabadge-gateway.container` is a Quadlet example. It exposes only
127.0.0.1 initially. Its server certificate must include the collector URL SAN;
localhost testing requires localhost SAN. For ESP32, explicitly select a Wi-Fi
LAN address and a resolvable SAN hostname. Add only that LAN PublishPort and
review router/client isolation, firewall and VPN return routing. The previous
M2 Tailscale return-route exception is historical; no M3 route/DNS/firewall change
is automatic. Do not use insecure TLS or a forced IP with the wrong SAN.

After separate authorization to install/start the gateway:

```sh
mkdir -p ~/.config/containers/systemd
cp deploy/m3/infrabadge-gateway.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start infrabadge-gateway.service
systemctl --user status infrabadge-gateway.service
journalctl --user -u infrabadge-gateway.service --no-pager
```

Quadlet's [Install] WantedBy is applied by its generator; do not attempt to enable
the generated service like a regular installed unit. Avoid an already occupied
8443 from the old lab gateway; stop it only after explicit operator review.
The gateway does not persist samples: restart yields UNKNOWN until next ingest.

## Uninstallation and recovery

Run only when the operator intends removal:

```sh
systemctl --user disable --now infrabadge-collector.timer
systemctl --user stop infrabadge-collector.service
systemctl --user stop infrabadge-gateway.service  # only if M3 Quadlet was installed
rm ~/.config/systemd/user/infrabadge-collector.service ~/.config/systemd/user/infrabadge-collector.timer
rm ~/.local/share/infrabadge-collector/infrabadge-collector.pyz ~/.local/share/infrabadge-collector/infrabadge-collector.pyz.sha256
rm ~/.config/containers/systemd/infrabadge-gateway.container  # only the M3 example
systemctl --user daemon-reload
systemctl --user reset-failed
```

Keep config/token/CA/state and all M2 originals unless explicitly choosing secret
retirement. Rotate/revoke the collector digest at gateway before deleting a token.
No cleanup command recursively deletes home/config/results, factory backup, NVS,
other user units or container storage. A software rollback starts the previous
gateway with its original private configuration; the board is unchanged by this
host-only installation. Board rollback is a separate authorized procedure.
