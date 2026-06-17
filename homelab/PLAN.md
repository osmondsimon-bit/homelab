# Homelab Plan

## Current infrastructure

### apophis (Proxmox host)
- Intel i7-8700T, 16 GB RAM, ~500 GB SSD (LVM-thin today; migrating to ZFS — see Cluster & HA)
- IP: YOUR_PROXMOX_IP
- vmbr0 is VLAN-aware — completed

| VM/LXC | VMID | Type | IP | Status |
|--------|------|------|----|--------|
| mgmt-vm | 100 | VM (Ubuntu Server) | YOUR_MGMT_VM_IP | Running — git, Claude Code, Terraform + Ansible control node |
| home-assistant | 200 | VM (HAOS) | YOUR_HA_IP | Running — Zigbee2MQTT, SLZB-06 at YOUR_ZIGBEE_COORD_IP. HA-failover target once clustered. |
| tailscale | 110 | LXC (Debian 12, unpriv) | YOUR_TAILSCALE_LAN_IP | Running — subnet router, advertises YOUR_LAN_CIDR (ADR-003/005). To migrate onto oneill. |

### oneill (Intel NUC, Proxmox host)
- Intel N150, 4 cores / 4 threads, 16 GB RAM, single ~477 GB SSD (**ZFS-on-root**, `rpool` — ADR-009)
- IP: YOUR_NUC_IP — Proxmox VE 9.2, standalone (joins the cluster in Phase 4)
- The low-power "simple services" node, offloading apophis (ADR-009 hardware roadmap)

| VM/LXC | VMID | Type | IP | Status |
|--------|------|------|----|--------|
| technitium | 111 | LXC (Debian 12, unpriv) | YOUR_TECHNITIUM_IP | Running — DNS-only resolver, OISD blocklist + DoH forwarders (ADR-011). **Live on the home VLAN** (same subnet). IoT/guest use the gateway (Auto) for DNS — isolated VLANs can't reach a main-LAN resolver + appliances break on blocklists (DNS-by-VLAN-role); camera/management have no internet. |
| pbs | 112 | LXC (Debian 12, unpriv) | YOUR_PBS_IP | Running — Proxmox Backup Server, backup hub (ADR-012). Datastore on `rpool/data/pbs-datastore`. |
| ha-backup-share | 113 | LXC (Debian 12, unpriv) | YOUR_HA_BACKUP_SHARE_IP | Running — Samba/CIFS share for HAOS native backups (ADR-012). |
| monitoring | 114 | LXC (Debian 12, unpriv) | YOUR_MONITORING_IP | Running — Prometheus + Grafana + Alertmanager → ntfy, node/pve/UniFi/HA exporters, apophis dead-man's-switch (ADR-013). |
| glance | 115 | LXC (Debian 12, unpriv) | YOUR_GLANCE_IP | Running — front-door dashboard, native Go binary, links to Grafana (ADR-014). On a fixed static-band IP (an earlier pick collided with a desktop's DHCP lease — see backlog). |

**Network note:** mgmt-vm is on the Home VLAN. VLAN tagging on the VM NIC is off for now — relying on UniFi to assign the correct VLAN via port profile.

## Hardware & cluster roadmap

Moving from a single host to a **3-node Proxmox cluster**, with local storage standardised on **ZFS** so HA failover works via replication (ADR-009). Still **all local storage** — no NAS/shared storage; HA comes from ZFS replication, not shared disks.

| Node | Role | Status | Intended to run |
|------|------|--------|-----------------|
| apophis | Compute-heavy | Live | Plex (QuickSync) + media stack; HA VM or its failover target |
| Intel NUC (**oneill**, N150 / 16 GB / ZFS) | Low-power | **Live (standalone)** — Technitium, PBS, HA-share, Monitoring, Glance | Simple services offloaded from apophis: Technitium ✓, Monitoring ✓, Glance ✓; Tailscale still to migrate |
| 2nd ThinkCentre M920Q | Cluster + HA quorum | ~1 month | HA-failover target; extra capacity |

Offloading the simple services to the NUC frees apophis's CPU for Plex transcoding. Three nodes give clean cluster quorum. Mixed CPUs are fine for HA failover (restart-on-another-node); live migration between different CPU generations needs a compatible CPU type.

## Provisioning & tooling

- **Ansible currently creates *and* configures** the LXCs — `pct create` + config in the `provision-*.yml` playbooks (ADR-005). This is the interim mechanism and recovers cleanly by re-running.
- **Terraform** (`bpg/proxmox`, ADR-008) is scaffolded but its **import is deferred to cluster scale** — it will take over the *create* role then. Target boundary: *Terraform = box exists with the right shape; Ansible = box is set up.*

## Planned VMs/LXCs

| Service | Type | Node (intended) | Purpose |
|---------|------|-----------------|---------|
| ~~Technitium DNS~~ | LXC | **oneill** | ✅ Live — CT 111 on oneill (see Current infrastructure). DNS-only, OISD blocklist + DoH (ADR-011). UniFi keeps DHCP; serves the **home VLAN** (IoT/guest use the gateway — ADR-011 DNS-by-VLAN-role). |
| ~~Monitoring (Prometheus + Grafana + Alertmanager)~~ | LXC | oneill (CT 114) | ✅ Live — scrapes Proxmox/UniFi/HA, Alertmanager → am-ntfy bridge → ntfy with starter rules, apophis dead-man's-switch (ADR-013). Dashboards/alerts as code. |
| ~~Homepage~~ → **Glance** | LXC | **oneill** (CT 115) | ✅ Live — front-door dashboard. Native Go binary (no Docker), links to Grafana; Homepage rejected as Docker-first (ADR-014). Wall-tablet UI is HA's job (Phase 6). |
| Plex | VM | apophis | Media server, Intel QuickSync passthrough |
| qBittorrent + Gluetun | LXC | apophis | Torrent client behind Gluetun killswitch → ProtonVPN Plus |
| Vaultwarden | LXC | cluster (HA) | Self-hosted password manager — **sequenced after the HA cluster + backups** (ADR-010) |

Per-service RAM/disk sizing is set when each is built; with services spread across three nodes the old single-16 GB-host budget no longer binds. Plex stays on apophis for the iGPU.

**Media stack:** qBittorrent + Gluetun in one LXC — Gluetun runs the ProtonVPN Plus tunnel + killswitch (all torrent traffic exits via ProtonVPN, drops if the tunnel dies). Plex serves media; shared download path via bind mount (NAS deferred to new house).

**Password manager (ADR-010):** self-host **Vaultwarden** (local Bitwarden-compatible). It's zero-knowledge — the server stores only ciphertext, so theft of a node never exposes passwords and encrypted backups are safe to store anywhere. Sequenced *after* the HA cluster (solves availability) and the backup story (solves durability). **Bridge with Bitwarden's cloud now**; migration to Vaultwarden is a trivial export/import. Infra/machine secrets stay in `ansible-vault`, not Vaultwarden.

## Updates & patching

Keeping nodes + guests patched is an open design item (ADR pending). Likely shape: `unattended-upgrades` for security patches on Debian/Ubuntu guests; a deliberate **monthly Proxmox update window**, rolling one node at a time once clustered, with HA failover covering the reboot. Revisit dedicated tooling (a patch dashboard) later.

## Security hardening

Standard practices: network segmentation, least-privilege access, and no direct internet exposure.

## Home Assistant expansion

- Install HACS
- Add Node-RED for automation logic
- ESPHome ready for future DIY sensors
- Wire HA stats into Grafana
- **Wall-mounted tablet dashboard** — HA Lovelace (Mushroom/bubble-card via HACS) in kiosk-mode, on a cheap Android tablet running Fully Kiosk Browser (+ its HA integration for screen-wake/presence). This is the *household control surface* — distinct from Glance (admin front-door, ADR-014) and Grafana (graphs). Homepage cannot do it (it can't control HA, only display read-only stats).

## Phase order

1. VLAN-aware Proxmox + firewall rules — ✓ completed
2. Tailscale ✓ (CT 110) + Technitium DNS ✓ (CT 111 on oneill, serving the home VLAN; IoT/guest use the gateway) — **✓ completed**
3. **Foundation + observability:** PBS/mgmt-vm backups ✓ → **Monitoring** ✓ (Prometheus + Grafana + Alertmanager) → **Glance** ✓ (front-door dashboard, ADR-014; was Homepage). **✓ closed via `/phase-gate` 2026-06-17** — see `docs/phases/3-foundation-observability.md`. Carry-forwards: ~~HA native backup~~ ✅ landing, ~~mgmt-vm restore drill~~ ✅ PASS, ~~PBS encryption~~ ✅ enabled — all 2026-06-17; **remaining: an HA-native-restore drill** (gates retiring the held `vzdump-qemu-200`). (Terraform import deferred to cluster scale — ADR-008.)
4. **Multi-node + HA:** Intel NUC (oneill) joins the cluster → migrate remaining simple services (Tailscale) onto it (Technitium already there); 2nd ThinkCentre → 3-node cluster on ZFS, replication + **HA for the Home Assistant VM**; a 2nd Technitium instance removes the DNS SPOF
5. **Media:** Plex (QuickSync) + qBittorrent/Gluetun on the freed-up apophis
6. **Secrets + HA expansion:** self-host Vaultwarden (now HA + backups exist); HACS, Node-RED, ESPHome, HA → Grafana
- Cross-cutting (designed early, not deferred to the end): VM-level backups, a patching approach
- Deferred to the new house: NAS / shared storage, cameras, Frigate

## Open tasks & decisions (carry-over)

Living backlog to pick up next session.

### ▶ Pick up next session (immediate)
- **Phase 3 ✓ CLOSED** (`/phase-gate` 2026-06-17 — doc-auditor + continuity-reviewer + security-review, record in `docs/phases/3-foundation-observability.md`). **Next: Phase 4** (cluster + HA). Phase 3 backup carry-forwards — mgmt-vm restore drill ✅ PASS, HA native backup ✅ landing, PBS encryption ✅ enabled (all 2026-06-17); **remaining before new stateful services: an HA-native-restore drill** (also retires the held `vzdump-qemu-200`).
- **Reserve in UniFi:** the Glance CT's IP (fixed-IP / outside the DHCP pool). **Lesson:** the first IP picked as "free" from group_vars collided with a desktop's DHCP-preferred lease — UniFi even cloned the desktop's name onto the CT. Reserve static-service IPs *before* provisioning, and you may want to "forget" the stale client in UniFi.
- **Done 2026-06-17:** **Glance** front-door dashboard (CT 115, ADR-014) — native Go binary, chosen over Homepage to keep oneill Docker-free (Docker deferred to Phase 5/Gluetun); wall tablet reassigned to HA (Phase 6). Now a **single-page operator dashboard rendered from an Ansible Jinja template** (`ansible/templates/glance/glance.yml.j2`): host/VM-LXC metrics live from Prometheus, service status, alert summary, versions, latest releases, admin links — links out to Grafana for deep metrics. Reproducible (staged + `config:print`-validated before promote); real IPs in gitignored `group_vars`.
- **Done 2026-06-16:** Monitoring **Alertmanager + alert rules** — Prometheus rules → Alertmanager → `am-ntfy.py` stdlib bridge → ntfy (ntfy has no native AM receiver). Starter rules: TargetDown / NodeFilesystemSpaceLow / NodeMemoryHigh / PVEStorageFull. Verified end-to-end. Monitoring Step 2 now complete.
- **HA backup (2026-06-17):** ✅ automatic partial backup **confirmed landing** on the oneill share (CT 113) — recurring, ~131 MB. mgmt-vm interim `vzdump-qemu-100` images **deleted** (PBS covers them). **HA `vzdump-qemu-200` held** until its partial backup is verified restorable (do it at the first restore drill). Still to do: eyeball in HAOS that the partial scope includes the Zigbee2MQTT add-on and excludes media.
- **Operator quick wins:** reserve the monitoring + Tailscale CT IPs in UniFi. (Grafana dashboard build-out is its own backlog section below.)
- **Parked:** UniFi read-only MCP eval (verify MCP works in this env first); off-site backup copy (ADR-012); CT 111 reprovision drill.
- Monitoring is live (Prometheus/Grafana + node/pve/unifi/HA + ntfy dead-man's-switch). `/phase-gate` skill exists for closing phases. A read-only Technitium token is at `~/.technitium-ro-token` for diagnostics.

### Next build (Phase 3)
- [x] **Technitium DNS** — ✅ done. Deployed on **oneill** (CT 111, `YOUR_TECHNITIUM_IP`): DNS-only, OISD Big blocklist + DoH forwarders, console secured. Config applied declaratively by `provision-technitium.yml` via the Technitium API (from group_vars). DHCP cutover live on the **home VLAN**; IoT/guest use the gateway for DNS (DNS-by-VLAN-role — isolated VLANs can't reach a main-LAN resolver, and appliances break on blocklists; camera/management have no internet). Old apophis CT 111 destroyed; its address freed.
- [x] **[High] VM-level backups — Phase 3 ENTRY task** (**ADR-012**, infra-designer reviewed). oneill is the backup hub. **PBS done** (mgmt-vm imaged daily off-box; CTs reproducible from playbooks). **HA native partial backup confirmed landing** on the Samba share (CT 113) 2026-06-17. Remaining hardening tracked as carry-forwards (restore drill, PBS encryption).
- [ ] **Terraform import — DEFERRED to cluster scale** (ADR-008). Ansible (`pct`) creates + configures the LXCs for now and recovers cleanly; scaffold kept in `terraform/`. Revisit when the 3-node cluster lands (then: PVE API token, import live guests, refactor playbooks to config-only).
- [x] **Monitoring stack** (Prometheus + Grafana + Alertmanager → ntfy, all exporters) — ✅ done (CT 114, ADR-013).
- [x] **Dashboard** — ✅ done. **Glance** (not Homepage) on oneill (CT 115, ADR-014): native Go binary front-door, **single-page dashboard rendered from an Ansible template** (host/VM metrics via Prometheus + service status + alerts + releases), links to Grafana.

### Backups
- [x] Local config backup — done (ADR-007); now includes ansible inventory + host_vars.
- [x] **VM images via PBS** — PBS on oneill (CT 112), apophis wired (scoped token), scheduled daily (**VM 100 mgmt-vm** → keep 7d/4w), GC daily. (ADR-012) CTs excluded — reproducible from playbooks (mgmt-vm is the only guest not in code).
- [x] **[High] HA native backup — landing confirmed (2026-06-17).** Samba CT 113 (`provision-ha-backup-share.yml`) + HAOS scheduled **PARTIAL** backup; automatic backups are recurring onto the share (~131 MB each). **Scope verified** from `backup.json`: HA core + **Zigbee2MQTT** add-on + Mosquitto + Cloudflared, compressed, no media. (Optional: tune recorder `purge_keep_days` ~10–14.)
- [x] **[High] HA backup encryption key — saved off-box (2026-06-17).** HAOS backups are **encrypted** (`"protected": true`); the key (HAOS → Settings → System → Backups → ⋮ → "Show encryption key") is now stored in **Google Password Manager**. No credential manager is set up yet (ADR-010's Bitwarden bridge isn't live) — migrate the key there when one lands. Without the key the encrypted backup is unrestorable.
- [~] **Interim safety net — mgmt-vm cleared, HA held.** Deleted the `vzdump-qemu-100` (mgmt-vm) images on apophis `local` — PBS covers them off-box. **Kept `vzdump-qemu-200` (HA)** as the whole-VM fallback until the partial backup is verified *restorable* (drop it at the first restore drill — the partial backup is landing but its restore is still untested).
- [ ] **CT 111 reprovision drill** — destroy + re-run `provision-technitium.yml`, record actual RTO. Converts the "Ansible-rebuild is sufficient" claim into a tested fact before the lab grows.
- [x] **[High] PBS encryption — ENABLED 2026-06-17** (`pvesm set pbs-oneill --encryption-key autogen`; ADR-012). Verified: a manual backup logged `enabling encryption`. Key lives at `/etc/pve/priv/storage/pbs-oneill.enc` on apophis (**not** in any repo — it's a credential). The pre-encryption `…T16:30:03Z` snapshot stays as an unencrypted fallback. Key + fingerprint **saved off-box in Google Password Manager (2026-06-17)** — required for DR (if apophis dies, restore the key file to `/etc/pve/priv/storage/` before restoring encrypted backups). Don't lose it: no key ⇒ encrypted backups unrestorable.
- [x] **[High] First restore drill — PBS mgmt-vm restore: PASS (2026-06-17).** `qmrestore` of VM 100's PBS image to throwaway VMID 199 (`--unique 1`, NIC stripped so it can't conflict with the live mgmt-vm): restored in 24 s, **booted to a working OS** (guest agent up, hostname `mgmt-vm`), `group_vars/all.yml` present (the irreplaceable config) and the git repo intact; 199 destroyed `--purge`, VM 100 untouched. Recovery is now a tested fact, not a hypothesis. **Still untested: HA native partial restore** (separate drill — spin up a fresh HAOS + restore the partial) → that's what gates retiring `vzdump-qemu-200`.
- Note: PBS daily backup confirmed **healthy** — apophis is on **AEST (UTC+10)**, so the `02:30` schedule = `16:30 UTC`; the snapshot `…T16:30:03Z` is today's scheduled run (one restore point so far = the job has run once on its daily cadence).
- [ ] **Off-site copy (this is how we "back up oneill") — deferred (ADR-012).** oneill's services rebuild from code, but the backup *data* (PBS datastore + HA share) is a single copy until an encrypted off-site sync (cloud) exists. Don't copy it to apophis (circular/same-site). Recovery model in `docs/operations/runbooks.md`.

### Observability — Grafana build-out (backlog)
Prometheus is scraping (node/pve/UniFi/HA) and alerting works, but **Grafana itself is essentially empty** — the data's there, the dashboards aren't. Glance is the at-a-glance summary; Grafana is meant to be the deep surface (time-series history, network throughput, alert debugging, capacity planning). Backlog:
- [ ] **Build core dashboards as code:** Node Exporter Full (1860), UniFi (unpoller), Proxmox (pve-exporter), a Home Assistant panel. Provision via **Grafana provisioning files in Ansible** (ADR-013) so a rebuild restores them. `allowUiUpdates: true` is set — any live edits must be **exported back to the repo** or they're lost on the next playbook run.
- [ ] **Prometheus recording rules** for the repeated 24h-peak expressions (host/guest CPU·RAM) that the Glance dashboard computes inline — cheaper and reusable by both Grafana and Glance (per the Glance review note).
- [ ] Optionally a true installed-vs-latest **version-drift** signal (recording rule or small summary endpoint) — today Glance's "Installed Versions / Latest Releases" is visual comparison only.

### Small / quick
- [ ] Drop `--accept-routes` from `provision-tailscale.yml` and re-run (unnecessary on a subnet router).
- [ ] Confirm/reserve these in UniFi (fixed-IP entries or outside the DHCP pool): `YOUR_TAILSCALE_LAN_IP`, the monitoring CT, and the Glance CT (ADR-013/014) — reserve *before* provisioning to avoid DHCP collisions.
- [ ] Document the cross-subnet Zigbee path: how HA on `the LAN subnet` reaches the SLZB-06 at `YOUR_ZIGBEE_COORD_IP` today (becomes a firewall/route rule once VLANs land).

### Decisions to make
- [~] **Patching/update approach — ADR-015 ACCEPTED; guest track LIVE (2026-06-17).** `provision-patching.yml` configures all guest LXCs (110–115, discovered via `pct list`): `unattended-upgrades` **security/point-release only (Debian default, not `-updates`)**, **no auto-reboot**, timer pinned to **12:00 local** (`patching_timezone`, DST-safe), **ntfy on failure**. mgmt-vm + HA VM excluded (manual). Also fixed: PBS CT 112 shipped the `pbs-enterprise` repo (401) — `provision-pbs.yml` now disables it. **Remaining (host track):** codify the `pve-no-subscription` host-prep for the Proxmox nodes; run the manual monthly host+mgmt-vm window (last day, 12:00 AEST). Host visibility live via Glance.
- [x] **Version the agents** — `.claude/agents/*.md` and `.claude/skills/phase-gate/SKILL.md` are now published with narrow `.gitignore` exceptions. Transcripts, memory, settings, caches, and credentials stay private.

_Resolved this session:_ RAM trim (moot — services now spread across 3 nodes); Proxmox API Ansible modules (superseded by Terraform, ADR-008); drop the `100.x` IP (done — full decouple, ADR-006).
