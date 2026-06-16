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
(ADR-011), serving home/IoT/guest VLANs. Provisioned via Ansible
(`ansible-playbook playbooks/provision-technitium.yml --limit oneill`, idempotent). Web
console on port `5380`, DNS on `53`.

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
5. **Roll out** to remaining VLANs once the test network is healthy.

### Rollback (if DNS misbehaves)

1. UniFi → the network's DHCP → **DNS Server** → set back to the previous resolver
   (gateway or `1.1.1.1`).
2. Renew a client lease to confirm recovery.
3. Technitium can stay running while you debug — clients no longer depend on it.

### Planned maintenance on oneill (DNS goes down with it)

Technitium is a single instance with no DHCP secondary (ADR-011), so taking oneill down
drops DNS for home/IoT/guest VLANs. Before planned maintenance:
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

#### Restore a guest from PBS
```bash
ssh root@YOUR_PROXMOX_IP "pvesm list pbs-oneill"                                            # list points
ssh root@YOUR_PROXMOX_IP "qmrestore pbs-oneill:backup/vm/100/<ISO-timestamp> <newvmid>"     # VM
ssh root@YOUR_PROXMOX_IP "pct restore <newctid> pbs-oneill:backup/ct/110/<ISO-timestamp>"   # CT
```

### Home Assistant — native partial backup (primary for HA)
- HA protects itself via a **scheduled partial backup** (Settings → System → Backups): HA config
  + **Zigbee2MQTT add-on** + add-on configs; **media excluded**; recorder DB kept small via
  `recorder` `purge_keep_days`. Written to an **NFS share on oneill** (CT 113) added in HAOS as
  network storage. Portable — restores onto any HAOS.
- **Interim:** until the native partial is verified, the old local `vzdump-qemu-200` image on
  apophis `local` is HA's safety net — delete it only after a native partial is confirmed.

### Recovery model — what recovers what (avoid doubling up)

Principle: **back up what code can't recreate.** Most services rebuild from git, so they
don't need image backups — only genuinely stateful or hand-built things do.

| Layer | Recreates | Lives |
|---|---|---|
| Terraform (ADR-008) | VM/LXC existence + shape | git (public) |
| Ansible playbooks | service config (Technitium, Tailscale, PBS, share) | git (public) |
| Private repo (ADR-007) | real inventory/group_vars/host_vars, `.claude` | git (private) |
| PBS images | **mgmt-vm** only (hand-built, not in code) | oneill |
| HA native partial | HA config + Zigbee2MQTT + add-ons | oneill share |

The only guest in PBS is **mgmt-vm** — it isn't reproducible from a playbook. The CTs
(Technitium, Tailscale) are deliberately **not** imaged: they rebuild from their playbooks
(`provision-technitium.yml` / `provision-tailscale.yml`), so PBS images would only duplicate code.

**Restore by scenario:**
- **A guest is lost/corrupted:** reproducible service → re-run its playbook; mgmt-vm (or any
  quick full restore) → `qmrestore` / `pct restore` from `pbs-oneill`; HA → restore its
  partial backup from the share onto HAOS.
- **oneill (backup hub) dies:** production is unaffected if apophis is up (oneill only holds
  Technitium + the backups). Rebuild: fresh PVE + ZFS → `ssh-copy-id` → re-run
  `provision-technitium.yml`, `provision-pbs.yml`, `provision-ha-backup-share.yml`. **The
  backup data on oneill is a single copy** — protected only once the off-site sync exists; an
  oneill SSD failure today loses restore history, not production.
- **apophis dies:** its guests' images are safe on oneill → restore to replacement hardware.
- **Both / site disaster:** infra rebuilds from git (Terraform + Ansible + private repo); VM
  *data* is lost until the off-site copy exists — the deferred-off-site gap.

**Backing up the hub itself:** don't copy oneill's backups to apophis (circular, same-site).
The backups are protected by the **off-site copy** (ADR-012 deferred leg — encrypted sync of
both datasets to cloud). That, not a second local copy, is "backing up oneill."

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
