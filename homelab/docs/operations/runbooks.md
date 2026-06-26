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
  **`GuestDown`** (`pve_up{id=~"lxc/.*|qemu/.*"} == 0` — a guest stopped/crashed while its host is up;
  `up`/TargetDown only covers *scraped* targets, so this is what catches a service LXC like Tailscale
  or Technitium dying on its own. A whole-host outage makes these go *absent*, caught by TargetDown).
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
- **Not this:** graphs/history → Grafana; household wall-tablet control → Home Assistant (Phase 5 HA-expansion).

---

## Patching & updates (ADR-015)

- **Guest LXCs (auto):** `provision-patching.yml` puts **`unattended-upgrades`** on every running CT
  (discovered via `pct list` on both hosts → the service LXCs; mgmt-vm + HA VM are excluded). Policy:
  **security/point-release only** (Debian default origins, *not* `-updates`), **no auto-reboot**,
  applied at **12:00 local** (`patching_timezone`, pinned in the systemd calendar so the UTC CTs
  still fire at local noon), **ntfy on failure** (OnFailure hook → your topic). **`needrestart`
  (mode `a`)** auto-restarts services on updated libs so the patch takes effect immediately — guests
  **never need a manual reboot** (they share the host kernel; kernel fixes come via the host window).
  - Apply/refresh: `cd homelab/ansible && ansible-playbook playbooks/provision-patching.yml` (idempotent, both hosts).
  - Check a guest: `pct exec <ctid> -- systemctl list-timers apt-daily-upgrade.timer` (next = local noon);
    `pct exec <ctid> -- unattended-upgrade --dry-run` (shows allowed origins + candidates).
  - Logs: inside the CT, `/var/log/unattended-upgrades/`. A failure pushes an ntfy alert.
- **Hosts + mgmt-vm (manual):** deliberate **monthly window — last day of month, 12:00 AEST** (be
  present for fallout). One node at a time; pre-cluster accept brief downtime, post-cluster (Phase 4)
  HA-failover the guests off first → `apt update && apt dist-upgrade` → reboot if
  `node_reboot_required` → next node. Driven by Glance's *Package Updates* / *Reboot required* panes.
- **HAOS:** update via the HA UI on your cadence; take/confirm a partial backup first (ADR-012).
- **Note (PBS repo):** the PBS CT must stay on `pbs-no-subscription` — `provision-pbs.yml` disables
  the shipped `pbs-enterprise` repo (it 401s and breaks `apt-get update` / unattended-upgrades).
- **Proxmox host repos:** fresh nodes ship the enterprise repos (401 without a sub) → switch to
  `pve-no-subscription` (done by hand on apophis + oneill; host-prep play still to be codified).

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
  were **deleted** (PBS covers mgmt-vm off-box). **`vzdump-qemu-200` (HA) retired 2026-06-18** — the
  partial backup was proven restorable end-to-end (see Restore drills below), so the whole-VM
  fallback is no longer needed. No `vzdump-qemu` images remain on apophis `local`.
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
| _pending_ | CT 111 / CT 117 Ansible reprovision | untested — records the real RTO |

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

- **apophis / carter (Lenovo ThinkCentre) — REMOTE, no console needed.** Recent kernels expose the
  Lenovo BIOS via the `thinklmi` driver, so set it over SSH (no BIOS password is set here):
  ```bash
  base="/sys/class/firmware-attributes/thinklmi/attributes/After Power Loss"
  cat "$base/current_value"                  # Power On / Power Off / Last State
  printf "Power On" > "$base/current_value"   # set it; applies on the next power event
  ```
  (If an Admin BIOS password is ever enabled — `.../authentication/Admin/is_enabled` = 1 — write it
  to `.../authentication/Admin/current_password` first.) **apophis set to "Power On" 2026-06-22.**
  carter: run the same one-liner once it's on the network.
- **oneill (generic N150 mini-PC, AMI Aptio BIOS) — NO remote interface** (`/sys/class/firmware-attributes/`
  absent). ✅ **FIXED 2026-06-22.** Root cause: BIOS **"State After G3" = S5** (stay off after power
  loss); changed to **S0** (power on) — confirmed self-boots on AC restore. On this board the setting
  is under **"State After G3" (S0/S5)**, *not* "Restore AC Power Loss"; if you're back in this BIOS,
  also check **Deep Sleep/ErP = Disabled**. Entry key: Del (try F2/Esc). No remote/SSH path for it.
- **UPS:** confirm the UPS also feeds the **network device** (gateway/switch) — else a blip still
  causes the common-mode outage ADR-009 warns about.

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
5. **Reinstall apophis** from the PVE 9.2.3 ISO → **ZFS (RAID0)** on the SSD, hostname `apophis`. Then: set no-subscription repos (same as carter onboarding), `apt update && dist-upgrade`, restore root `authorized_keys`. **VERIFY:** boots, `pveversion`=9.2.3, `zpool list` shows rpool.
6. **Rejoin (carter root has 2FA — cluster-wide):** from mgmt-vm `ssh-keygen -R YOUR_PROXMOX_IP` (clear apophis's old host key) then `ssh-copy-id root@YOUR_PROXMOX_IP` (re-add the node-local mgmt-vm key); on **apophis's shell (a TTY)** run `pvecm add YOUR_CARTER_IP` — enter carter's root pw **+ 2FA OTP** (the GUI/API join fails with 2FA, as when we first formed the cluster). On rejoin apophis pulls the cluster-shared `/etc/pve` → users/2FA/ACLs/monitoring-token/storage.cfg return automatically. **VERIFY:** `pvecm status` = 2 nodes, Quorate, Expected 2.
7. **Fix storage:** `pvesm set local-zfs --nodes apophis,carter` and `pvesm remove local-lvm` (apophis has no LVM now). **VERIFY:** local-zfs active on both.
8. **Migrate 100 + 200 back to apophis** (`--targetstorage local-zfs`). **VERIFY:** HA + mgmt-vm healthy on apophis.
9. **Verify monitoring resumes:** the PVE monitoring token is in cluster-shared `/etc/pve` → it returns on rejoin, so apophis's pve-exporter should auth automatically. **node_exporter** is node-local → reinstall it: `ansible-playbook playbooks/install-node-exporter.yml --limit apophis`. **VERIFY:** apophis node + pve-exporter targets up in Prometheus; only re-run `provision-monitoring.yml` if the pve target stays down.
10. **2FA — no re-enrollment needed:** root@pam + simon@pve TOTP lives in cluster-shared `/etc/pve/priv/tfa.cfg` and returns on rejoin. **VERIFY:** log into apophis's GUI with TOTP to confirm it works.
11. **Set up replication:** `pvesr create-local-job 200-0 carter --schedule '*/15'` then `pvesr run --id 200-0` (first full send). **VERIFY:** `pvesr status` shows job `200-0` State OK, FailCount 0; `zfs list -t snapshot` on carter shows a `__replicate__` snapshot. *(Note: the job ID is `<vmid>-<n>`, e.g. `200-0`; the older `pvesr create --guest …` form does not exist on PVE 9.)*

> **Execution notes — what actually happened on 2026-06-25 (corrections to the plan above):**
> - **Step order was violated:** apophis was physically pulled and reinstalled **before** `pvecm delnode` (step 4). carter then dropped to 1/2 and went **read-only**. Recovery: on carter `pvecm expected 1` → `pvecm delnode apophis` → `rm -rf /etc/pve/nodes/apophis` (stale node dir), which freed the name to rejoin. **Do step 4 first** — but if you slip, this is the recovery.
> - **Step 10's "2FA returns automatically, no re-enrollment" was WRONG in practice.** The cluster-shared TOTP *did* return, but the `pvecm add` TTY OTP prompt **kept returning `401 authentication failure`** for both `root@pam` and `simon@pve` — even with carter's clock NTP-synced (verified <1 s skew) and after a phone time-correction. Root cause was an authenticator/secret mismatch, not clock. **Fix that unblocked the join:** over SSH (key auth bypasses 2FA) `pveum user tfa delete root@pam --id <id>` to drop root's TOTP, after `cp -a /etc/pve/priv/tfa.cfg /root/tfa.cfg.bak.$(date +%s)`. `pvecm add` then needs only carter's root **password** (no OTP). **Afterwards, re-enroll fresh TOTP** for `root@pam` *and* `simon@pve` via Datacenter → Permissions → Two Factor (the old `simon@pve` secret was also stale — delete + re-add). Lesson: treat 2FA as a join blocker; have the SSH-removal path ready.
> - **Live-migration tunnel dropped intermittently** (`mirror-<disk>: Input/output error (io-status: ok)` then `writing to tunnel failed: broken pipe`) when running at near-line-rate on the shared **1 Gb** NIC — network itself was clean (0 % ping loss, corosync stable). **Fix:** cap with `qm migrate <vmid> apophis --online --with-local-disks --bwlimit 100000` (~80 MB/s ≈ 80 % of 1 Gb, leaving corosync headroom). First uncapped attempt failed ~24 %; capped retry completed. Apply the same `--bwlimit` to every cross-node migration on this single-NIC pair.
> - **CTs can't live-migrate** — CT 110 used `pct migrate 110 <node> --restart` (brief stop). zfspool→zfspool works fine now both nodes are ZFS (the old lvmthin→zfspool block is gone).
> - **Step 3 (rebuild Tailscale CT 110 on oneill) was skipped** — CT 110 was instead migrated to carter then back to apophis. **Keeping Tailscale on apophis is the accepted placement (decided 2026-06-25)** — the earlier "Tailscale → oneill" intent is superseded.

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

**2. Monitoring — mostly automatic, confirm + register**
- Automatic (no action): `GuestDown` (`pve_up`), Glance VM/LXC CPU/RAM/Disk (`pve_guest_info` +
  `guest:*` recording rules), `PVEStorageFull` + Storage Pools for any new `storage/.*`.
- [ ] Add a tile to **`glance_services`** (group_vars) — one entry; re-run `provision-glance.yml`.
- [ ] If it has GitHub releases, add to **`glance_release_repos`**.
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

**Node-specific:** also add to `monitoring_node_targets`, `monitoring_pve_nodes`, and
`glance_hosts`; run `install-node-exporter.yml`; mint the PVEAuditor token (play 1 of
`provision-monitoring.yml`, no `--limit`). **Storage-specific:** `PVEStorageFull` +
Storage Pools cover it automatically; if it's a new backup datastore, extend
`backup-freshness.sh`.

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
#   save plaintext to /root/vw-admin-token.txt (chmod 600), put HASH in the env file.
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
