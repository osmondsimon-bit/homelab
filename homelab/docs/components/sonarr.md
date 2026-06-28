# Sonarr (CT 123)

TV automation — Phase 7, ADR-022. Monitors wanted series, grabs releases via Prowlarr's indexers,
hands them to qBittorrent, then imports + renames (**hardlinked**) into `/media/library/tv`. Native
Servarr install (no Docker). LAN + Tailscale only.

| | |
|---|---|
| Host / CTID | **apophis** / CT 123 (unprivileged Debian 12 LXC, `nesting=1`) |
| IP / UI | `YOUR_SONARR_IP` — WebUI on `:8989` |
| Shape | 1 GB / 1 core / 8 GB rootfs |
| Packaging | native Servarr self-contained build in `/opt/Sonarr`, systemd unit, user `sonarr` |
| Media | the whole USB-SSD media root bind-mounted (`/mnt/usb-media` → `/media`) so downloads + library are **one filesystem** (hardlinks) |
| Ownership | `sonarr` joins the shared **media group** (in-CT gid 1000 → host 101000) + `UMask=0002` so imports hardlink and stay group-writable |
| Backup | **NONE by design** — config is small + reproducible; media isn't imaged |

## How it's managed

`provision-sonarr.yml` (idempotent): creates the CT, bind-mounts the media, installs Sonarr from the
**GitHub release** (the `services.sonarr.tv` updatefile endpoint serves a manifest, not a tarball —
`sonarr.servarr.com` returns one too), joins the media group, installs the systemd unit.

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-sonarr.yml --limit apophis
```

## First-run wiring (web UI)
- **Settings → Media Management →** add Root Folder `/media/library/tv`; tick **Use Hardlinks instead of Copy**.
- **Settings → Download Clients →** add qBittorrent (`YOUR_QBITTORRENT_IP:8080`, your password, category `tv`).
- Indexers arrive automatically from **Prowlarr** (configured there under Apps).

## Health / recovery
- **Health:** `http://<ip>:8989/ping` (200). **Logs:** `pct exec 123 -- journalctl -u sonarr`.
- **Hardlink check:** after an import, `stat` the file in downloads + library — same inode, link count ≥ 2.
- **Recovery:** reproducible from code → re-run `provision-sonarr.yml`, then re-link the download client + indexers. Media persists on the USB SSD. **Note:** the monitored-series list and quality profiles live only in Sonarr's SQLite DB inside the CT; a reprovision loses them — re-add from memory or a Sonarr backup export (Settings → System → Backup).

## Related
ADR-022 (media automation) · ADR-017 · [radarr.md](radarr.md) · [prowlarr.md](prowlarr.md) · [jellyfin.md](jellyfin.md) · [qbittorrent.md](qbittorrent.md).
