# ADR-021: Media stack — Jellyfin + torrent client on apophis, USB-SSD storage

**Date:** 2026-06-27
**Status:** Accepted (infra-designer-reviewed 2026-06-27 — required changes folded in below)

## Context

Phase 6 (Media) — the last planned phase. PLAN has long named **Jellyfin** (open source, no
licence; preferred over Plex) for serving media and **qBittorrent behind a VPN killswitch** for
acquisition, both on **apophis** (its i7-8700T iGPU / UHD 630 is the only QuickSync transcoder in
the lab). The trigger: a spare **500 GB USB-C SSD** to plug into apophis as a low-commitment way to
*start* a media stack and see whether it's worth growing into a NAS — explicitly a "try it small"
bet, not a permanent storage design.

Constraints carried in from earlier ADRs:
- **Docker-free service nodes (ADR-014).** Docker exists in the lab exactly once — confined to the
  Vaultwarden VM (118). The media phase was the *anticipated* place Docker would arrive (via
  Gluetun). This ADR revisits whether that's actually necessary.
- **No inbound from the internet (ADR-003).** Remote access is Tailscale / Cloudflare Tunnel only.
- **Observability & continuity by default (ADR-017).** Every new guest/storage gets monitoring,
  alerting, a recorded backup *decision*, and a restore note.
- **Back up what code can't recreate (ADR-012).** Media is replaceable bulk data.

ProtonVPN: the operator will subscribe to **Plus/Unlimited** (free tier forbids P2P; Plus adds
port forwarding) before the torrent leg is built — so the work **phases** naturally.

## Decision

Build the media stack on **apophis**, in **two sub-phases**, all in **unprivileged LXCs** (not VMs)
so the USB-SSD storage can be shared by trivial host bind-mounts rather than virtiofs/NFS.

### 6a — Storage + Jellyfin (no VPN dependency; build first)

- **Storage:** the 500 GB USB-C SSD, mounted on apophis by `/dev/disk/by-id/...` (stable across
  re-enumeration), formatted **ext4**, added as a Proxmox **directory** storage. Layout
  `/media/{library,downloads}`, bind-mounted into the LXCs. **ext4 single-disk, not ZFS** — media is
  disposable, and a single USB device gains nothing from ZFS redundancy while inheriting USB-reset
  fragility. **Stateful service config (Jellyfin DB/metadata, qBittorrent settings) stays on apophis's
  internal SSD**, never on the USB disk — so a USB dropout can't corrupt service state.
- **Jellyfin:** unprivileged LXC (proposed **CTID 120**, `YOUR_JELLYFIN_IP`, ~2 cores / 2 GB,
  rootfs 8 GB) with the iGPU passed through — bind-mount `/dev/dri/renderD128` (+ `card0`), the
  cgroup2 device allow, and the render-group GID mapped — for **QuickSync hardware transcode**. No
  VFIO/VM passthrough: the host keeps the GPU, no exclusive grab, and it's reproducible from a
  playbook. Provisioned by a new `provision-jellyfin.yml`.
- **Exposure:** **LAN + Tailscale only**, no public hostname (ADR-003). Off-network streaming via a
  Cloudflare Tunnel is deferred as a separate decision (only if wanted).

### 6b — Torrent client + VPN killswitch (gated on ProtonVPN Plus)

- **Acquisition:** qBittorrent in an unprivileged LXC (proposed **CTID 121**, `YOUR_QBIT_IP`,
  ~2 cores / 2 GB), all egress forced through a **ProtonVPN WireGuard** tunnel with a **killswitch**
  (default-drop `nftables`: traffic leaves only via `wg0`, plus a LAN-management exception; if the
  tunnel drops, torrent traffic stops — no leak). **NAT-PMP** (`natpmpc` renew loop) claims the
  forwarded port Proton hands out. Bind-mounts `/media/downloads` (shared with Jellyfin, which
  imports completed files from the same path).
- **No Docker / no Gluetun (recommended).** Gluetun's only value is bundling VPN + killswitch +
  port-forwarding into a container — but qBittorrent (`qbittorrent-nox`), WireGuard, `nftables`, and
  `natpmpc` are all **native packages**, matching the lab's native-binary pattern (Technitium,
  Glance, Tailscale, Prometheus). A native WireGuard + nftables killswitch achieves the identical
  outcome **without a second Docker exception**, keeping every service LXC Docker-free. *(Fallback: if
  the native killswitch proves unreliable in testing, fall back to **Gluetun in this LXC** as the
  documented ADR-014 exception #2 — but that is the fallback, not the default. This supersedes
  ADR-014's assumption that Gluetun forces Docker in Phase 6.)*

### Cross-cutting

- **Backups (ADR-012/017):** the **media library + downloads are NOT backed up** — replaceable bulk
  data, single USB copy by design. Jellyfin/qBittorrent **config** is small and only semi-reproducible
  (users, watch state, torrent list) → a tiny periodic config-dir copy to the oneill share, or accept
  loss + re-scan; decided at onboarding. Registered in backup-freshness so the "not backed up by
  design" decision is explicit, not an oversight.
- **Monitoring/dashboards (ADR-017):** both CTs get node_exporter + GuestDown coverage + a Glance
  tile; USB-SSD free-space added to the storage panel/alerts.
- **Network:** both CTs on the Home VLAN (clients stream from there); qBittorrent's egress is the
  tunnel regardless of VLAN. A dedicated media VLAN is possible later but unnecessary now.

## Consequences

- **Single USB SSD is not redundant** and USB devices can drop under sustained load — accepted for
  disposable media. Mitigations: `by-id` mount, service state off the USB disk, free-space alerting.
  The **growth path is a NAS** (deferred to the new house) — this stack is deliberately the cheap
  trial that informs whether that investment is worth it.
- **Keeps the lab Docker-free except Vaultwarden's VM** if the native killswitch holds — a cleaner
  outcome than ADR-014 anticipated. The cost is hand-rolling the WireGuard + nftables killswitch
  instead of inheriting Gluetun's; the killswitch **must be leak-tested** (kill the tunnel → confirm
  zero egress, no DNS leak) before the client is trusted.
- **Two new LXCs + new storage + iGPU passthrough** → this ADR is the design record; gated by the
  **infra-designer** review and **/security-review** before provisioning, per CLAUDE.md.
- **apophis RAM:** ~12 GB free today; the two CTs (~2 GB each) fit with headroom alongside mgmt-vm,
  HA, Vaultwarden, Tailscale.
- **iGPU is shared** between host and the Jellyfin LXC (no exclusive VM grab), so adding a second
  consumer later (e.g. Frigate at the new house) stays possible.
- New playbooks: `provision-jellyfin.yml` (6a) and `provision-qbittorrent.yml` (6b). VMIDs 120/121
  and IPs are proposals pending a UniFi reservation *before* provisioning (the Glance `.12`
  DHCP-collision lesson).

## infra-designer review — 2026-06-27 (required changes, must clear before provisioning)

Verdict **APPROVE-WITH-CHANGES**. Architecture sound; RAM headroom confirmed (~20.25 GB allocated of
32 → the two 2 GB CTs fit). Blockers folded in:

1. **iGPU passthrough specifics (6a):** `provision-jellyfin.yml` must map the host `render` GID and
   allow both DRI devices. **As-found on apophis 2026-06-27:** iGPU = Intel **UHD Graphics 630**
   (CoffeeLake-S, QuickSync ✓); **`render` GID = 993** (NOT the usual 104 — verify, don't assume);
   `/dev/dri/renderD128` = char **226:128** (render group), `/dev/dri/card0` = **226:0** (video
   group). So: `lxc.idmap` for GID 993, the `dev0`/`dev1` entries for card0+renderD128, **and**
   `lxc.cgroup2.devices.allow = c 226:0 rwm` + `c 226:128 rwm`; the Jellyfin process must be in the
   `render` group inside the CT. `nesting=0` is fine. **Smoke-test in the runbook:** confirm a
   transcode reports `h264_qsv` (not `libx264`) and `intel_gpu_top` shows the render engine active —
   missing either device/allow line = silent software fallback.
2. **USB mount (6a):** fstab entry must be `by-id` with **`nofail,x-systemd.device-timeout=10`** (else
   apophis hangs at boot without the disk). Document the reconnect-recovery step (`mount -a` +
   `pvesm enable usb-media`) in the runbook. Jellyfin DB (`/var/lib/jellyfin`) + qBit settings stay
   on rootfs/internal SSD, never the USB disk.
3. **Killswitch (6b):** the nftables policy in `provision-qbittorrent.yml` must include the
   **WireGuard-UDP-establishment rule on the physical NIC** (most-missed; without it `wg0` can never
   come up → permanent lockout), a LAN-management exception (keeps SSH/console when the tunnel is
   down), and **DNS forced through the tunnel** (a UDP/53 allow to Technitium in the LAN exception is
   a leak path). NAT-PMP renew loop must run faster than the ~60 s lease (≈45 s timer).
   **Leak-test (must pass, in the runbook) before trusting the client:** (a) in-CT egress IP is a
   Proton exit, not home WAN; (b) `wg0` down → `curl`/`dig` both time out (no leak); (c) `wg0` up →
   resumes; (d) DNS-leak test returns Proton resolvers, not Technitium/ISP.
4. **qBittorrent hardening (6b):** set a Web-UI password and bind the Web-UI to the management IP
   (not `0.0.0.0`) in the playbook — fresh qBit has no auth.
5. **Jellyfin hardening (6a):** known admin account + disable open user registration post-setup.
6. **ADR-017 backup-freshness:** confirm `backup-freshness.sh` will **not** fire `BackupAbsent` for
   CTs 120/121 (add an exclusion if it auto-discovers); decide config handling explicitly — either a
   tiny config-dir copy to the oneill share + a reprovision drill for CT 120, or record "config loss
   accepted, library re-scans" with reasoning. Plus the one-line `glance_services` tiles + GuestDown
   id-map comment for 120/121.
7. **Pre-provision gates:** reserve the 120/121 IPs in UniFi first; verify the scoped PBS token can't
   enumerate the USB datastore (media must never be imaged); `/security-review` before build.

## Revision — 2026-07-21 (500 GB storage management)

The initial free-space card is supplemented by a daily, metadata-only inventory on apophis. It
deduplicates by device/inode so imported files hardlinked between downloads and the library count
once, identifies download-only allocations, and exposes bounded top-title/top-file rankings to the
LAN/Tailscale-only Glance Media page. The inventory is informational and cannot remove files;
cleanup remains deliberate in the owning media application. Capacity sampling stays a separate
six-hour service so a deeper directory walk cannot weaken mount or low-space detection.
