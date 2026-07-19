# Runbooks

Common operational procedures for Simon's homelab. Keep entries short — what to run, what to check, what success looks like.

---

## Disaster recovery — scenario index (start here in an outage)

**Pick what's broken, read the recovery model, jump to the steps.** This is a front
door only — the detailed commands live in the sections it links to, never duplicated
here. Logical facts (VMIDs, which node owns what) are owned by [PLAN.md](../../PLAN.md);
real addresses/secrets are **not** in this repo (ADR-006) — they live in the gitignored
Ansible config and your password manager. The credentials these procedures reference
(PBS encryption key, Technitium admin password, HA backup key, 2FA recovery codes) are
Tier-1/2 anchors in Keychain/Google Password Manager — **not** in Vaultwarden, so
recovery stays non-circular.

**Drill status legend:** ✅ proven by a real restore drill · ⚠️ procedure written but
**never drilled** (a hypothesis until run) · ❌ known gap, no recovery path yet.

| What's down | Recovery model (one line) | Drill | Jump to |
|---|---|---|---|
| **apophis** (primary node) dies | carter survives read-only → `pvecm expected 1`, manual-failover VM 200 (+ 118) from the latest replica → rebuild apophis on ZFS → rejoin → failback | ✅ failover 2026-06-25 · ✅ rebuild executed 2026-06-25 | [Manual failover](#manual-failover-vm-200-when-apophis-is-truly-dead--adr-009) · [Rebuild apophis on ZFS](#phase-4b-rebuild-apophis-on-zfs-one-time--infra-designer-reviewed-2026-06-22) |
| **carter** (failover target + Actual host) dies | HA/Vaultwarden continue on apophis, but Actual is down → restore VM 127's PBS image temporarily to apophis or rebuild + rejoin Carter → restore 127 → recreate replication jobs 200-0 + 118-0 → reprovision CT 117 | ⚠️ runbook written; live host drill deferred (apophis 4b is the symmetric proof) | [Rebuild carter — DR runbook](#rebuild-carter-the-failover-target--dr-runbook) |
| **oneill** (standalone services hub) dies | DNS/monitoring/backup outage only — CT 117 covers DNS; production unaffected if apophis is up → fresh PVE+ZFS → no-sub repo → re-run the oneill playbooks | ⚠️ not drilled | [Recovery model → "oneill dies"](#recovery-model--what-recovers-what-avoid-doubling-up) |
| **mgmt-vm** (VM 100) dies | not recreatable from code → `qmrestore` its PBS image to a new VMID | ✅ 2026-06-17 | [Restore a guest from PBS](#restore-a-guest-from-pbs) · [Restore drills](#restore-drills-a-backup-you-havent-restored-is-a-hypothesis) |
| **mgmt-vm2** (cold VM 128) is lost | reproducible → re-run `provision-secondary-mgmt.yml` from VM 100; a fresh distinct automation key is rolled out automatically | n/a — deliberately not imaged | [Cold secondary management VM](#cold-secondary-management-vm) |
| **Home Assistant** (VM 200) dies | restore the native partial backup onto a fresh HAOS, **or** fail over to carter's replica | ✅ HA restore 2026-06-18 · ✅ failover 2026-06-25 | [HA native partial backup](#home-assistant--native-partial-backup-primary-for-ha) · [Manual failover](#manual-failover-vm-200-when-apophis-is-truly-dead--adr-009) |
| **Vaultwarden** (VM 118) dies | playbook rebuilds VM+container; vault **data** comes from the PBS image (or carter replica) → `qmrestore` | ✅ 2026-06-26 | [Restore a guest from PBS](#restore-a-guest-from-pbs) · [Restore drills](#restore-drills-a-backup-you-havent-restored-is-a-hypothesis) |
| **Actual Budget** (VM 127) dies | playbook rebuilds VM+container; finance **data** comes from its Carter→oneill PBS image or portable Actual ZIP | ✅ PBS restore 2026-07-15 | [Actual Budget component](../components/actual-budget.md) · [Restore a guest from PBS](#restore-a-guest-from-pbs) |
| **Jellyfin** (CT 120) dies | reproducible from code → re-run `provision-jellyfin.yml`, redo wizard + re-add `/media/library`; **media persists on the USB SSD**, config not imaged (cheap to recreate) | n/a — not imaged by design | [jellyfin.md](../components/jellyfin.md) |
| **qBittorrent** (CT 121) dies | reproducible → re-run `provision-qbittorrent.yml` (needs WG config + IP in gitignored `all.yml`); downloads persist on the USB SSD; killswitch must pass leak-test after | n/a — not imaged by design | [qbittorrent.md](../components/qbittorrent.md) · [leak-test](#qbittorrent--wireguard-killswitch-ct-121--adr-021-phase-6b) |
| **Sonarr** (CT 123) dies | reproducible → re-run `provision-sonarr.yml --limit apophis`; re-add qBittorrent download client + root folder (`/media/library/tv`) in web UI; indexers re-sync from Prowlarr. **Wanted-list (monitored series) is lost** — re-add manually or from a Sonarr backup export. | n/a — not imaged by design | [sonarr.md](../components/sonarr.md) |
| **Radarr** (CT 124) dies | reproducible → re-run `provision-radarr.yml --limit apophis`; re-add qBittorrent download client + root folder (`/media/library/movies`) in web UI; indexers re-sync from Prowlarr. **Wanted-list (monitored movies) is lost** — re-add manually or from a Radarr backup export. | n/a — not imaged by design | [radarr.md](../components/radarr.md) |
| **Jellyseerr / Prowlarr / ByParr** (VM 125) dies | reproducible → re-run `provision-jellyseerr.yml` (no `--limit`; needs `prowlarr_vpn_wg_config` + `jellyseerr_ip` in gitignored `all.yml`); redo Jellyfin OAuth sign-in; re-add Sonarr/Radarr with new API keys; re-add indexers + ByParr FlareSolverr proxy (`http://localhost:8191`) in Prowlarr. | n/a — not imaged by design | [jellyseerr.md](../components/jellyseerr.md) · [prowlarr.md](../components/prowlarr.md) |
| **Technitium DNS** (CT 111 oneill / CT 117 carter) | reproducible from code → re-run `provision-technitium.yml --limit <node>`; the other resolver covers DNS during the rebuild. **Needs the admin/API password at the prompt** | ⚠️ not drilled (reprovision drill pending) | [Recover CT 111](#recover-ct-111-lost--corrupted-or-oneill-rebuilt) |
| **Tailscale** (CT 110) / **Glance** (CT 115) / **Monitoring** (CT 114) / **infra-portal** (CT 116) / **HA share** (CT 113) / **PBS** down | all reproducible from code → re-run the matching `provision-*.yml` / `install-node-exporter.yml` | ⚠️ not drilled | [Recovery model](#recovery-model--what-recovers-what-avoid-doubling-up) |
| **PBS datastore / oneill SSD lost** (backup data, not production) | single local copy today → loses restore history, not production. **Off-site copy is the real fix and is still deferred** | ❌ off-site GAP (ADR-012) | [Recovery model → "Backing up the hub"](#recovery-model--what-recovers-what-avoid-doubling-up) |
| **Both nodes / site disaster** | infra rebuilds from git (Ansible + private repo); VM **data** is lost until the off-site copy exists | ❌ off-site GAP | [Recovery model → "Both / site disaster"](#recovery-model--what-recovers-what-avoid-doubling-up) |

> **Two soft spots to know before you need them:** (1) backup **data** on oneill is a
> single copy — the off-site leg (ADR-012) is unresolved, so a site disaster loses VM
> data; (2) the CT 111/117 reprovision and oneill-rebuild paths are **documented but
> not yet drilled** — treat their RTO as an estimate, not a fact, until run.

---

## Proxmox host (apophis)

### Check host health
```bash
ssh root@YOUR_PROXMOX_IP 'pvesh get /nodes/apophis/status --output-format json | python3 -m json.tool'
```
Look for: `uptime`, `mem.used` vs `mem.total`, `cpu`.

### List running VMs and LXCs
```bash
ssh root@YOUR_PROXMOX_IP 'qm list && echo "---" && pct list'
```

### Check storage
```bash
ssh root@YOUR_PROXMOX_IP 'pvesm status'
```

---

## Home Assistant

### Check HA is reachable
- Local: http://YOUR_HA_IP:8123
- Remote: via Cloudflare Tunnel URL

### Restart HA (from Proxmox)
```bash
ssh root@YOUR_PROXMOX_IP 'qm reboot 200'
```

### Check Zigbee coordinator
Zigbee2MQTT connects to SLZB-06 at `YOUR_ZIGBEE_COORD_IP`. If Zigbee devices stop responding:
1. Check HA → Zigbee2MQTT add-on logs
2. Ping coordinator: `ping -c 3 YOUR_ZIGBEE_COORD_IP`
3. Restart Zigbee2MQTT add-on from HA UI

**Cross-subnet path (HA on Home VLAN → SLZB-06 on IoT VLAN).** HA (Home Network, **Secure** zone)
reaches the coordinator (IoT Network, **Unsecure** zone) via two UniFi zone rules: **Allow
Secure→Unsecure** (Home→IoT, subnet-wide) for HA→coordinator, and the **Allow** return
(IoT-subnet→Home-subnet) for replies. Z2M talks to the SLZB-06 over **TCP** (serial-over-IP). The
Home→IoT allow is **subnet-wide, not scoped to the HA IP** — a *hardening backlog item* is to tighten
it to `HA-IP → coordinator-IP` only. (This breadth is also why the restore-drill test HA must sit on a
fully-isolated VLAN, not the Home VLAN — see Restore drills.)

---

## mgmt-vm

### Check mgmt-vm connectivity
```bash
ping -c 3 YOUR_MGMT_VM_IP
```

### SSH to mgmt-vm
```bash
ssh simon@YOUR_MGMT_VM_IP
```

## Cold secondary management VM

VM 128 `mgmt-vm2` is an independent Ubuntu control node on Carter at
`YOUR_SECONDARY_MGMT_IP`. It is not a clone of VM 100. Its own hostname, MAC, machine identity, SSH
host keys and automation key allow a controlled test alongside the primary without an address or
identity collision. It is normally `stopped`, has `onboot=0`, and is protected against accidental
deletion.

**Build validation passed 2026-07-18:** Ubuntu 24.04.4, 2 cores / 8 GB / 64 GB thin zvol, unique
machine and SSH host identity, both operator login keys, key-only SSH, passwordless sudo, DNS, guest
agent, clean checkout, and Ansible `pong` from Apophis/Carter/Oneill. It returned to stopped/protected
state after the test. ZFS actual use was 2.28 GB; `refreservation=none` prevents a cold VM from
reserving its full virtual size.

### Commissioning status (2026-07-18)

- VM 128 `mgmt-vm2` is live on Carter and deliberately left `stopped`, with `onboot=0`,
  `protection=1`, and tags `cold-standby;recovery`.
- Operator SSH, passwordless sudo, DNS, QEMU guest agent, the clean repository checkout, security
  patching, and Ansible access to all three PVE hosts have been tested successfully.
- Public HTTPS fetches work. Before the first push, display `~/.ssh/id_ed25519_github.pub` and add
  that repo-scoped key under the GitHub repository's **Settings → Deploy keys** with write access.
  Do not copy or register the primary management VM's account key.
- **AI-ready refresh codified 2026-07-19, live refresh pending:** the playbook now installs Claude
  Code from Anthropic's signed stable apt channel and Codex from OpenAI's official npm package in
  `~/.local/npm`. It validates both binaries but deliberately copies no agent credentials or state.
- A cold VM cannot start itself. When the operator is away from the authorized desktop, Carter
  still needs a separate authenticated access path before `qm start 128`; direct operator-only
  Tailscale SSH to Carter remains a backlog item.

The checkout is `/home/simon/src/homelab`; the real gitignored `hosts.ini` and `group_vars/all.yml`
are copied there during provisioning. Its distinct automation public key is authorized on all PVE
hosts. The checkout uses public HTTPS for credential-free fetches. A separate
`~/.ssh/id_ed25519_github` is generated for SSH pushes without copying the primary's account key;
register its `.pub` once under the repository's **Settings → Deploy keys** with write access. Agent
sign-in is deliberately not copied from the primary.

After the AI-ready playbook refresh, complete the one-time agent commissioning interactively on
`mgmt-vm2`; never copy `~/.claude`, `~/.codex`, tokens, sessions, or browser credentials from VM 100:

```bash
claude --version
codex --version
claude auth login
codex login
```

Both sign-in flows use a browser. For Codex over a headless SSH session, `codex login --device-auth`
is the documented fallback when the localhost browser callback is unavailable. Confirm the final
state without printing tokens:

```bash
claude auth status --text
codex login status
```

For VS Code, connect with Remote SSH and confirm the status bar identifies `mgmt-vm2`. Install the
Claude Code and Codex extensions in the remote window when VS Code offers **Install in SSH:
mgmt-vm2**, then sign in there. Do not rely on the primary VM's extension or cached authentication
appearing in the remote extension host.

### Use the recovery VM

Use `mgmt-vm2` when the primary management VM is unavailable, when planned work takes the primary
offline, or when an independent control node on Carter is needed to diagnose or recover the PVE
hosts. It is not a highly available service host and should not remain powered on after the
management session.

Start it from an authenticated Carter session, connect to it, and validate its control-plane view
before making changes:

```bash
ssh root@YOUR_CARTER_IP 'qm start 128'
ssh simon@YOUR_SECONDARY_MGMT_IP
cd ~/src/homelab
git status --short --branch
git pull --ff-only
cd homelab/ansible
ansible proxmox -m ping
claude --version
codex --version
```

Stop if the checkout has uncommitted changes, is not on the intended branch, cannot fast-forward,
or any host expected to be available does not return `pong`. Once validated, use the same playbooks
and runbook procedures as on the primary management VM. Commit and push completed infrastructure
changes before shutting down so the primary can later resume from the repository's canonical state.

If Apophis is actually down, Carter first loses quorum. Confirm this is a real node outage rather
than a network partition, then use the already-authorized operator desktop path:

```bash
ssh root@YOUR_CARTER_IP 'pvecm expected 1 && pvecm status && qm start 128'
```

Never lower expected votes while Apophis might still be running. A remote Tailscale client retains
the network route through CT 126 on Oneill, but it still needs an authorized way to SSH to Carter;
the cold VM cannot start itself.

### Working and shutdown rules

- Pull with `git pull --ff-only` before editing. Register the generated repo-scoped deploy key once
  before the first push; no `gh auth login` is used.
- Never run both management VMs from the same working branch. Finish, commit and push from one
  control node before continuing that branch on the other.
- Treat the copied inventory as a point-in-time recovery copy. Re-run the provisioning playbook
  after meaningful local-only inventory changes to refresh and revalidate the standby.
- Treat Claude and Codex authentication as independent recovery-node state. Sign in interactively;
  never copy the primary VM's agent directories or credential files.
- Do not add VM 128 to normal autostart or GuestDown alerting; powered off is its healthy state.

Return it to cold state from inside the VM, then verify from Carter:

```bash
sudo poweroff
ssh root@YOUR_CARTER_IP 'qm status 128; qm config 128 | grep -E "^(onboot|protection):"'
# expect: stopped, onboot: 0, protection: 1
```

Build or refresh deliberately from the primary control node:

```bash
cd ~/homelab/ansible
ansible-playbook playbooks/provision-secondary-mgmt.yml
```

---

## Tailscale (CT 110, subnet router)

Unprivileged LXC 110 on apophis (LAN `YOUR_TAILSCALE_LAN_IP`, Tailscale IP `YOUR_TAILSCALE_IP`).
Advertises `YOUR_LAN_CIDR` for remote LAN access. Provisioned via Ansible
(`ansible-playbook playbooks/provision-tailscale.yml`, idempotent).

### Check status (from apophis)
```bash
pct exec 110 -- tailscale status
```

### Restart Tailscale
```bash
pct exec 110 -- systemctl restart tailscaled
```

### Change advertised routes
Edit `tailscale_advertise_routes` in `ansible/inventory/group_vars/all.yml`, re-run
the playbook, then **approve the new route** in the Tailscale admin console.

### If remote access stops working
1. `pct status 110` — is the CT running?
2. `pct exec 110 -- tailscale status` — is Tailscale up?
3. Confirm the subnet route is still approved (admin console → Machines → node).
4. `pct exec 110 -- sysctl net.ipv4.ip_forward` — should be `1`.

---

## Technitium DNS (CT 111, DNS-only resolver)

Unprivileged LXC 111 on **oneill** (KAMRUI Essenx E2, `YOUR_NUC_IP`). **DNS only — UniFi keeps DHCP**
(ADR-011). Provisioned via Ansible
(`ansible-playbook playbooks/provision-technitium.yml --limit oneill`, idempotent). Web
console on port `5380`, DNS on `53`.

> **DNS-by-VLAN-role (important):** Technitium serves the **home VLAN only** (same subnet as
> the resolver). **IoT + guest VLANs use the gateway (Auto) for DNS** — they're isolated and
> can't reach a main-LAN resolver (it lives on the home VLAN), and cloud appliances (Sensibo, Roborock…) break on
> blocklist NXDOMAINs. Pointing an isolated/appliance VLAN at Technitium silently breaks its
> devices (queries never arrive — confirmed by zero such clients in Technitium's logs).
> Camera/management have no internet, so no resolver.

> **Config invariant:** all Technitium config (forwarders, blocking, blocklists) is applied
> by the playbook via the API from `technitium_*` group_vars. Treat the web console as
> **read-only** — make changes in group_vars and re-run, or they'll be overwritten and lost
> on the next run (and the reprovision/restore path won't reproduce them).

### Check status (on oneill)
```bash
ssh root@YOUR_NUC_IP 'pct exec 111 -- systemctl status dns.service --no-pager'
```

### Test resolution (from the mgmt-vm)
```bash
dig @YOUR_TECHNITIUM_IP example.com +short                    # should resolve
dig @YOUR_TECHNITIUM_IP securepubads.g.doubleclick.net +short # should be blocked (NXDOMAIN)
```
Note: test with a hostname that is **actually in the list** (e.g. `securepubads.g.doubleclick.net`,
`accounts.doubleclick.net`). OISD lists ad/tracking *hostnames*, not bare apex domains — so
`doubleclick.net` itself resolving is expected and is not a sign blocking is broken.

### Restart Technitium
```bash
pct exec 111 -- systemctl restart dns.service
```

### Logs
Console → **Logs**, or: `pct exec 111 -- journalctl -u dns.service -n 50 --no-pager`

---

### First-run config — automated by the playbook

Forwarders (DoH), blocking type (NX Domain), and the blocklist (OISD Big) are applied by
`provision-technitium.yml` via the Technitium API from the `technitium_*` group_vars — no
manual console setup. To change them, edit the vars and re-run the playbook (the config
tasks are idempotent and run every time; they read the settings back and fail if anything
didn't apply). **Verify** with the `dig` tests above; the Dashboard **Block List** count
should read ~300k+ once OISD finishes downloading.

To configure manually instead (console at `http://YOUR_TECHNITIUM_IP:5380`): Settings →
Proxy & Forwarders for upstreams; Settings → Blocking to enable, set NX Domain, add
`https://big.oisd.nl/domainswild2`, Save, then Update Now.

### DHCP → DNS cutover (the actual switch)

The switch is **one UniFi DHCP field**, not a service migration. Reversible.

1. **Pre-flight:** confirm the two `dig` tests above pass against `YOUR_TECHNITIUM_IP`.
   Reserve/exclude `YOUR_TECHNITIUM_IP` in UniFi so the LXC IP never changes.
2. **Cut over (per-network, low-traffic window):** UniFi → Settings → Networks → (your
   LAN/VLAN) → DHCP → **DNS Server** → set to `YOUR_TECHNITIUM_IP`. Leave the secondary
   **blank** by default — a public secondary (e.g. `1.1.1.1`) silently bypasses blocking
   whenever it's used (ADR-011). Add one only if you accept that trade-off for resilience.
3. **Propagate:** clients pick up the new resolver on lease renewal. Force it on a test
   client (`ipconfig /renew`, or toggle Wi-Fi) and confirm `nslookup` shows the new server.
4. **Watch** the Technitium dashboard — query volume should climb as clients renew.
5. **Per-VLAN policy (DNS-by-VLAN-role):** only point a VLAN at Technitium if it can *reach*
   the resolver and benefits from blocking — i.e. the **home VLAN**. **Leave isolated/appliance VLANs
   (IoT, guest) on the gateway (Auto)** — they can't reach a main-LAN resolver and appliances
   break on blocklists. Don't blanket-roll-out to every VLAN.

### Rollback (if DNS misbehaves)

1. UniFi → the network's DHCP → **DNS Server** → set back to the previous resolver
   (gateway or `1.1.1.1`).
2. Renew a client lease to confirm recovery.
3. Technitium can stay running while you debug — clients no longer depend on it.

### Planned maintenance on oneill (DNS goes down with it)

Technitium is a single instance with no DHCP secondary (ADR-011), so taking oneill down
drops DNS for the **home VLAN** (IoT/guest use the gateway, so they're unaffected). Before planned maintenance:
1. UniFi → each affected network's DHCP → set **DNS Server 2 = `1.1.1.1`** (temporary fallback).
2. Do the maintenance.
3. **Remove** the `1.1.1.1` secondary afterwards (so blocking is never silently bypassed).

DNS redundancy is now live (Phase 4 ✓ 2026-06-25): CT 117 `technitium2` on carter. The remaining operator step is to hand **both** resolver IPs out as DHCP DNS servers (primary + secondary) on the home VLAN so clients fail over automatically — then planned oneill maintenance no longer needs the temporary `1.1.1.1` secondary above.

### Recover CT 111 (lost / corrupted, or oneill rebuilt)

Technitium is stateless relative to Ansible — all config is in `technitium_*` group_vars.
Recovery is a reprovision, RTO ~15–20 min:
```bash
ssh root@YOUR_NUC_IP 'pct stop 111 && pct destroy 111'   # if the CT still exists
cd ~/homelab/ansible && ansible-playbook playbooks/provision-technitium.yml --limit oneill
```
Then verify with the `dig` tests above. If the whole oneill SSD died: fresh PVE install
(ZFS-on-root) → `ssh-copy-id` → re-run the playbook. (Untested — see the reprovision-drill
backlog item.)

---

## Monitoring + alerting (CT 114 on oneill) — ADR-013

- **Prometheus + Grafana** in unprivileged CT 114 on oneill (needs `features nesting=1` — their
  systemd sandboxing fails 226/NAMESPACE without it). TSDB on a quota'd ZFS bind-mount, 30d.
  - Prometheus: `http://YOUR_MONITORING_IP:9090` (`/targets` for scrape health).
  - Grafana: `http://YOUR_MONITORING_IP:3000` (admin) — LAN/Tailscale only. Import dashboards
    (e.g. 1860 Node Exporter Full); export edits back to the repo per ADR-013.
- **node_exporter** on apophis + oneill (`:9100`) via `install-node-exporter.yml`.
- **Exporters:** pve-exporter (`:9221`, PVE API, read-only `PVEAuditor` token), unpoller
  (`:9130`, UniFi read-only user), Home Assistant `/api/prometheus` (long-lived token). All creds
  are `vars_prompt`/vault — never committed (ADR-006).
- **Alerting chain:** Prometheus rules (`/etc/prometheus/rules/*.yml`, sourced from
  `ansible/files/monitoring/alert-rules.yml`) → **Alertmanager** (`:9093`, localhost-routed) →
  **am-ntfy bridge** (`/usr/local/bin/am-ntfy.py`, a stdlib webhook→ntfy translator on
  `127.0.0.1:9095`, since ntfy isn't a native AM receiver) → **ntfy** (private topic; subscribe the
  app). The topic is a secret — gitignored `group_vars/all.yml` (`ntfy_topic`), never committed; the
  bridge reads it from `/etc/am-ntfy/env` (0600). AM's cluster port (`:9094`) is disabled (single
  instance). Rules: `TargetDown`, `NodeFilesystemSpaceLow`, `NodeMemoryHigh`, `PVEStorageFull`,
  **`GuestDown`** (`pve_up{id=~"lxc/.*|qemu/.*",id!="qemu/128"} == 0` — a guest stopped/crashed while its host is up;
  `up`/TargetDown only covers *scraped* targets, so this is what catches a service LXC like Tailscale
  or Technitium dying on its own. VM 128 is excluded because powered off is the cold standby's
  healthy state. A whole-host outage makes these go *absent*, caught by TargetDown).
  - **Test the pipeline:** `pct exec 114 -- amtool --alertmanager.url=http://localhost:9093 alert add
    alertname=PipelineTest severity=critical --annotation=summary="test"` → ntfy push after the 30s
    group_wait (auto-resolves ~5 min later). Confirm delivery without a phone:
    `curl -s "https://ntfy.sh/<topic>/json?poll=1&since=3m"`.
  - **Validated on a real outage (2026-06-18):** apophis powered off for a RAM upgrade → oneill's
    Prometheus fired `TargetDown` (critical) for `node`/`pve-apophis`/`home-assistant` ~5 min in
    (respecting `for: 5m`), then `RESOLVED` when it came back — full path Prometheus → Alertmanager →
    am-ntfy → ntfy → phone confirmed. Gap found + closed in the same test: the service LXCs weren't
    individually watched (added `GuestDown`).
- **Dead-man's-switch:** `provision-deadmans-switch.yml` installs a 5-min cron on **apophis**
  (`/usr/local/bin/oneill-watch.sh`) that checks oneill's Prometheus + Technitium DNS and ntfy-alerts
  on failure — so "oneill/Technitium down" is caught even though Alertmanager lives on oneill (it
  can't alert on its own host being down). Test: `ssh root@YOUR_PROXMOX_IP /usr/local/bin/oneill-watch.sh`
  (silent when healthy).

---

## Glance dashboard (CT 115 on oneill) — ADR-014

- **What:** the front-door operator dashboard — `http://YOUR_GLANCE_IP:8080`, LAN/Tailscale only,
  **no auth**. Single Go binary at `/opt/glance/glance` (pinned `glance_version`), config
  `/etc/glance/glance.yml` **rendered from the committed template `ansible/templates/glance/glance.yml.j2`**.
  `Overview` puts core telemetry, a three-host CPU/RAM/ZFS pulse with local-ZFS GB detail plus compact
  PBS/Media USB capacity, and host-grouped service links first. Maintenance explicitly separates
  automatic, monthly, and immediate action; update review is exception-only and sits lower down.
  `Infrastructure` holds visual host/workload resources and the fleet baseline.
  Stateless — nothing to back up.
- **Manage:** edit the **template** (`glance.yml.j2`) and/or `glance_*` vars (`glance_prometheus_url`,
  `glance_hosts`, `glance_version`, service IP vars) in `group_vars`, then
  `ansible-playbook playbooks/provision-glance.yml --limit oneill`. Never edit the live config by
  hand — the playbook stages + `config:print`-validates the render, then promotes it (a bad render
  can't break the running dashboard) and overwrites the live file each run.
- **Health/restart:** `pct exec 115 -- systemctl status glance`; `... journalctl -u glance -n 50`;
  `... curl -fsS -o /dev/null -w '%{http_code}' http://localhost:8080/` (expect `200`); content:
  `curl -fsS http://YOUR_GLANCE_IP:8080/api/pages/overview/content/` and
  `curl -fsS http://YOUR_GLANCE_IP:8080/api/pages/infrastructure/content/` (neither should contain `ERROR`).
- **A metric/status pane is empty or red:** a `custom-api` pane needs Prometheus (CT 114) reachable
  — check it first; a `monitor` tile red means that service is unreachable; for self-signed HTTPS
  tiles (Proxmox/PBS/UniFi) the template sets `allow-insecure: true` + `alt-status-codes`.
- **Recovery:** stateless → reprovision (RTO ~10 min). Bumping Glance: change `glance_version`,
  re-run, eyeball the page (pre-1.0 config-key renames — see ADR-014).
- **Not this:** graphs/history → Grafana; household wall-tablet control → Home Assistant (Phase 5 HA-expansion).

---

## Patching & updates (ADR-015)

- **Apt guests (auto security):** `provision-patching.yml` puts **`unattended-upgrades`** on every
  running CT (discovered via `pct list`) plus Ubuntu VMs 100/118/125. HAOS remains excluded. Policy:
  **security-only** (Debian security/point-release defaults; Ubuntu security plus release-pocket
  dependencies; never `-updates`), **no auto-reboot**,
  applied at **12:00 local** (`patching_timezone`, pinned in the systemd calendar so the UTC CTs
  still fire at local noon), **ntfy on failure** (OnFailure hook → your topic). **`needrestart`
  (mode `a`)** auto-restarts services on updated libs so the patch takes effect immediately. LXCs
  **never need a manual reboot** because they share the host kernel. Ubuntu VMs can require a
  real-kernel reboot, but that remains a deliberate monthly action.
  - Apply/refresh: `cd homelab/ansible && ansible-playbook playbooks/provision-patching.yml --ask-become-pass`
    (idempotent; all PVE hosts + the three Ubuntu VMs).
  - Check a guest: `pct exec <ctid> -- systemctl list-timers apt-daily-upgrade.timer` (next = local noon);
    `pct exec <ctid> -- unattended-upgrade --dry-run` (shows allowed origins + candidates).
  - Check an Ubuntu VM: `systemctl list-timers apt-daily-upgrade.timer`; `sudo unattended-upgrade --dry-run`.
  - Logs: `/var/log/unattended-upgrades/` inside the target. A failure pushes an ntfy alert.
  - Visibility: the daily maintenance collector on each PVE host reports enrollment, all pending
    packages, security-classified pending packages, and last unattended-upgrades activity. A new
    CT that was not enrolled turns the Glance Maintenance State pane red and raises
    `GuestPatchEnrollmentMissing` after one hour.
  - Glance semantics: **Automatic at daily patch window** means leave security updates to
    `unattended-upgrades`; **Monthly action** means ordinary packages or a PVE-host update should be
    handled in the planned window; **Action required** means automatic patching is overdue, enrollment
    is missing, or a deliberate reboot is outstanding. Security updates become overdue only after the
    existing three-day alert threshold, avoiding a false emergency before the next daily run.
- **PVE hosts + remaining Ubuntu work (manual):** deliberate **monthly window — last day of month,
  12:00 AEST** (be present for fallout). One node at a time via
  **`update-pve-host.yml --limit <host>`** (upgrades +
  reports reboot need; add `-e do_reboot=true` to reboot in-window), order **oneill → carter →
  apophis** (apophis last — it holds mgmt-vm + the HA VM, so **its reboot is out-of-band**; never run
  it as one block — see the per-host steps + danger box below). Ubuntu VM **non-security updates and
  reboots** are handled by hand. A persistent mgmt-vm timer sends an ntfy reminder at the
  start of the window; open Glance's **Maintenance State** pane and Renovate PRs from that reminder.
- **Ubuntu VMs (100 mgmt-vm, 118 vaultwarden, 125 jellyseerr):** security updates now auto-apply at
  local noon. Ordinary Ubuntu packages and any required reboot wait for the monthly window. Docker
  images on 118/125 remain pinned and are bumped separately (see below).
  After 125 reboots, confirm Gluetun's VPN egress ≠ home WAN.
- **HAOS:** update via the HA UI on your cadence; take/confirm a partial backup first (ADR-012).
- **Note (PBS repo):** the PBS CT must stay on `pbs-no-subscription` — `provision-pbs.yml` disables
  the shipped `pbs-enterprise` repo (it 401s and breaks `apt-get update` / unattended-upgrades).
- **Proxmox host repos:** fresh nodes ship the enterprise repos (401 without a sub) → switch to
  `pve-no-subscription`. Now codified: `provision-host-base.yml` (or `provision-host.yml`, which
  runs it first). See the [Host rebuild — ordered recipe](#host-rebuild--ordered-recipe).

> **Why hosts and Ubuntu VMs can still show a pile of updates:** only guest **security** updates run
> daily. PVE packages and ordinary Ubuntu updates batch monthly, so they accumulate between windows.
> Normal — Glance separates the security count so overdue exposure is visible independently.

### Run it yourself — ONE tier at a time (never as a single block)

> ⚠️ **Do not run the whole cycle as one script.** Two operations below can take the lab down if
> chained blindly — a real incident on **2026-07-07** did exactly that (rebooting the DNS host broke
> name resolution lab-wide, then a from-mgmt-vm apophis reboot killed the control node + dropped
> cluster quorum, forcing a power-cycle). Run each host as its own deliberate step and **verify
> recovery before moving on.**
>
> **The two hard rules:**
> 1. **apophis reboot is OUT-OF-BAND only.** apophis hosts **mgmt-vm (where you run this) + the HA
>    VM**, and is half the 2-node cluster. Rebooting it kills your control node *and* drops the
>    cluster to 1/2 votes → carter's `/etc/pve` goes **read-only** (looks online, won't manage). Do
>    it from the **Proxmox console/IPMI**, not SSH-from-mgmt-vm, and give carter a temporary
>    single-vote quorum first (see below).
> 2. **Never reboot the DNS-hosting node (oneill → CT 111) without checking the secondary first.**
>    Rebooting oneill drops primary DNS; resolution then leans on CT 117 (carter). If failover isn't
>    clean, every `ssh root@<host>` starts failing with *"Temporary failure in name resolution".*
>    (Underlying fix TODO: make resolvers list BOTH Technitium instances so either can reboot cleanly.)

| Tier | Cadence | Reboot? | Tool |
|------|---------|---------|------|
| Guest LXCs | security auto, daily 12:00 local; other monthly | never (share host kernel) | `unattended-upgrades` |
| PVE hosts (oneill/carter/apophis) | manual, monthly | only if kernel/PVE | `update-pve-host.yml` |
| Ubuntu VMs (100, 118, 125) | security auto daily; other monthly | deliberate if kernel | `unattended-upgrades` + monthly `sudo apt` |
| HAOS (200) | manual, your cadence | yes (appliance) | HA UI |
| Docker images (pinned) | manual, deliberate | n/a | bump digests |

**Apt guests — automatic security.** Re-run after adding a CT/Ubuntu VM, or to force one target:
```bash
cd ~/homelab/ansible
ansible-playbook playbooks/provision-patching.yml --ask-become-pass  # enrol CTs + VMs 100/118/125
pct exec <ctid> -- unattended-upgrade -v                 # (optional) force one now
sudo unattended-upgrade -v                              # on an Ubuntu VM; optional immediate run
```

**PVE hosts — one at a time, verify between each.** Upgrade first (safe from mgmt-vm); reboot is a
separate, in-window decision. **All `ansible-playbook` commands below run from `~/homelab/ansible`.**

*oneill (standalone; hosts primary DNS CT 111 + PBS/monitoring/glance/portal):*
```bash
ansible-playbook playbooks/update-pve-host.yml --limit oneill                    # upgrade only
dig @<carter-ct117-ip> github.com +short                                         # confirm secondary DNS answers BEFORE reboot
ansible-playbook playbooks/update-pve-host.yml --limit oneill -e do_reboot=true  # reboot (in-window; drops DNS/PBS ~2-3m)
ssh root@oneill 'pveversion; pct list'                                           # verify: all 6 CTs (incl. 111) running
```

*carter (clustered):*
```bash
ansible-playbook playbooks/update-pve-host.yml --limit carter
ansible-playbook playbooks/update-pve-host.yml --limit carter -e do_reboot=true  # in-window
ssh root@apophis 'pvecm status | grep Quorate'                                   # expect Quorate once carter returns
```

*apophis (LAST — SPECIAL, out-of-band reboot):*
```bash
ansible-playbook playbooks/update-pve-host.yml --limit apophis                   # upgrade packages ONLY (no reboot)
# If it needs a reboot, do NOT reboot from mgmt-vm. At the Proxmox console/IPMI:
#   1. reboot apophis from its console. mgmt-vm + HA VM drop with it; carter loses quorum and
#      /etc/pve becomes read-only. Carter GUI/TOTP login also FAILS while quorum is absent, but its
#      running guests (incl. CT 117 DNS) keep serving, and DNS stays up on oneill.
#   2. when it's back:   ssh root@apophis 'pvecm status | grep Quorate'   # auto-restores to 2 votes
# RECOVERY ACCESS (verified 2026-07-18):
#   - mgmt-vm normally reaches Carter as root, but mgmt-vm is hosted by apophis and disappears with it.
#   - Carter has an independent operator-desktop key in root's node-local authorized_keys. Direct
#     desktop-to-Carter root SSH was tested successfully on 2026-07-18. Recheck with:
#     ssh root@carter 'hostname; pvecm status'
#   - Away from home, the LAN remains reachable through the HA subnet router CT 126 on oneill if
#     CT 110/apophis is down. Subnet routing does not provide SSH authentication: the remote client
#     still needs its own Carter-authorized key. Never copy the desktop private key to another device.
#   - Proposed keyless remote recovery is Tailscale directly on Carter with operator-only Tailscale
#     SSH policy. It is not deployed; treat it as a separate security/host change and test before use.
# NOTE: do NOT run `pvecm expected 1` as a pre-step — corosync rejects lowering expected below the
#       live vote count (CS_ERR_INVALID_PARAM). It is a RECOVERY step ONLY, valid once apophis is
#       actually down (carter = 1 live vote): if apophis does not return promptly or you need the
#       Carter GUI, SSH from the operator desktop and run `ssh root@carter 'pvecm expected 1'`. Confirm
#       apophis is truly down first; never do this for an uncertain network partition.
# ACCEPTED: manual quorum recovery is the intended 2-node operating model. No QDevice is planned.
```

**mgmt-vm — monthly non-security packages / deliberate reboot (control node):**
```bash
sudo apt update && sudo apt full-upgrade                 # reboot if it asks (ends any live SSH/agent session)
sudo systemctl start homelab-maintenance.service         # refresh Glance immediately if not rebooting yet
# stuck dpkg lock (D-state unattended-upgr = unkillable) → reboot the VM:
#   sudo systemctl stop apt-daily.timer apt-daily-upgrade.timer apt-daily.service apt-daily-upgrade.service
#   last resort: from apophis -> qm reset 100
```

**Docker OS-VMs (118, 125) — monthly non-security packages, one at a time:**
```bash
ssh simon@YOUR_VAULTWARDEN_IP 'sudo apt update && sudo apt full-upgrade -y && sudo systemctl reboot'   # 118
ssh simon@YOUR_JELLYSEERR_IP  'sudo apt update && sudo apt full-upgrade -y && sudo systemctl reboot'   # 125
ssh simon@YOUR_JELLYSEERR_IP  'sudo docker ps; sudo docker exec gluetun wget -qO- https://api.ipify.org'  # egress != home WAN
```

The maintenance collector runs three minutes after boot. If an OS VM does not need a reboot, refresh
its dashboard state immediately with `sudo systemctl start homelab-maintenance.service`.

**HAOS (200):** HA UI → partial backup (ADR-012) → Settings → Updates.
**Docker images (pinned):** Renovate proposes tag/digest changes against the committed
`all.yml.example`; review the upstream release notes, copy the accepted value into the gitignored
live `all.yml`, and re-run the owning provision play. Renovate never automerges or deploys. The
repository-side `renovate.json` is ready; proposal PRs begin only after the Renovate GitHub App is
enabled for this repository.

### Maintenance visibility — deploy or refresh

The collector is read-only. It can count packages and compare kernels but cannot upgrade or reboot:

```bash
cd ~/homelab/ansible
ansible-playbook playbooks/provision-maintenance-monitoring.yml --ask-become-pass  # PVE + Ubuntu VMs + monthly reminder
ansible-playbook playbooks/provision-monitoring.yml              # scrape Ubuntu VMs + load alert rules
ansible-playbook playbooks/provision-glance.yml --limit oneill   # render Maintenance State
```

The become prompt is for the local `simon` account on mgmt-vm. The playbook never patches or reboots;
its monthly timer only sends the operator reminder.

On PVE, `/var/run/reboot-required` is often absent after a kernel upgrade. The collector therefore
uses the same reliable rule as `update-pve-host.yml`: **running kernel != newest installed `-pve`
kernel** means a reboot is required. This is only a status signal. `update-pve-host.yml` still does
not reboot unless `-e do_reboot=true` is explicitly supplied, and apophis reboot remains an
out-of-band operation per the danger box above.

Useful checks:

```bash
systemctl start homelab-maintenance.service
cat /var/lib/prometheus/node-exporter/homelab_maintenance.prom
systemctl list-timers homelab-maintenance-reminder.timer  # on mgmt-vm; confirm next monthly reminder
curl -s 'http://YOUR_MONITORING_IP:9090/api/v1/query?query=homelab_reboot_required'
```

---

## Backups (PBS + Home Assistant) — ADR-012

**oneill is the backup hub.** Two layers, local cross-host (cloud off-site deferred).

### PBS — whole VM/CT images
- **PBS** runs as unprivileged CT **112** on oneill (`YOUR_PBS_IP`), datastore `main` on a
  bind-mounted ZFS dataset `rpool/data/pbs-datastore` (quota 150 G). UI: `https://YOUR_PBS_IP:8007`.
  Provisioned by `provision-pbs.yml` (`--limit oneill`).
- **apophis → PBS wiring** (one-time, done live; recorded here for rebuild):
  - PBS API token `root@pam!apophis` with role **DatastorePowerUser** on `/datastore/main`
    (backup + prune for retention) — `proxmox-backup-manager user generate-token` + `acl update`
    inside CT 112.
  - apophis storage `pbs-oneill` added with that token + the datastore **fingerprint**
    (`proxmox-backup-manager cert info` on PBS).
- **Scheduled cluster job:** **VM 100 (mgmt-vm) + VM 118 (vaultwarden) + VM 127 (Actual)** →
  `pbs-oneill`, daily **02:30**, snapshot mode, retention **keep-daily 7 / keep-weekly 4**.
  `provision-actual.yml` idempotently enrols VM 127 and takes its first image immediately.
  A cluster backup job follows each selected VM to its current node; a separate Carter schedule is
  unnecessary. CTs and HA are **excluded** — CTs rebuild from playbooks and HA uses the native
  partial below. The imaged VMs contain state that Ansible cannot reproduce.
- **GC:** datastore `main` runs garbage collection daily.
- **Encryption (2026-06-17, ADR-012):** client-side encryption is **on** (`pvesm set pbs-oneill
  --encryption-key autogen`) — backups are encrypted before leaving apophis. The key lives at
  `/etc/pve/priv/storage/pbs-oneill.enc` (a credential — **never** committed) and a copy + its
  fingerprint are in **Google Password Manager**. **DR:** to restore on replacement hardware you
  must first put that key file back at `/etc/pve/priv/storage/pbs-oneill.enc` — no key, no restore.
  The pre-encryption `…T16:30:03Z` snapshot remains unencrypted as a fallback.

#### Restore a guest from PBS
```bash
ssh root@YOUR_PROXMOX_IP "pvesm list pbs-oneill"                                            # list points
ssh root@YOUR_PROXMOX_IP "qmrestore pbs-oneill:backup/vm/118/<ISO-timestamp> <newvmid>"     # Vaultwarden
ssh root@YOUR_CARTER_IP "qmrestore pbs-oneill:backup/vm/127/<ISO-timestamp> <newvmid>"       # Actual Budget
# CTs are reprovisioned from Ansible, NOT restored from PBS (no CT is in the backup job).
```

### Home Assistant — native partial backup (primary for HA)
- HA protects itself via a **scheduled partial backup** (Settings → System → Backups). Written
  to the **Samba/CIFS share on oneill** (CT 113, `//YOUR_HA_BACKUP_SHARE_IP/ha-backups`, user
  `habackup`) added in HAOS as network storage. Portable — restores onto any HAOS.
- **Backup location must be the share**, not just "this device" — confirm the automatic backup
  writes to oneill (files land in CT 113 `/srv/ha-backups`), otherwise it only stays local.
- **Selection (keep current as you add apps):** HA config + the **stateful add-ons** —
  Zigbee2MQTT (critical: avoids re-pairing), Mosquitto, Cloudflared, etc. **media excluded**;
  recorder DB kept small via `recorder` `purge_keep_days` (~10–14). ⚠️ **When you add a new
  stateful add-on, add it to the partial-backup selection** — it isn't picked up automatically.
- **Status (2026-06-17):** automatic partial backup **confirmed landing** on the share (CT 113,
  recurring, ~131 MB). Scope verified from `backup.json`: HA core + Zigbee2MQTT + Mosquitto +
  Cloudflared, compressed, no media. The mgmt-vm `vzdump-qemu-100` interim images on apophis `local`
  were **deleted** (PBS covers mgmt-vm off-box). **`vzdump-qemu-200` (HA) retired 2026-06-18** — the
  partial backup was proven restorable end-to-end (see Restore drills below), so the whole-VM
  fallback is no longer needed. No `vzdump-qemu` images remain on apophis `local`.
- **⚠️ Encryption key:** HAOS backups are **encrypted** (`"protected": true` in `backup.json`). The
  key (HAOS → Settings → System → Backups → ⋮ → "Show encryption key") **must be stored off-box** —
  losing it makes every encrypted backup unrestorable. It's a **Tier 2 anchor (ADR-018)** — it stays
  in Keychain/Google Password Manager, deliberately **outside** Vaultwarden so recovery is non-circular
  (Vaultwarden may itself be down). Vaultwarden is now live (VM 118, Phase 5) but Tier 2 secrets do not move into it.

### Recovery model — what recovers what (avoid doubling up)

Principle: **back up what code can't recreate.** Most services rebuild from git, so they
don't need image backups — only genuinely stateful or hand-built things do.

| Layer | Recreates | Lives |
|---|---|---|
| Ansible playbooks | **the LXCs end-to-end** — `pct create` + config (Tailscale, Technitium, PBS, share) | git (public) |
| Private repo (ADR-007) | real inventory/group_vars/host_vars, `.claude` | git (private) |
| PBS images | **mgmt-vm** (hand-built) + **vaultwarden VM 118** + **Actual VM 127** (stateful Docker data) | oneill |
| HA native partial | HA config + Zigbee2MQTT + add-ons (restore onto a fresh HAOS) | oneill share |
| Terraform (ADR-008) | **planned** — declarative VM/LXC definitions; not yet imported (empty scaffold) | git (public) |

**Reality check (2026-06-16):** Terraform manages nothing yet (no state) — the four LXCs are
created **and** configured by their Ansible playbooks today (re-run to rebuild). The CTs are
deliberately not in PBS (the playbooks rebuild them). **mgmt-vm, the HA VM, Vaultwarden (VM 118),
and Actual (VM 127) are the exceptions — none is fully recreatable from code:** mgmt-vm relies on its PBS image; HA
relies on manually creating a HAOS VM then restoring the native partial; Vaultwarden's playbook
rebuilds the VM+container but its vault data comes from the PBS image (or carter replica); Actual's
playbook rebuilds the VM+container but its finance data comes from PBS or the portable ZIP. VM 118's
PBS restore path is **proven ✅ 2026-06-26** and VM 127's is **proven ✅ 2026-07-15** (see Restore drills table). The playbook rebuild path is unproven
until the **CT 111 reprovision drill** (pending) actually runs it.

**Restore by scenario:**
- **A guest is lost/corrupted:** reproducible service → re-run its playbook; mgmt-vm (or any
  quick full restore) → `qmrestore` / `pct restore` from `pbs-oneill`; HA → restore its
  partial backup from the share onto HAOS.
- **oneill (backup hub + simple services) dies:** production is unaffected if apophis is up
  (oneill holds Technitium, PBS, the HA share, and monitoring — all rebuildable from code).
  Rebuild: fresh PVE + ZFS → **switch to the PVE no-subscription repo** (a fresh PVE 9 ships
  the enterprise repos, which 401 without a subscription and break `apt`; disable
  `pve-enterprise`/`ceph` `.sources` and add a `pve-no-subscription.sources`) → `ssh-copy-id`
  → re-run `install-node-exporter.yml`, `provision-technitium.yml`, `provision-pbs.yml`,
  `provision-ha-backup-share.yml`, `provision-monitoring.yml`. **The backup data on oneill is a
  single copy** — protected only once the off-site sync exists; an oneill SSD failure today
  loses restore history, not production.
- **apophis dies:** its guests' images are safe on oneill → restore to replacement hardware.
- **Both / site disaster:** infra rebuilds from git (Terraform + Ansible + private repo); VM
  *data* is lost until the off-site copy exists — the deferred-off-site gap.

**Backing up the hub itself:** don't copy oneill's backups to apophis (circular, same-site).
The backups are protected by the **off-site copy** (ADR-012 deferred leg — encrypted sync of
both datasets to cloud). That, not a second local copy, is "backing up oneill."

### Restore drills (a backup you haven't restored is a hypothesis)

Safe pattern for the mgmt-vm PBS restore (mgmt-vm is the box you're on — **never** boot a clone
with networking, or it fights the live VM for its IP):

```bash
# on apophis. 199 = throwaway VMID; --unique regenerates the MAC.
qmrestore pbs-oneill:backup/vm/100/<UTC-timestamp> 199 --unique 1 --storage local-lvm
qm set 199 --delete net0          # strip NIC so it can't conflict with live mgmt-vm
qm start 199
qm agent 199 ping                 # agent up ⇒ the clone booted to a working OS
qm guest exec 199 -- /bin/ls /home/simon/homelab/ansible/inventory/group_vars/   # real config present?
qm stop 199 && qm destroy 199 --purge
```

**HA native partial restore (operator-guided).** HAOS restore is UI-driven, and the restored
Zigbee2MQTT **must not touch the live SLZB-06 coordinator** (two Z2M instances on one coordinator
disrupts production), so the test HA is **isolated**. Procedure (done 2026-06-18):

1. **Isolated test VLAN.** A dedicated VLAN (its own `/24`, its own UniFi zone): **Test→External =
   Allow, Test→all internal = Block** — critically including the **Unsecure zone** (where the IoT/
   coordinator lives; the zone matrix must show `Test → Unsecure = Block All`). Add a one-way
   **Secure→Test, TCP 8123, Allow + "Auto Allow Return Traffic"** (ordered above the blocks) so your
   browser reaches the test HA UI without opening Test→internal. (The return path matters: Test→Secure
   is blocked, so without "Auto Allow Return" the SYN-ACK is dropped and `:8123` times out.)
2. **Throwaway HAOS VM** on apophis, mirroring prod (OVMF/q35 + EFI disk, 2 cores/3 GB), NIC on the
   test VLAN tag, from the latest HAOS `ova` image:
   ```bash
   curl -fsSL -o /var/lib/vz/haos.qcow2.xz <haos_ova-*.qcow2.xz>; unxz /var/lib/vz/haos.qcow2.xz
   qm create 299 --name ha-restore-test --bios ovmf --machine q35 --cores 2 --memory 3072 \
     --net0 virtio,bridge=vmbr0,tag=<TEST_VLAN> --scsihw virtio-scsi-pci --serial0 socket \
     --ostype l26 --efidisk0 local-lvm:0,efitype=4m,pre-enrolled-keys=0 --agent 1 --onboot 0
   qm importdisk 299 /var/lib/vz/haos.qcow2 local-lvm
   qm set 299 --sata0 local-lvm:vm-299-disk-1 --boot order=sata0 && qm start 299
   qm agent 299 network-get-interfaces   # read the test HA's DHCP IP on the test VLAN from this
   ```
   Check `ha core info` / `ha network info` on the Proxmox console: Core version should match prod,
   `host_internet/supervisor_internet: true` (so it can pull Core + add-on images).
3. **Get the backup to your browser** — the isolated test HA can't reach the share, so serve the
   latest `.tar` over HTTP from a **Home-subnet** host and download it in your browser:
   ```bash
   # on oneill (backup-hub host); the file lives in CT 113
   mkdir -p /tmp/harestore && pct pull 113 /srv/ha-backups/<latest>.tar /tmp/harestore/ha-backup.tar
   systemd-run --unit=harestore-http --collect --working-directory=/tmp/harestore \
     /usr/bin/python3 -m http.server 8000 --bind 0.0.0.0
   # browser → http://<oneill-ip>:8000/ha-backup.tar  (encrypted; key entered at restore time)
   # after download: systemctl stop harestore-http; rm -rf /tmp/harestore
   ```
4. **Restore** at `http://<test-ip>:8123` → onboarding **"Restore from backup"** → upload the `.tar`
   → enter the **encryption key** (Google Password Manager) → full restore (~5–10 min, re-pulls add-ons).
5. **Verify**: log in with prod credentials; dashboards/entities present; **Zigbee devices listed**
   (Settings → Devices, count ≈ prod ⇒ the **Z2M pairing database restored**). Z2M logging
   "can't connect to coordinator" is **expected** (isolated) — we prove the *database*, not live radio.
6. **Teardown**: `qm stop 299 && qm destroy 299 --purge`; `rm` the HAOS image; stop the temp server.

| Date | Backup tier | Result |
|------|-------------|--------|
| 2026-06-17 | PBS mgmt-vm (VM 100) | ✅ PASS — restored 24 s, booted, `group_vars/all.yml` + git repo present |
| 2026-06-18 | HA native partial → fresh HAOS (isolated VLAN 5) | ✅ PASS — encrypted backup restored into HAOS 17.3, config/entities + **Zigbee device DB** present. Held `vzdump-qemu-200` retired. |
| 2026-06-25 | **VM 200 `pvesr` failover (apophis→carter)** | ✅ PASS — disabled job 200-0, `zfs clone` of the latest `__replicate__` snapshot → **no-network** test VM 299 on carter; HAOS **booted off the replicated copy** (~1 GB read / 119 MB written, CPU climbing). Procedure validated (clone→create→start). Live HA untouched; clones+VM destroyed; replication re-enabled + re-synced OK. *Bootability proven non-destructively; full app-on-network is the real failover's job (uses VM 200's own config/IP).* |
| 2026-06-26 | **PBS image of VM 118 (Vaultwarden)** | ✅ PASS — `qmrestore` of the 02:01Z image → throwaway VM 119 (NIC stripped, never on the tailnet), restored in 11 s. Guest agent up; `/opt/vaultwarden/data/db.sqlite3` present (272 KB, non-zero) + `rsa_key.pem` intact. 119 destroyed; live 118 untouched. **Vault recovery is now proven, not a hypothesis.** |
| 2026-07-15 | **Encrypted PBS image of VM 127 (Actual Budget)** | ✅ PASS — restored the data-bearing 05:22Z image to throwaway VM 197 on Carter, removed its NIC before boot, and verified the account database, non-empty budget files, and Compose definition. RTO 155 s. VM 197 destroyed; live VM 127 remained running. **Finance-state recovery is proven.** |
| _pending_ | CT 111 / CT 117 Ansible reprovision | untested — records the real RTO |
| _pending_ | CT 123 (Sonarr) Ansible reprovision | untested — simplest Phase 7 drill (no VPN credential dep); re-add qBit + root folder, verify hardlink import |
| _pending_ | CT 124 (Radarr) Ansible reprovision | untested — same drill path as Sonarr |
| _pending_ | VM 125 (Jellyseerr + Prowlarr + ByParr) Ansible reprovision | untested — needs `prowlarr_vpn_wg_config` in `all.yml`; verify Prowlarr egress = ProtonVPN after rebuild |

> **Timezone note:** apophis runs **AEST (UTC+10)**. Backup-job schedules (e.g. `02:30`) are
> local; PBS snapshot names are **UTC** (`…T16:30:03Z` = 02:30 AEST). Don't mistake the offset
> for a missing run.

---

## Power-loss & autostart resilience (ADR-009)

This lab uses **manual failover, not the Proxmox HA manager** (ADR-009 — automatic HA is unsafe on a
single-network-path lab). So a host's own auto-recovery after a reboot/power event is what keeps
services up. Two independent things must both be true: the **host powers itself back on**, and its
**guests start automatically**.

### A. Per-host: power on after AC loss

After a power blip, a host only comes back if its firmware is set to power on. How to check/set it:

- **apophis (ThinkCentre M720q) / carter (ThinkStation P330 Tiny) — REMOTE, no console needed.** Recent kernels expose the
  Lenovo BIOS via the `thinklmi` driver, so set it over SSH (no BIOS password is set here):
  ```bash
  base="/sys/class/firmware-attributes/thinklmi/attributes/After Power Loss"
  cat "$base/current_value"                  # Power On / Power Off / Last State
  printf "Power On" > "$base/current_value"   # set it; applies on the next power event
  ```
  (If an Admin BIOS password is ever enabled — `.../authentication/Admin/is_enabled` = 1 — write it
  to `.../authentication/Admin/current_password` first.) **apophis set to "Power On" 2026-06-22;
  carter verified "Power On" 2026-07-14.**
- **oneill (KAMRUI Essenx E2 N150, AMI Aptio BIOS) — NO remote interface** (`/sys/class/firmware-attributes/`
  absent). ✅ **FIXED 2026-06-22.** Root cause: BIOS **"State After G3" = S5** (stay off after power
  loss); changed to **S0** (power on) — confirmed self-boots on AC restore. On this board the setting
  is under **"State After G3" (S0/S5)**, *not* "Restore AC Power Loss"; if you're back in this BIOS,
  also check **Deep Sleep/ErP = Disabled**. Entry key: Del (try F2/Esc). No remote/SSH path for it.
- **UPS:** confirm the UPS also feeds the **network device** (gateway/switch) — else a blip still
  causes the common-mode outage ADR-009 warns about.

#### Oneill firmware baseline (2026-07-14)

The purchase record identifies Oneill as a **KAMRUI Essenx E2**, Twin Lake-N N150, 16 GB DDR4 and
512 GB M.2 SSD; that configuration also matches
[KAMRUI's E2 product page](https://kamrui.com/products/kamrui-essenx-basic-e2). Its SMBIOS identity
fields all contain `Default string`, so Linux alone cannot identify its manufacturer, product, SKU,
family, or baseboard. The installed AMI BIOS is **`TWL_P0_AK_10_0108_AMI.15W` (2025-01-17)**,
revision 5.27. It runs PVE 9.2.4 and kernel
`7.0.14-4-pve` in UEFI mode. Secure Boot is disabled and the platform is in Setup Mode (no enrolled
platform key); this is recorded state, not a reason to enable Secure Boot during routine maintenance.

| Setting / capability | Verified value |
|---|---|
| Boot mode | UEFI; ZFS root |
| Secure Boot | Disabled; platform in Setup Mode |
| CPU virtualization | VT-x exposed |
| Firmware settings from Linux | None (`/sys/class/firmware-attributes/` absent) |
| State After G3 | S0 / power on; set and AC-restore tested 2026-06-22 |
| Active watchdog | Software Watchdog (`softdog`), 10-second timeout, `nowayout=0` |
| Chipset watchdog candidate | Alder Lake-N PCH; `iTCO_wdt` module available but untested/not loaded |
| Wired NIC wake | Supported, but disabled (`Wake-on: d`) |

**Do not flash Oneill from a BIOS image inferred from the BIOS version string.** The purchase record
establishes the E2/N150 model, but the blank SMBIOS still prevents the machine from validating an
image itself. Before any update, obtain an image and checksum from KAMRUI support with explicit
confirmation that it applies to the Essenx E2 N150 and current `TWL_P0_AK` firmware family. The
2025 BIOS date creates no immediate update pressure in the absence of a model-specific security
advisory or a firmware fault. Loading or testing `iTCO_wdt` is a separate controlled maintenance
task; module availability alone does not prove the watchdog is usable.

#### Carter firmware baseline before the planned update (2026-07-14)

Carter was previously documented as an M920q; DMI confirms it is a **ThinkStation P330 Tiny**, type
`30CE`, machine type/model `30CES0DW00`, with an i5-8500. It runs PVE 9.2.4 and kernel
`7.0.14-4-pve`. The installed BIOS is **`M1UKT23A` (2018-12-05)**. Lenovo's model-compatible,
recommended release is [M1UKT79A (2026-03-30)](https://support.lenovo.com/ag/en/downloads/DS503907),
available as bootable ISO `m1uj979usa.iso`; use the checksum shown by Lenovo at download time.

Record these values again immediately before flashing and restore them if the update resets setup:

| Setting | Verified value |
|---|---|
| Boot mode / CSM | UEFI Only / Disabled |
| Secure Boot | Disabled |
| Primary boot sequence | M.2 Drive 1 first; Linux Boot Manager is current EFI entry |
| SATA | Controller enabled; AHCI |
| Intel Virtualization Technology / VT-d | Enabled / Enabled |
| Core multiprocessing / Turbo / EIST | Enabled / Enabled / Enabled |
| C-state support | C1/C3/C6/C7/C8 |
| Security chip | TPM 2.0 enabled; discrete TPM selected |
| After Power Loss | Power On |
| Wake on LAN / NIC wake | Automatic / magic-packet enabled |
| PXE | Option ROM plus IPv4/IPv6 stacks enabled; after local storage in primary sequence |
| OS Optimized Defaults | Enabled |
| BIOS rollback | Allowed |
| BIOS administrator password | Not enabled |
| Windows UEFI firmware updates | Enabled |

The active watchdog remains **Software Watchdog (`softdog`)**, timeout 10 seconds, `nowayout=0`;
there is no proven hardware-backed watchdog. Do not load or experiment with `iTCO_wdt` during the
firmware window. The upgrade from 23A to 79A is strongly justified: Lenovo's cumulative changelog
includes security fixes, CPU microcode, NVMe detection/support, POST-hang fixes, and BIOS-update
reliability changes. Before taking either cluster node down, confirm SSH access to the survivor and
keep `pvecm expected 1` available as a recovery-only step. Update one Lenovo per maintenance window
with a local display and power control available.

### B. Per-guest: autostart + ordering

Check every guest auto-starts and in a sane order (DNS first → dependencies → HA VM). Audit current
state per host:

```bash
# VMs
for v in $(qm list | awk 'NR>1{print $1}'); do echo "VM $v:"; qm config $v | grep -E 'onboot|startup' || echo '  (no onboot/startup → defaults: onboot off)'; done
# CTs
for c in $(pct list | awk 'NR>1{print $1}'); do echo "CT $c:"; pct config $c | grep -E 'onboot|startup' || echo '  (no onboot/startup)'; done
```

Set autostart + ordering (lower `order` starts first; `up=` is a post-start delay in seconds):

```bash
qm set <vmid> --onboot 1 --startup order=3,up=30      # e.g. HA VM: later, after DNS
pct set <ctid> --onboot 1 --startup order=1,up=10      # e.g. Technitium: first
```

Suggested order: Technitium/DNS = 1 → Tailscale/PBS/monitoring = 2 → Home Assistant VM = 3.

### C. Verify (don't assume)

- **Autostart only** (safe, no power risk): reboot a non-critical guest's host in a window, or
  `qm stop` then reboot the host, and confirm guests come up unattended in order.
- **Full power-loss test** (the real proof): in a maintenance window, physically cut power to one
  host (or its UPS outlet) and confirm it powers back on **and** its guests autostart. Do one host
  at a time; never two (quorum). Record the result + recovery time here.

---

## Host rebuild — ordered recipe

**What runs, in order, to bring a reinstalled PVE node fully back.** The node-specific sections
below ([apophis 4b](#phase-4b-rebuild-apophis-on-zfs-one-time--infra-designer-reviewed-2026-06-22),
[carter DR](#rebuild-carter-the-failover-target--dr-runbook)) carry the cluster-join detail and
lessons; this is the master checklist so nothing is silently skipped (the NIC-hardening + watchdog
are easy to forget — that's the whole point of `provision-host.yml`).

**Split: some steps can't be codified (they precede or wrap Ansible), the rest are one command.**

| # | Step | How | Codified? |
|---|------|-----|-----------|
| 1 | Install PVE from ISO → **ZFS (RAID0)**, set hostname + network | at the console | ✋ manual (ISO installer) |
| 2 | Re-add the mgmt-vm root SSH key | `ssh-keygen -R <ip>` then `ssh-copy-id root@<ip>` from mgmt-vm | ✋ manual (bootstrap trust) |
| 3 | **Base host config** — no-sub repos, key-only SSH, node_exporter, NIC-hardening, net-watchdog | `ansible-playbook playbooks/provision-host.yml --limit <node>` | ✅ `provision-host.yml` |
| 4 | `apt dist-upgrade` the host | `ansible-playbook playbooks/update-pve-host.yml --limit <node>` | ✅ `update-pve-host.yml` |
| 5 | **Cluster join** (apophis/carter only — oneill is standalone) | `pvecm add …` on the node's TTY — **mind the 2FA join blocker** | ✋ manual — see per-node section |
| 6 | Storage + replication (cluster nodes) | `pvesm set local-zfs --nodes …`; `pvesr create-local-job …` | ✋ manual — see per-node section |
| 7 | **Node-specific guests/services** (below) | per-node playbooks | ✅ playbooks (secrets prompted) |

**Step 7 — which service plays to run, by node** (each is idempotent; secrets are pasted from
Vaultwarden at the prompt where noted):

| Node | Run after base |
|------|----------------|
| **apophis** | `provision-tailscale.yml --limit apophis` · `provision-deadmans-switch.yml` · `provision-patching.yml` · media plays (`provision-jellyfin/qbittorrent/sonarr/radarr/jellyseerr.yml`) |
| **carter** | `provision-technitium.yml --limit carter` (admin pw) · restore stateful VM 127 from PBS (or `provision-actual.yml` only for a clean deployment with no finance data) · `provision-patching.yml` |
| **oneill** | `provision-monitoring.yml` (Grafana pw) · `provision-tailscale.yml --limit oneill -e tailscale_ctid=126 …` (see [tailscale.md](../components/tailscale.md)) · `provision-technitium.yml --limit oneill` · `provision-pbs.yml` · `provision-ha-backup-share.yml` |

> **Note (cluster nodes):** most guest **config** returns automatically via cluster-shared
> `/etc/pve` on rejoin (users/2FA/ACLs/storage.cfg/VM configs) — the plays above rebuild the
> **node-local** bits (node_exporter, NIC/watchdog) and re-create guests that live only as code
> (Tailscale, Technitium). Imaged guests (VM 118 Vaultwarden) restore from PBS, not a play.

## Phase 4b: rebuild apophis on ZFS (one-time) — infra-designer-reviewed 2026-06-22

Goal: move apophis from LVM-thin to **ZFS-on-root** so it can host `pvesr`-replicated VMs for
manual failover (ADR-009). apophis hosts VM 100 (mgmt-vm, the Ansible/Claude host), VM 200 (HAOS),
CT 110 (Tailscale). Strategy: evacuate everything to **carter**, reinstall apophis on ZFS, rejoin,
migrate back, set up replication. HA stays up on carter throughout. **Do this in a maintenance
window**, one step at a time, honouring every VERIFY gate.

### Pre-flight gates (all must pass before the destructive step)
- **Migration method / CPU type.** Both VMs are `cpu: host`, which **blocks live migration**. Pick one:
  - *Live (zero-downtime move):* `qm set 100 --cpu x86-64-v2-AES` and `qm set 200 --cpu x86-64-v2-AES`, then **restart each VM** (stop/start, to apply), then live-migrate. Portable type is also correct cluster hygiene long-term. *(host is still fine for cold failover — only live migration needs this.)*
  - *Offline (simpler, brief downtime):* leave `cpu: host`, `qm shutdown`, then `qm migrate <id> carter --targetstorage local-zfs --with-local-disks`, then start on carter. ~2–3 min downtime per VM.
- **carter AC power-recovery** must be set to power-on (PLAN backlog) — carter is the *sole* host running production during the reinstall; if it loses power and stays off, both VMs are down with no path back.
- **PBS encryption key:** lives in cluster-shared `/etc/pve/priv/storage/` → carter retains a copy and it returns to apophis on rejoin, so the reinstall won't lose it. Still confirm an **off-box** copy exists (fingerprint `70:ed:…:79:81` in the password manager) as whole-cluster-loss insurance.
- **Fresh backups:** trigger a manual PBS backup of VM 100; confirm the latest HAOS native backup landed on CT 113 (<24h).
- **SSH trust:** cluster root keys return via shared `/etc/pve`; the **mgmt-vm's** root key is node-local → re-added in step 6 (`ssh-copy-id`). No need to hand-save it.

> **Key fact — `/etc/pve` is cluster-shared.** Reinstalling apophis wipes only its *node-local* state. On `pvecm add`, apophis pulls the cluster filesystem from carter, so **users, 2FA, ACLs, the monitoring PVE token, the PBS key, storage.cfg, and VM configs all return automatically.** Node-local things to redo: SSH host key, mgmt-vm's root authorized_key, no-sub apt repos, node_exporter.

### Sequence (VERIFY at each gate; rollback notes inline)
1. **Migrate VM 200 → carter** (`--targetstorage local-zfs`, with local disks). *Drive from the apophis GUI, not from inside mgmt-vm.* **VERIFY:** HA UI loads, Z2MQTT connected, Zigbee devices respond. *Rollback: migration is non-destructive — source stays until success; if it fails, 200 is still on apophis.*
2. **Migrate VM 100 → carter.** *Drive from a browser NOT inside mgmt-vm* (this session drops + reconnects; same IP via the UniFi MAC reservation). **VERIFY:** SSH to mgmt-vm works, `hostname`=mgmt-vm, git repo intact.
3. ~~**Rebuild Tailscale on oneill**~~ — **SKIPPED (2026-06-25): Tailscale stays on apophis** (decided; supersedes the earlier "→ oneill" intent). CT 110 was migrated carter→apophis during 4b instead. See execution notes below.
4. **Remove apophis from the cluster.** Power apophis off first, then on **carter**: `pvecm expected 1` (else carter, now 1/2, goes read-only) → `pvecm delnode apophis`. **VERIFY:** `pvecm status` on carter = Quorate, Expected 1; VMs 100+200 running on carter.
5. **Reinstall apophis** from the PVE 9.2.3 ISO → **ZFS (RAID0)** on the SSD, hostname `apophis`. Then re-add the mgmt-vm key (`ssh-keygen -R YOUR_PROXMOX_IP` + `ssh-copy-id root@YOUR_PROXMOX_IP`) and run the **codified base**: `ansible-playbook playbooks/provision-host.yml --limit apophis` (no-sub repos + key-only SSH + node_exporter + NIC-hardening + net-watchdog), then `update-pve-host.yml` for the dist-upgrade. **VERIFY:** boots, `pveversion`=9.2.3, `zpool list` shows rpool. *(This replaces the old by-hand repo switch — see [Host rebuild — ordered recipe](#host-rebuild--ordered-recipe).)*
6. **Rejoin (carter root has 2FA — cluster-wide):** from mgmt-vm `ssh-keygen -R YOUR_PROXMOX_IP` (clear apophis's old host key) then `ssh-copy-id root@YOUR_PROXMOX_IP` (re-add the node-local mgmt-vm key); on **apophis's shell (a TTY)** run `pvecm add YOUR_CARTER_IP` — enter carter's root pw **+ 2FA OTP** (the GUI/API join fails with 2FA, as when we first formed the cluster). On rejoin apophis pulls the cluster-shared `/etc/pve` → users/2FA/ACLs/monitoring-token/storage.cfg return automatically. **VERIFY:** `pvecm status` = 2 nodes, Quorate, Expected 2.
7. **Fix storage:** `pvesm set local-zfs --nodes apophis,carter` and `pvesm remove local-lvm` (apophis has no LVM now). **VERIFY:** local-zfs active on both.
8. **Migrate 100 + 200 back to apophis** (`--targetstorage local-zfs`). **VERIFY:** HA + mgmt-vm healthy on apophis.
9. **Verify monitoring resumes:** the PVE monitoring token is in cluster-shared `/etc/pve` → it returns on rejoin, so apophis's pve-exporter should auth automatically. **node_exporter** is node-local but already reinstalled by `provision-host.yml` at step 5 (re-run `install-node-exporter.yml --limit apophis` only if you skipped it). **VERIFY:** apophis node + pve-exporter targets up in Prometheus; only re-run `provision-monitoring.yml` if the pve target stays down.
10. **2FA — no re-enrollment needed:** root@pam + simon@pve TOTP lives in cluster-shared `/etc/pve/priv/tfa.cfg` and returns on rejoin. **VERIFY:** log into apophis's GUI with TOTP to confirm it works.
11. **Set up replication:** `pvesr create-local-job 200-0 carter --schedule '*/15'` then `pvesr run --id 200-0` (first full send). **VERIFY:** `pvesr status` shows job `200-0` State OK, FailCount 0; `zfs list -t snapshot` on carter shows a `__replicate__` snapshot. *(Note: the job ID is `<vmid>-<n>`, e.g. `200-0`; the older `pvesr create --guest …` form does not exist on PVE 9.)*

> **Execution notes — what actually happened on 2026-06-25 (corrections to the plan above):**
> - **Step order was violated:** apophis was physically pulled and reinstalled **before** `pvecm delnode` (step 4). carter then dropped to 1/2 and went **read-only**. Recovery: on carter `pvecm expected 1` → `pvecm delnode apophis` → `rm -rf /etc/pve/nodes/apophis` (stale node dir), which freed the name to rejoin. **Do step 4 first** — but if you slip, this is the recovery.
> - **Step 10's "2FA returns automatically, no re-enrollment" was WRONG in practice.** The cluster-shared TOTP *did* return, but the `pvecm add` TTY OTP prompt **kept returning `401 authentication failure`** for both `root@pam` and `simon@pve` — even with carter's clock NTP-synced (verified <1 s skew) and after a phone time-correction. Root cause was an authenticator/secret mismatch, not clock. **Fix that unblocked the join:** over SSH (key auth bypasses 2FA) `pveum user tfa delete root@pam --id <id>` to drop root's TOTP, after `cp -a /etc/pve/priv/tfa.cfg /root/tfa.cfg.bak.$(date +%s)`. `pvecm add` then needs only carter's root **password** (no OTP). **Afterwards, re-enroll fresh TOTP** for `root@pam` *and* `simon@pve` via Datacenter → Permissions → Two Factor (the old `simon@pve` secret was also stale — delete + re-add). Lesson: treat 2FA as a join blocker; have the SSH-removal path ready.
> - **Live-migration tunnel dropped intermittently** (`mirror-<disk>: Input/output error (io-status: ok)` then `writing to tunnel failed: broken pipe`) when running at near-line-rate on the shared **1 Gb** NIC — network itself was clean (0 % ping loss, corosync stable). **Fix:** cap with `qm migrate <vmid> apophis --online --with-local-disks --bwlimit 100000` (~80 MB/s ≈ 80 % of 1 Gb, leaving corosync headroom). First uncapped attempt failed ~24 %; capped retry completed. Apply the same `--bwlimit` to every cross-node migration on this single-NIC pair.
> - **CTs can't live-migrate** — CT 110 used `pct migrate 110 <node> --restart` (brief stop). zfspool→zfspool works fine now both nodes are ZFS (the old lvmthin→zfspool block is gone).
> - **Step 3 (rebuild Tailscale CT 110 on oneill) was skipped** — CT 110 was instead migrated to carter then back to apophis. **Keeping Tailscale on apophis is the accepted placement (decided 2026-06-25)** — the earlier "Tailscale → oneill" intent is superseded.

## Rebuild carter (the failover target) — DR runbook

carter is the `pvesr` replication + manual-failover target for **VM 200 (HA)** and **VM 118
(Vaultwarden)**, and hosts **CT 117 `technitium2`** (the 2nd DNS resolver) plus stateful **VM 127
`actual`**. A Carter loss leaves HA/Vaultwarden running on apophis, but **Actual is unavailable**
until its encrypted PBS image is restored to apophis or Carter returns. While Carter is down there is
also no failover target for VM 200/118 and DNS rides on CT 111 (oneill) alone. Do this in a maintenance
window. This mirrors the apophis 4b rebuild; the same lessons apply.

> **Key fact — `/etc/pve` is cluster-shared.** Reinstalling carter wipes only its *node-local*
> state. On `pvecm add`, carter pulls the cluster filesystem from apophis, so **users, 2FA, ACLs,
> the monitoring PVE token, the PBS key, storage.cfg, and VM configs return automatically.**
> Node-local to redo: SSH host key, mgmt-vm's root authorized_key, no-sub repos, node_exporter,
> the `local-zfs` node list, the replication jobs, and CT 117.

> **Prereq:** carter's BIOS **AC power-recovery = Power On** (verified 2026-07-14) — so an unattended
> power blip brings the failover target back by itself.

1. **Keep apophis writable.** A 2-node cluster minus carter is 1/2 → apophis goes **read-only**. On
   apophis: `pvecm expected 1`. **VERIFY:** `pvecm status` = Quorate, Expected 1; VMs 100/110/118/200
   still running on apophis.
2. **Remove carter from the cluster** (do this *before* wiping it). On apophis:
   `pvecm delnode carter`, then if the node dir lingers `rm -rf /etc/pve/nodes/carter`. **VERIFY:**
   carter gone from `pvecm status` and the GUI.
3. **Reinstall carter** from the PVE 9.2.3 ISO → **ZFS (RAID0)** on its SSD, hostname `carter`. Then
   re-add the mgmt-vm key (`ssh-keygen -R YOUR_CARTER_IP` + `ssh-copy-id root@YOUR_CARTER_IP`) and run
   the **codified base**: `ansible-playbook playbooks/provision-host.yml --limit carter` (no-sub repos
   + key-only SSH + node_exporter + NIC-hardening + net-watchdog), then `update-pve-host.yml` for the
   dist-upgrade. **VERIFY:** boots, `pveversion`, `zpool list` shows rpool.
   *(See [Host rebuild — ordered recipe](#host-rebuild--ordered-recipe).)*
4. **Rejoin — mind the 2FA join blocker.** apophis's `root@pam` has cluster-wide 2FA; the `pvecm add`
   OTP prompt **will likely fail `401`** (this bit us on the apophis join). Pre-empt it: from mgmt-vm
   (key auth bypasses 2FA) on **apophis** `cp -a /etc/pve/priv/tfa.cfg /root/tfa.cfg.bak.$(date +%s)`
   then `pveum user tfa delete root@pam --id <id>`. From mgmt-vm `ssh-keygen -R YOUR_CARTER_IP` +
   `ssh-copy-id root@YOUR_CARTER_IP`. On **carter's TTY**: `pvecm add YOUR_PROXMOX_IP` — now needs only
   apophis's root **password**. **VERIFY:** `pvecm status` = 2 nodes, Quorate, Expected 2. Then
   **re-enroll TOTP** for `root@pam` (and check `simon@pve`) via Datacenter → Permissions → Two Factor,
   and `pvecm expected 2`.
5. **Fix storage:** `pvesm set local-zfs --nodes apophis,carter`. **VERIFY:** local-zfs active on both.
6. **node_exporter** — already reinstalled by `provision-host.yml` at step 3 (re-run
   `install-node-exporter.yml --limit carter` only if you skipped it). The PVE monitoring token is
   cluster-shared → carter's pve-exporter re-auths automatically. **VERIFY:** carter node + pve
   targets up in Prometheus.
7. **Recreate replication (apophis → carter)** for both critical VMs:
   `pvesr create-local-job 200-0 carter --schedule '*/15'` and
   `pvesr create-local-job 118-0 carter --schedule '*/15'`, then `pvesr run --id 200-0 && pvesr run --id 118-0`
   (first full sends). **VERIFY:** `pvesr status` both jobs State OK, FailCount 0; `zfs list -t snapshot`
   on carter shows `__replicate__` snapshots for 200 and 118.
8. **Reprovision CT 117 `technitium2`** (reproducible from code; admin password pasted from Vaultwarden
   at the prompt): `ansible-playbook playbooks/provision-technitium.yml --limit carter`. **VERIFY:**
   `dig @YOUR_TECHNITIUM2_IP example.com +short` resolves and a blocked domain returns NXDOMAIN.
9. **Restore VM 127 `actual` from PBS** to Carter using the newest `vm/127` image. Do not run
   `provision-actual.yml` over a replacement VM when finance data already exists; the PBS image is the
   authoritative full recovery. **VERIFY:** Tailscale Serve URL loads, `/opt/actual/data` is present,
   and VM 127 remains selected in the cluster backup job. For a prolonged Carter outage, restore 127
   to apophis instead; its fixed MAC/IP let the UniFi reservation follow it without a network change.
10. **Restore freshness/quorum baseline:** confirm 0 firing alerts, `pvecm status` Expected 2, and
   that VM 200/118 failover to carter is available again (replication snapshots present).

> **Lessons carried from the apophis 4b rebuild (2026-06-25):** do the `delnode` *before* wiping
> (else the survivor goes read-only — recover with `pvecm expected 1`); treat 2FA as a **join
> blocker** and have the SSH `pveum user tfa delete` path ready; cap any cross-node migration on the
> 1 Gb NIC with `--bwlimit 100000`. The live carter-rebuild drill itself is deferred — this runbook
> is the tested-on-paper plan; the apophis execution proved the symmetric procedure.

## Manual failover (VM 200, when apophis is truly dead) — ADR-009

No auto-HA (no fencing). Failover is a deliberate human action:
1. **Confirm apophis is actually dead** (not a network blip).
2. On **carter**: `pvecm expected 1` (makes carter quorate alone → `/etc/pve` writable).
3. `zfs list -t snapshot rpool/data/vm-200-disk-1` — note the latest `__replicate__` snapshot (≤15 min data loss accepted).
4. `qm start 200` on carter (config is cluster-shared, synced to the last replication).
5. Confirm HA up + Z2MQTT reconnects (self-heal automation assists).
6. When apophis returns: `pvecm expected 2`, re-sync/restart replication, migrate 200 back when stable.

## Onboarding a new guest / node / storage (ADR-017)

Observability + a continuity plan are part of provisioning, not a later add-on. Work
top-to-bottom; most monitoring is automatic, so the list is short.

**1. Provision**
- [ ] Reserve the static IP in UniFi *before* provisioning (DHCP collisions bite — see Glance `.12`).
- [ ] Add the `<svc>_*` block to `group_vars/all.yml` (+ placeholder in `all.yml.example`).
- [ ] Write/run `provision-<svc>.yml` (Terraform creates / Ansible configures per ADR-008).
- [ ] **Enrol in auto-patching (ADR-015):** for a new **CT**, re-run `provision-patching.yml`
      (it discovers running CTs via `pct list`, so a new one is only covered after a re-run) —
      otherwise the CT **never security-patches**. Confirm with
      `pct exec <ctid> -- systemctl list-timers apt-daily-upgrade.timer`. For a new **Ubuntu VM**,
      add it to the direct targets in `provision-patching.yml` and
      `provision-maintenance-monitoring.yml`, then add its node_exporter endpoint to
      `provision-monitoring.yml`; re-run all three so it auto-patches security updates and Glance
      reports its state. Ordinary packages, Docker image changes, and reboots remain manual.

**2. Monitoring — mostly automatic, confirm + register**
- Automatic (no action): `GuestDown` (`pve_up`) and Glance workload CPU/RAM/Disk
  (`pve_guest_info` + `guest:*` recording rules). A new node's `local-zfs` joins Host Pulse;
  other physical/shared storage needs an explicit semantic decision so overlapping backends are not summed.
- [ ] Add a tile to **`glance_services`** (group_vars), including `node` + `workload` placement;
      re-run `provision-glance.yml`.
- [ ] If it has GitHub releases, add to **`glance_release_repos`**.
- [ ] If its configured pin is a reliable version tag, add it to **`glance_version_currency`**.
- [ ] If it exposes its own metrics, add a `scrape_config` to `provision-monitoring.yml`
      (+ a Grafana dashboard under `files/monitoring/dashboards/`).
- [ ] Update the `GuestDown` id-map comment in `alert-rules.yml`.

**3. Alerting**
- [ ] Confirm `GuestDown`/`TargetDown` cover it. Add a service-specific rule only for a
      real failure mode beyond "process down".

**4. Backup — a deliberate decision (ADR-012), then make it visible**
- [ ] Pick one and record it in PLAN.md / `components/<svc>.md`:
  - **Reproducible-from-playbook** (most LXCs) — the playbook is the backup; no image.
  - **App-native** (e.g. HA partial) — configure + land off-box.
  - **PBS image** (stateful, not reproducible from code) — add to the Proxmox backup job.
- [ ] Register freshness: PBS groups + the HA share are auto-discovered by
      `backup-freshness.sh` → `BackupStale`/`BackupAbsent` + Glance "Backup State" +
      the Grafana "Backups & Recoverability" dashboard cover it for free. A new *kind*
      of target (new datastore/share) → teach the script that path, then re-run
      `provision-backup-monitoring.yml`.

**5. Continuity — prove it**
- [ ] Run a restore/reprovision drill; record the RTO in the Restore drills table above.

**6. Docs**
- [ ] Update `PLAN.md` (infra table + single source of truth) and add `docs/components/<svc>.md`.

**Node-specific:** also add to `monitoring_pve_nodes` and `glance_hosts`; run
`install-node-exporter.yml`; mint the PVEAuditor token (play 1 of
`provision-monitoring.yml`, no `--limit`). **Storage-specific:** `PVEStorageFull` +
Storage Pools cover it automatically; if it's a new backup datastore, extend
`backup-freshness.sh`.

---

## Media USB monitoring — apophis

The media stack expects a distinct filesystem at `/mnt/usb-media`. Debian's node_exporter excludes
all `/mnt` paths from its filesystem collector. On apophis, `install-node-exporter.yml` therefore
enables the built-in systemd collector and restricts it to the generated
`mnt-usb\x2dmedia.mount` unit. This reports mount state without calling `statfs` on the USB disk.
The configuration clears node_exporter's default `.mount` exclusion; the anchored include still
restricts per-unit collection to this one mount.
An inactive or absent active-state series means the mount is absent; an unavailable
`node="apophis"` target is host/exporter loss. A separate textfile collector runs every six hours,
caches exact used/total/available bytes plus its successful-sample timestamp, and leaves its last
good sample untouched when the mount is absent. Prometheus scrapes only the cached file, so neither
Prometheus nor a dashboard refresh calls `statfs` on the USB filesystem.

Deploy or refresh both consumers from `~/homelab/ansible`:

```bash
ansible-playbook playbooks/install-node-exporter.yml --limit apophis
ansible-playbook playbooks/provision-media-storage-monitoring.yml
ansible-playbook playbooks/provision-monitoring.yml
ansible-playbook playbooks/provision-glance.yml --limit oneill
```

The node_exporter play restarts only apophis's exporter when its arguments change. The monitoring
play reloads `MediaStorageNotMounted` (critical after 5m while apophis remains reachable),
`MediaStorageSpaceLow` (warning above 85% used), and `MediaStorageCapacityStale` (warning when no
successful sample exists for 18h). The existing `TargetDown` alert covers host/exporter loss.
Glance shows mount state, cached used/total capacity, and sample age.

Useful checks on apophis:

```bash
mountpoint /mnt/usb-media
findmnt /mnt/usb-media
systemctl status homelab-media-storage.timer
cat /var/lib/prometheus/node-exporter/homelab_media_storage.prom
```

If the mount is absent, stop media writes and correct the USB device/mount first. If the mount is
present but Prometheus has no active-state series, confirm `prometheus-node-exporter` is running,
check its metrics for `node_systemd_unit_state`, and inspect the `node` target on Prometheus's
Targets page.

### Capacity collector incident and revised cadence — 2026-07-17/18

The first deployment of a dedicated `df`-based textfile collector coincided with a complete apophis
lock at 18:54 AEST during timer enablement or the immediate service run. The previous boot ended
without USB, UAS, xHCI, NIC, OOM, panic, or hung-task diagnostics; after a physical power cycle the
Samsung T5 mounted cleanly. The deployment remains correlated with the incident, but no evidence
proved that one filesystem-allocation query caused it; the active media services also access this
filesystem continuously. The original five-minute collector was therefore not restored. Capacity
sampling returned at a deliberately low six-hour cadence, starts 15 minutes after boot, records its
age, and is never used to determine mount state. A userspace timeout is still not claimed as a kernel
I/O safeguard. Keep the Lenovo firmware investigation open and retire capacity sampling again if
USB/UAS/xHCI or repeat lock evidence appears.

---

## qBittorrent + WireGuard killswitch (CT 121) — ADR-021, Phase 6b

Provisioned by `provision-qbittorrent.yml`. All egress is forced through a ProtonVPN
WireGuard tunnel; an nftables killswitch (default-drop output — only `lo`, established,
`wg0`, and the WG handshake to the Proton endpoint are allowed) means a tunnel drop = **zero
leak**. qBittorrent also binds torrents to `wg0`. LAN reaches only the Web-UI + SSH.

### Leak-test — MUST pass before trusting it (run after provisioning)
```bash
CT=121
# 1) Tunnel up + egress is a Proton IP (NOT your home WAN IP):
pct exec $CT -- wg show wg0 | grep -E 'latest handshake|transfer'   # a recent handshake
pct exec $CT -- curl -s --max-time 8 https://api.ipify.org; echo    # must be a ProtonVPN exit IP
# 2) Killswitch holds when the tunnel drops — bring wg0 down and confirm egress STOPS:
pct exec $CT -- ip link set wg0 down
pct exec $CT -- bash -c 'curl -s --max-time 5 https://api.ipify.org; echo "exit:$?"'  # must TIME OUT (non-zero)
pct exec $CT -- bash -c 'dig +time=3 +tries=1 example.com >/dev/null; echo "dns:$?"'  # must FAIL (no DNS leak)
# 3) Restore:
pct exec $CT -- systemctl restart wg-quick@wg0
pct exec $CT -- wg show wg0 | grep handshake
```
If step 2 returns an IP or resolves DNS, **stop** — the killswitch is leaking; do not torrent
until fixed (check the nftables `output` policy is `drop` and the only accepts are lo/established/
wg0/handshake).

### First-run + port forwarding
- **Web-UI password (set immediately):** the first-run temp password is logged —
  `pct exec 121 -- journalctl -u qbittorrent | grep -i 'temporary password'`. Log in at
  `http://<qbittorrent_ip>:{{ webui_port }}` (LAN/Tailscale), set a real password.
- **NAT-PMP forwarded port:** `pct exec 121 -- journalctl -u natpmp-renew | tail` shows the
  forwarded public port; set qBittorrent's listen port to match (Options → Connection).
- **Save path:** completed downloads land in `/media/downloads` (shared with Jellyfin); move/
  hardlink into `/media/library/{movies,tv}` for Jellyfin to index.

### Recovery
Reproducible from code → re-run `provision-qbittorrent.yml` (needs `qbittorrent_wg_config` +
`qbittorrent_ip` in the gitignored `all.yml`). Not imaged; downloads on the USB SSD persist.

---

## Git / repo

### Push latest changes
```bash
git add <files> && git commit -m "..." && git push
```

### Check what's uncommitted
```bash
git status && git diff
```

---

## Vaultwarden VM build — codified in `provision-vaultwarden.yml` (manual recipe below for reference)

VM 118 `vaultwarden` on apophis: Ubuntu 24.04 cloud image + official Docker container + Tailscale Serve.
**Lessons (why this shape):** a Debian-12 cloud image **kernel-panics** on emulated CPU models
(`x86-64-v2-AES`, `Skylake-Client`) — Ubuntu boots fine; building Vaultwarden from source OOMs a small
guest. So: Ubuntu cloud image, the official container, `Skylake-Client-noTSX-IBRS` CPU (boots **and**
migrates the Coffee-Lake pair).

```bash
# --- on apophis: create the VM from the Ubuntu cloud image + cloud-init ---
wget -P /var/lib/vz/template https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
echo "<mgmt-vm pubkey>" > /tmp/k.pub
qm create 118 --name vaultwarden --memory 2048 --cores 1 --cpu Skylake-Client-noTSX-IBRS \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --machine q35 --ostype l26 \
  --agent enabled=1 --onboot 1 --startup order=2,up=10
qm set 118 --scsi0 local-zfs:0,import-from=/var/lib/vz/template/noble-server-cloudimg-amd64.img
qm set 118 --ide2 local-zfs:cloudinit --boot order=scsi0
qm disk resize 118 scsi0 10G
qm set 118 --ciuser simon --sshkeys /tmp/k.pub --ipconfig0 ip=<vw-ip>/24,gw=<gw> --nameserver <gw>
qm start 118    # boots in ~15s, cloud-init brings up the IP + SSH key + sudo

# --- in the VM (ssh simon@<vw-ip>): guest agent, Docker, Tailscale ---
sudo apt-get install -y qemu-guest-agent && sudo systemctl enable --now qemu-guest-agent
# Docker official apt repo (docker-ce + compose-plugin); Tailscale: curl -fsSL https://tailscale.com/install.sh | sudo sh
sudo tailscale up --authkey=<reusable,non-ephemeral,pre-approved> --hostname=vaultwarden --ssh=false

# --- deploy the container (in /opt/vaultwarden) ---
# admin token: TOKEN=$(openssl rand -base64 24); HASH=$(printf %s "$TOKEN" | argon2 "$(openssl rand -base64 12)" -id -t 3 -m 16 -p 4 -l 32 -e)
#   put HASH in the env file; store the plaintext TOKEN in Vaultwarden (Tier 1), not on the VM
#   (the as-built /root/vw-admin-token.txt was deleted 2026-06-26 once it was in the vault).
# env file NAMED vaultwarden.env (NOT .env — compose treats .env as interpolation source) AND
#   escape every $ in ADMIN_TOKEN as $$ (this compose version interpolates env_file values too).
# vaultwarden.env: DOMAIN=https://vaultwarden.<tailnet>.ts.net, ROCKET_ADDRESS=0.0.0.0, ROCKET_PORT=8080,
#   SIGNUPS_ALLOWED=false (true only for first registration), INVITATIONS_ALLOWED=false, login rate-limit, ADMIN_TOKEN=<$$-escaped hash>
# docker-compose.yml: image vaultwarden/server:1.36.0, env_file vaultwarden.env, volume ./data:/data,
#   ports "127.0.0.1:8080:8080", security_opt [no-new-privileges:true], cap_drop [ALL]
sudo docker compose up -d
sudo tailscale serve --bg --https=443 http://127.0.0.1:8080   # needs HTTPS+Serve enabled on the tailnet (one-time)
```

**Onboarding done:** `pvesr create-local-job 118-0 carter --schedule '*/15'`; added 118 to the PBS vzdump
job + immediate backup; OS password locked (key-only). **Health:** `curl https://vaultwarden.<tailnet>.ts.net/alive`;
`docker compose -f /opt/vaultwarden/docker-compose.yml logs`. **Restart:** `cd /opt/vaultwarden && sudo docker compose restart`.
**Lock signups after registering:** set `SIGNUPS_ALLOWED=false`, `docker compose up -d --force-recreate`.

**Tailnet ACL (the vault is reachable only by your devices):** the live policy is the versioned
reference at [`ansible/files/tailscale-acl.hujson`](../../ansible/files/tailscale-acl.hujson). The
node is tagged `tag:vaultwarden`; default-deny means only `group:operators` reach it on `:443`.
ACLs are console/API-only — edit at login.tailscale.com/admin/acls and keep the reference file in
sync. The file's header documents the safe staged rollout (declare tags → tag machines → tighten acls).

---

*Add new entries as services are deployed. Each service should have: how to check health, how to restart, where to find logs.*
