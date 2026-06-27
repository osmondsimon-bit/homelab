# Jellyfin (CT 120)

Media server (open source, no licence) — Phase 6a, ADR-021. Serves media off the 500 GB USB-C SSD
on apophis, with **Intel QuickSync** hardware transcode via iGPU passthrough. **LAN + Tailscale only —
no inbound from the internet** (ADR-003).

| | |
|---|---|
| Host / CTID | **apophis** / CT 120 (unprivileged Debian 12 LXC — **not** a VM; `nesting=1`) |
| IP | `YOUR_JELLYFIN_IP` (static; reserved in UniFi) — UI on `:8096` |
| Shape | 2 GB / 2 cores / 8 GB rootfs |
| iGPU | UHD 630 passed through: `/dev/dri` bind + cgroup allow `c 226:0` / `c 226:128`; host **render GID 993** mapped 1:1 into the CT; `jellyfin` user in that group |
| Storage | media bind-mounted from the USB SSD — `/mnt/usb-media/library` → `/media/library`, `/mnt/usb-media/downloads` → `/media/downloads` (ext4, by-id, `nofail`) |
| Service config | on the CT **rootfs** (internal SSD), `/var/lib/jellyfin` — deliberately **not** on the USB disk |
| Backup | **NONE by design** — media is replaceable; Jellyfin config is small + semi-reproducible. Not PBS-imaged (so invisible to `BackupAbsent`/`BackupStale`). |

## Why an unprivileged LXC (not a VM)

QuickSync via `/dev/dri` passthrough into an **unprivileged LXC** keeps the iGPU shared with the host
(no exclusive VFIO grab — Frigate at the new house stays possible), and the media on the USB SSD is
shared with the (future) qBittorrent CT by trivial host bind-mounts rather than virtiofs/NFS. Only the
host `render` GID is mapped in; the UID map stays fully unprivileged. See ADR-021.

## How it's managed

Provisioned **and** configured by `homelab/ansible/playbooks/provision-jellyfin.yml` (idempotent):

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-jellyfin.yml --limit apophis
```

The `lxc.*` passthrough/idmap lines are written with `lineinfile` (not `blockinfile`) because **pct
strips unrecognized comment lines** from the CT config — markers don't survive, so a re-run would
otherwise duplicate the idmap and break boot.

> **First-run (operator, over LAN/Tailscale — the setup wizard has no auth):** open
> `http://YOUR_JELLYFIN_IP:8096` → create the admin account → Dashboard → Playback → **Hardware
> acceleration = VAAPI** (or Intel QSV), device `/dev/dri/renderD128`. Add the library pointing at
> `/media/library`.

## Health / operations

- **Smoke-test (HW transcode usable):** as the jellyfin user inside the CT —
  `runuser -u jellyfin -- /usr/lib/jellyfin-ffmpeg/vainfo --display drm --device /dev/dri/renderD128`
  should list `VAProfileH264*`/`VAProfileHEVC*` with `VAEntrypointVLD` (decode) **and** `EncSlice`
  (encode). Confirmed ✅ 2026-06-27. In a live transcode the codec shows `h264_qsv` and host-side
  `intel_gpu_top` shows the render engine active.
- **Glance:** monitor tile (`http://…:8096/System/Info/Public`). **GuestDown** covers `lxc/120`.
- **Logs / restart:** `pct exec 120 -- journalctl -u jellyfin` / `… systemctl restart jellyfin`.

## Recovery

Reproducible from code — **no image backup**. To rebuild: re-run `provision-jellyfin.yml`, then redo
the setup wizard and re-add the library at `/media/library`. The **media survives** on the USB SSD
(independent of the CT); only Jellyfin's own config (accounts, watch state) is lost and is cheap to
recreate. If the USB disk drops and reconnects, remount on apophis (`mount -a`) and restart the CT.

## Related

ADR-021 (media stack) · ADR-014 (Docker confinement — Jellyfin is native, no Docker) ·
ADR-017 (observability/continuity by default) · [operations/runbooks.md](../operations/runbooks.md).
