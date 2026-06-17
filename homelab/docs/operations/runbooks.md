# Runbooks

Common operational procedures for Simon's homelab. Keep entries short — what to run, what to check, what success looks like.

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

Unprivileged LXC 111 on **oneill** (NUC, `YOUR_NUC_IP`). **DNS only — UniFi keeps DHCP**
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

A permanent fix (second Technitium instance) lands with the cluster in Phase 4.

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
  instance). Starter rules: `TargetDown`, `NodeFilesystemSpaceLow`, `NodeMemoryHigh`, `PVEStorageFull`.
  - **Test the pipeline:** `pct exec 114 -- amtool --alertmanager.url=http://localhost:9093 alert add
    alertname=PipelineTest severity=critical --annotation=summary="test"` → ntfy push after the 30s
    group_wait (auto-resolves ~5 min later). Confirm delivery without a phone:
    `curl -s "https://ntfy.sh/<topic>/json?poll=1&since=3m"`.
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
  One `Homelab` page: host/VM-LXC metrics (live from Prometheus), service status, alert summary,
  versions, releases, admin links. Stateless — nothing to back up.
- **Manage:** edit the **template** (`glance.yml.j2`) and/or `glance_*` vars (`glance_prometheus_url`,
  `glance_hosts`, `glance_version`, service IP vars) in `group_vars`, then
  `ansible-playbook playbooks/provision-glance.yml --limit oneill`. Never edit the live config by
  hand — the playbook stages + `config:print`-validates the render, then promotes it (a bad render
  can't break the running dashboard) and overwrites the live file each run.
- **Health/restart:** `pct exec 115 -- systemctl status glance`; `... journalctl -u glance -n 50`;
  `... curl -fsS -o /dev/null -w '%{http_code}' http://localhost:8080/` (expect `200`); content:
  `curl -fsS http://YOUR_GLANCE_IP:8080/api/pages/homelab/content/` (should have no `ERROR`).
- **A metric/status pane is empty or red:** a `custom-api` pane needs Prometheus (CT 114) reachable
  — check it first; a `monitor` tile red means that service is unreachable; for self-signed HTTPS
  tiles (Proxmox/PBS/UniFi) the template sets `allow-insecure: true` + `alt-status-codes`.
- **Recovery:** stateless → reprovision (RTO ~10 min). Bumping Glance: change `glance_version`,
  re-run, eyeball the page (pre-1.0 config-key renames — see ADR-014).
- **Not this:** graphs/history → Grafana; household wall-tablet control → Home Assistant (Phase 6).

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
- **Scheduled job (apophis):** **VM 100 (mgmt-vm)** → `pbs-oneill`, daily **02:30**, retention
  **keep-daily 7 / keep-weekly 4**. CTs and HA are **excluded** — the CTs rebuild from their
  playbooks; HA uses the native partial below. (mgmt-vm is the only guest not reproducible from code.)
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
ssh root@YOUR_PROXMOX_IP "qmrestore pbs-oneill:backup/vm/100/<ISO-timestamp> <newvmid>"     # VM
ssh root@YOUR_PROXMOX_IP "pct restore <newctid> pbs-oneill:backup/ct/110/<ISO-timestamp>"   # CT
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
  were **deleted** (PBS covers mgmt-vm off-box). **`vzdump-qemu-200` (HA) is retained** as the
  whole-VM fallback until the partial backup is verified *restorable* — retire it at the first
  restore drill (landing ≠ restorable).
- **⚠️ Encryption key:** HAOS backups are **encrypted** (`"protected": true` in `backup.json`). The
  key (HAOS → Settings → System → Backups → ⋮ → "Show encryption key") **must be stored off-box** —
  losing it makes every encrypted backup unrestorable. No credential manager is set up yet, so it's
  kept in Google Password Manager for now; move it into the password manager when one lands (ADR-010).

### Recovery model — what recovers what (avoid doubling up)

Principle: **back up what code can't recreate.** Most services rebuild from git, so they
don't need image backups — only genuinely stateful or hand-built things do.

| Layer | Recreates | Lives |
|---|---|---|
| Ansible playbooks | **the LXCs end-to-end** — `pct create` + config (Tailscale, Technitium, PBS, share) | git (public) |
| Private repo (ADR-007) | real inventory/group_vars/host_vars, `.claude` | git (private) |
| PBS images | **mgmt-vm** (hand-built, no playbook) | oneill |
| HA native partial | HA config + Zigbee2MQTT + add-ons (restore onto a fresh HAOS) | oneill share |
| Terraform (ADR-008) | **planned** — declarative VM/LXC definitions; not yet imported (empty scaffold) | git (public) |

**Reality check (2026-06-16):** Terraform manages nothing yet (no state) — the four LXCs are
created **and** configured by their Ansible playbooks today (re-run to rebuild). The CTs are
deliberately not in PBS (the playbooks rebuild them). **mgmt-vm and the HA VM are the exceptions
— neither is recreatable from code:** mgmt-vm relies on its PBS image; HA relies on manually
creating a HAOS VM then restoring the native partial. The playbook rebuild path is unproven
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

| Date | Backup tier | Result |
|------|-------------|--------|
| 2026-06-17 | PBS mgmt-vm (VM 100) | ✅ PASS — restored 24 s, booted, `group_vars/all.yml` + git repo present |
| _pending_ | HA native partial → fresh HAOS | untested — **gates retiring the held `vzdump-qemu-200`** |
| _pending_ | CT 111 Ansible reprovision | untested — records the real RTO |

> **Timezone note:** apophis runs **AEST (UTC+10)**. Backup-job schedules (e.g. `02:30`) are
> local; PBS snapshot names are **UTC** (`…T16:30:03Z` = 02:30 AEST). Don't mistake the offset
> for a missing run.

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

*Add new entries as services are deployed. Each service should have: how to check health, how to restart, where to find logs.*
