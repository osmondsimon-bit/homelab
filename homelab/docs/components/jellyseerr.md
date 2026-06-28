# Jellyseerr (VM 125)

Request UI for the media stack — Phase 7, ADR-022. Users search and request movies/shows; Jellyseerr
authenticates **via Jellyfin** and hands requests to Sonarr/Radarr. Runs the official container in a
dedicated Ubuntu 24.04 Docker VM (ADR-014 Docker exception #2, like Vaultwarden) — which also hosts
the indexer-VPN stack (Gluetun + Prowlarr + ByParr).

| | |
|---|---|
| Host / VMID | **apophis** / VM 125 (Ubuntu 24.04, Docker; CPU `Skylake-Client-noTSX-IBRS`, migratable) |
| IP / UI | `YOUR_JELLYSEERR_IP` — `:5055` (LAN/Tailscale only; **LAN-direct**, *not* behind the VPN) |
| Shape | 3 GB / 2 cores / 20 GB (RAM + disk sized for ByParr's headless browser) |
| Co-tenants | `gluetun` + `prowlarr` + `byparr` (the indexer-VPN sidecars — see [prowlarr.md](prowlarr.md)) |
| Image | `fallenbagel/jellyseerr` (pinned tag); container `no-new-privileges` |
| Backup | NONE by design — small SQLite config, reproducible |

## How it's managed

`provision-jellyseerr.yml` — play 1 creates the VM on apophis (cloud-init), play 2 deploys the Docker
compose over SSH. Run it **without `--limit`** (play 1 is scoped to apophis; play 2 targets the VM).

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-jellyseerr.yml
```

## First-run wiring (web UI)
- Open `http://<ip>:5055` → **Sign in with Jellyfin** (`http://YOUR_JELLYFIN_IP:8096`, your Jellyfin login).
- **Settings → Services →** add Sonarr (`:8989`) + Radarr (`:7878`) with API keys + default root folders (`/media/library/{tv,movies}`) + quality profiles.

## Health / recovery
- **Health:** `http://<ip>:5055/api/v1/status` (200).
- **Recovery:** reproducible → re-run `provision-jellyseerr.yml` (needs `jellyseerr_ip` + `prowlarr_vpn_wg_config` in gitignored `all.yml`). Redo the Jellyfin sign-in + service links.

## Related
ADR-022 · ADR-014 (Docker exception #2) · [prowlarr.md](prowlarr.md) · [jellyfin.md](jellyfin.md).
