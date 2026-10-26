# Current official CASA v0.1.0 publication (2026-10-25)

- Owner explicitly authorizes Apache-2.0 for original code, license/docs PR,
  merge under main rules, annotated v0.1.0 tag and public GitHub Release.
- Work chore/license-v0.1.0 from verified main03e5948. License/docs only;
  preserve third-party notices and scope, no functional changes or new features.
- Verify exact PR HEAD/CI/protections, merge without bypass, then verify main CI
  before tagging the exact commit. Publish notes from docs/releases/v0.1.0.md.
- No extra binaries/assets, private data, hosts/services/timers/certs/network,
  ESP32/USB/NVS or firmware intervention. The installed M3.6 is distinct from CI.
- Preserve all accepted deferrals; do not claim first productive leaf rotation,
  physical night/energy/TRABAJO or M3.6 expiry/recovery passed. No collector audit.

# Current CASA v0.1.0 closure (2026-10-25)

- User authorizes documentation-only update, Ready/merge of PR12 after exact-HEAD
  CI/rules checks, and post-merge main CI. This supersedes earlier no-merge scope.
- Productive TLS supervised installation and exact installation rollback confirmed:
  monitor/evaluate/renew active, historical monitor disabled, same leaf/CA retained.
  Source bd4a98a plus two approved operational inventory adapters; no redeployment.
- First real leaf rotation remains unobserved until renewal_due27/10 22:03 ART.
  Three recovered collector failures have unknown cause; no extended investigation.
- Prepare v0.1.0 notes and tag/release candidate only. DO NOT create/push tag or
  publish release, alter hosts/services/timers/certs/network or touch ESP32/NVS.
- Night remains disabled; TRABAJO, energy, M3.6 expiry/recovery, OTA and extra
  peripherals are accepted deferrals, not new closure blockers.

# Current CASA stable closeout (2026-10-25)

- Work `chore/casa-stable-closeout` from verified main7e6d7af. PR11 is merged;
  corrected verifier passed three real sandbox checks. Keep its initial probe
  failure with undetermined cause documented. No need to repeat those trials.
- Development/tests/CI/docs, inert operational bundle and one draft PR only.
  Read-only Core inventory is authorized; no production certificate, timer,
  restart, network, SQLite, ESP32/USB/NVS, NAS or corporate-host changes.
- M3.6 CASA daytime is the installed physical baseline; night stays disabled,
  TRABAJO absent. Do not repeat BOOT/HTTPS/daytime expiry or factory backups.
- Existing public-only verifier/custodian separation remains mandatory. New
  heartbeat detection must work locally without an enabled webhook channel.
- Renewal <=10 days, never forced early; signer custody and retirement inventory
  must be reconciled before productive activation. No merge/tag/release.

# Current accelerated TLS fix (2026-10-24)

- Work PR11/feat/supervised-tls-renewal from verified7eca981. Fix verifier key
  isolation with public-only verification; never remove key/issuer masks or add
  privileges to bypass custody. Keep key-pair validation in authorized renewer.
- Operator reported previous65 TLS, five physical scenarios,120s guard/rollback
  and13 local alerts passed. Do not repeat or attribute them to corrected code.
  Corrected verifier on Core is pending; document it and keep PR11 unmerged.
- Software/full CI, exact production procedure and M3.5 provisioning preparation
  only. No production/SSH changes, rotation, timers, messages, network, NAS,
  reboot or board operations. No new firmware; M3.6/night remains subsequent.

# Current TLS lifecycle scope (2026-10-24)

- User explicitly authorized ready/merge of PR10 after exact-SHA checks; merged
  as ca9c172 with main CI successful. Preserve branches and operational evidence.
- Work feat/supervised-tls-renewal from that main: software, disposable PKI/TLS
  tests, inert units, docs and draft PR only; do NOT merge the new PR.
- No real certificate rotation, CA replacement, Edge/Core/collector/host service
  changes, installed timers, network/firewall/DNS/Grants, external messages,
  board/USB/NVS/flash, NAS or work-host access. Production remains untouched.
- Keep CA/SAN trust, v1/v2 ETag/TTL and dedicated probe identity. Never use the
  lab CA generator to renew production. Signer custody/channel need approval.
- No memory controller on Core: LimitAS is virtual, not RSS. Energy remains deferred.

# Current CASA edge on Core (2026-10-23)

- Adapt PR10/feat/permanent-edge-preparation in place. CASA runs on
  infrabadge-core: separate unprivileged edge -> verified127.0.0.1:9443 Core.
  NAS deployment proposal is abandoned; do NOT access or modify NAS for this task.
- Core SSH metadata/TLS preflight is authorized read-only. Operator separately
  ran the sudo reader; never request passwords in chat or reuse deployment plans.
- Implement/test offline install and rollback tools; local TLS fixtures only.
  No real users/files/services, Core/collector/SQLite changes, firewall/routes/
  DNS/Grants, credentials, host restart, board/USB/NVS/flash or PR10 merge.
- Actual host has final INPUT DROP: separate allow table alone is insufficient.
  Future8443 access needs explicit exact owned exception before existing drop,
  plus owned source restriction and rollback by handle/digest. No general policy.
- Core already binds127.0.0.1+Tailscale9443 with valid127 SAN. No bind/PKI change
  to Core. Copy only public CA to separate edge dir after future authorization;
  no shared user/group or access to Core config/SQLite/key. Memory controller
  is absent, so MemoryMax is NOT a physical RAM limit on this host.

# Historical permanent-edge preparation (2026-10-23)

- User-authorized consolidation merged PR8/c24b0dc, PR9/66bf529 and scoped
  PR7/c62f800 with exact-HEAD checks; verify main post-merge CI before reporting
  completion. Preserve all branches and private backups.
- Work feat/permanent-edge-preparation only: inert templates, allowlisted
  preflight, verified TLS probe with distinct synthetic identity, owned rollback,
  tests and draft PR. This new PR is NOT authorized for merge or deployment.
- NAS root SSH metadata-only audit was explicitly authorized and completed.
  No NAS data/keys/socket reads, installs, services, network, credentials or
  storage changes; no work-host access or corporate telemetry approval.
- Tests may bind temporary loopback TLS only. No LAN listeners/firewall/routes/
  DNS/Tailscale/Grants changes, service activation, provisioning/USB/flash/NVS,
  suspend/roaming/night or electrical trials. M3.5 stays installed; M3.6 physical
  roaming/night and M3.3 G/H/I remain pending. Energy is operator-deferred.
- Root rollback code is inert: never execute against systemd/nft on a real host
  without specific deployment authorization and independently verified timer.

# Historical PR consolidation (2026-10-23)

- User explicitly authorizes ready/merge of technically prepared PR8, then PR9,
  then scoped PR7, respecting main protections. Preserve branches/backups and
  traceability; this supersedes historical no-merge instructions below.
- PR8 integrated as c24b0dc; PR9 integrated as 66bf529. Verify post-merge
  CI before scoped PR7 integration, then verify its exact-HEAD and main CI.
- NAS root SSH read-only metadata audit was explicitly approved on2026-10-23;
  this does not authorize deployment, NAS data/key reads or host changes.
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

# Historical M3.3 scope: exclusively F completed after specific approval (2026-10-22)

- User authorized ONLY F: fresh nodes, Fedora H/W baseline allowed without health
  policy changes; abort critical memory/pressure/OOM/deterioration. No G/H/I.
- Actual trial started three HEALTHY/fresh, memory improved. Only collector URL
  port9443->9444 changed; same hostname/CA/token/identity. Original timer stayed
  active; acquisitions continued. UNKNOWN/OFFLINE and two NEW real CPU-delta
  recovery samples observed. Core/NAS remained HEALTHY/fresh and advanced.
- Independent systemd user helper was exercised first, then watchdog armed
  BEFORE fault. Exact config restoration within390s proven in its journal;
  hashes/UID/GID/mode intact, timer enabled/active and oneshot success, transient
  timers removed. Private consumed marker/evidence retained; NEVER repeat it.
- See docs/M3.3-TRANSPORT-RESULTS.md. This is unreachable configured endpoint,
  NOT physical link loss, suspend, roaming/logout or power evidence. No network,
  central service, NAS, firmware, policy or credential change. Keep PR7 draft.
- Do not suspend, change Wi-Fi/Tailscale/firewall/Grants, restart, logout, enable
  linger, repair old M3 gateway or begin another disruptive trial under F approval.

# Historical M3.3 scope: F READ-ONLY preflight/design (2026-10-22)

- The new request explicitly authorizes ONLY F audit/design, then STOP for
  approval before any transport/service/session/network interruption. D/E
  approvals and consumed markers do not authorize F/G/H/I.
- Revalidated base49e1927, PR7 draft and12 successful checks; Fedora collector
  one timer active/enabled, three real nodes HEALTHY/fresh, TLS1.3 verified.
- Proposed F changes ONLY gateway_url port9443->9444 on SAME hostname/CA/token.
  Central unprivileged SSH found no9444 listener; unauthenticated2s TCP probe
  timed out;9443 reader stayed available. This is an unreachable configured
  endpoint test, NOT physical network loss or blocking original9443.
- Candidate/config copy/private restoration helper and17 synthetic tests are
  prepared outside Git. Pending manifests approved=false; authorized manifest
  absent; no fault applied or watchdog armed. Never turn it on without approval.
- Proposed watchdog390s (inside480s), same user manager, self-contained stdlib
  restore; no daemon-reload/unit edits, no stop/restart of collector or core.
  Abort on drift/observer/other-node failure; preserve all markers/evidence.
- Acquire/save baseline precedes POST in installed M3; during transport failure
  CPU may remain valid. Do not require warmup solely due to network failure.
- Later reader smoke observed notebook WARNING/fresh from low available RAM;
  core/NAS stayed HEALTHY. Do not force health or close apps. Before F, require
  three HEALTHY nodes again or an explicitly revised baseline authorization.
- G preparation follows completion of F; suspend requires separate permission.
  H is plan-only; I no logout/reboot/linger. No NAS SSH/Docker/board, Grants,
  global firewall/DNS/routes/VPN/NM or local gateway repair. Keep PR7 draft.

# Historical M3.3 scope: authorized collector expiry/recovery E completed (2026-10-22)

- After D, the user explicitly authorized pausing ONLY the Fedora collector for
  at most8min, observing expiry/recovery and automatically restoring its timer.
- E used the existing HTTPS reader identity, no new credentials or sudo. A
  transient user watchdog was armed BEFORE pause to reactivate the SAME timer
  at7min; normal cleanup restored it earlier and removed the watchdog.
- The real API observed notebook UNKNOWN/stale atTTL180, OFFLINE at360, with
  current metrics absent and explicit historical data; other two nodes remained
  fresh and independently advanced. Resume produced NEW warmup/UNKNOWN then
  valid CPU delta with health from current metrics. No queued old payloads or
  duplicate collector.
- This is collector-pause evidence, NOT network outage, suspend/resume, network
  switching or logout. Those remain unexecuted and require separate approval.
  No central service/config, firewall, DNS/routes/VPN/Grants, NAS or board change.
- E consumed marker/results stay private and must not be rerun. Keep PR7 draft;
  publish sanitized docs/results only, no secrets/raw inventory/journals.

# Historical M3.3 scope: authorized phase D completed (2026-10-22)

- The user explicitly authorized the concrete phase D after A/B/C: private
  rollback copies, one new independent collector token, migration of the one
  existing Fedora collector, central node/scoped identity and ONE exact
  notebook/32->core/32 TCP9443 tailscale0 rule plus its own persistence line.
  One short core-only restart was authorized; socket/core timer stayed active.
- D completed in the private 20261022T154403Z run. Two independent Fedora samples
  (UNKNOWN/cpu_warmup then HEALTHY/delta), fresh HEALTHY core/NAS samples,
  TLS1.3/CA/name/date and four scoped401 rejections verified. Subsequent Fedora
  timer deliveries succeeded. Installed M3 zipapp and all units are unchanged.
- The previous153358Z attempt failed at Python config import before network or
  core mutation. The launcher was corrected to match service PYTHONPATH/CWD;
  the consumed attempt and unused token were preserved, continuation reused it.
  Do not rerun either consumed execution marker or generate replacement tokens.
- Central config/firewall copies and coherent SQLite backup were verified with
  restore into a NEW destination. Live DB inode preserved; no old DB overwrite.
  Local original M3 config/token/CA/baseline/image/units remain private.
- Old local gateway remains in its pre-existing failed/protocol state. Do not
  repair/start it or claim functional rollback delivery. No NAS SSH/Docker,
  Grants, routes/DNS/NM/VPN/clock/linger, firmware or host reboot changes.
- Further collector pause, transport interruption, suspend/resume, network
  switch or logout tests require separate authorization. D does NOT close all
  M3.3 acceptance criteria. Energy, external backup and DR remain deferred.
- Update only sanitized evidence/docs and draft PR7; never publish addresses,
  credentials, private configs or raw journals. Keep draft, no merge.

# Historical M3.3 scope: READ-ONLY preflight A/B/C (2026-10-22)

- Work on feat/m3.3-fedora-mobile from main da4a3ff. M3.2 PR6 is merged;
  M3.1 PR5 closed without merge, both historical branches preserved.
- This task authorizes Fedora read-only audit, plans, docs and a draft PR only.
  No collector migration, service control, credential/firewall/Grants/DNS/routes/
  NetworkManager/VPN/clock change, install, suspend/logout/reboot or board access.
- The user separately authorized read-only SSH inspection of the central host,
  including its existing administrative account. Strict known-host verification
  is mandatory; operator entered sudo locally. Never access NAS or work hosts.
- Existing installed M3 zipapp is compatible: prefer retaining code and user
  units, one collector/timer. Do not run installer or generate live credentials.
- Core firewall currently rejects notebook9443; old local gateway is failed.
  Do not claim a working delivery rollback or third-node/mobility validation.
- All proposed real addresses/config deltas/evidence stay private outside Git.
  Next gate is explicit authorization for D, including a short core-only restart,
  which makes retained samples historical until fresh deliveries. Grants and
  disruptive mobility tests require separate review/authorization.

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
