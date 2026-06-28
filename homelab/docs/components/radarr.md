# Radarr (CT 124)

Movie automation — Phase 7, ADR-022. Monitors wanted movies, grabs releases via Prowlarr's indexers,
hands them to qBittorrent, then imports + renames (**hardlinked**) into `/media/library/movies`.
Native Servarr install (no Docker). LAN + Tailscale only.

| | |
|---|---|
| Host / CTID | **apophis** / CT 124 (unprivileged Debian 12 LXC, `nesting=1`) |
| IP / UI | `YOUR_RADARR_IP` — WebUI on `:7878` |
| Shape | 1 GB / 1 core / 8 GB rootfs |
| Packaging | native Servarr self-contained build in `/opt/Radarr`, systemd unit, user `radarr` |
| Media | the whole USB-SSD media root bind-mounted (`/mnt/usb-media` → `/media`) so downloads + library are **one filesystem** (hardlinks) |
| Ownership | `radarr` joins the shared **media group** (in-CT gid 1000 → host 101000) + `UMask=0002` so imports hardlink and stay group-writable |
| Backup | **NONE by design** — config is small + reproducible; media isn't imaged |

## How it's managed

`provision-radarr.yml` (idempotent): creates the CT, bind-mounts the media, installs Radarr from the
`radarr.servarr.com` updatefile endpoint, joins the media group, installs the systemd unit.

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-radarr.yml --limit apophis
```

## First-run wiring (web UI)
- **Settings → Media Management →** add Root Folder `/media/library/movies`; tick **Use Hardlinks instead of Copy**.
- **Settings → Download Clients →** add qBittorrent (`YOUR_QBITTORRENT_IP:8080`, your password, category `movies`).
- Indexers arrive automatically from **Prowlarr** (configured there under Apps).

## Health / recovery
- **Health:** `http://<ip>:7878/ping` (200). **Logs:** `pct exec 124 -- journalctl -u radarr`.
- **Hardlink check:** after an import, `stat` the file in downloads + library — same inode, link count ≥ 2.
- **Recovery:** reproducible from code → re-run `provision-radarr.yml`, then re-link the download client + indexers. Media persists on the USB SSD.

## Related
ADR-022 (media automation) · ADR-017 · [sonarr.md](sonarr.md) · [prowlarr.md](prowlarr.md) · [jellyfin.md](jellyfin.md) · [qbittorrent.md](qbittorrent.md).
