# Prowlarr (on VM 125, behind a VPN)

Indexer manager for the *arr stack — Phase 7, ADR-022. Configure indexers once; it syncs them to
Sonarr/Radarr. **Runs behind a ProtonVPN tunnel** (Gluetun) because Australian ISPs site-block many
indexer domains *and* the VPN keeps a consistent exit IP for Cloudflare solving.

| | |
|---|---|
| Host / VMID | **apophis** / VM 125 (the Docker VM, shared with Jellyseerr) |
| WebUI | `http://YOUR_JELLYSEERR_IP:9696` (published on the VM IP by Gluetun) |
| Packaging | `lscr.io/linuxserver/prowlarr` Docker container, **`network_mode: service:gluetun`** (digest-pinned) |
| VPN | **Gluetun** → a 2nd ProtonVPN WireGuard exit (no port-forwarding); egress verified ≠ home WAN |
| Cloudflare | **ByParr** (FlareSolverr-compatible solver) shares Gluetun's netns → Prowlarr reaches it at `http://localhost:8191`; tag CF-gated indexers (e.g. 1337x) |
| DNS | Gluetun's own resolver (DoT over the VPN) — **not** Technitium |
| LAN reachback | Gluetun `FIREWALL_OUTBOUND_SUBNETS` = the LAN, so Prowlarr still reaches Sonarr/Radarr |
| Backup | NONE by design — config small + reproducible |

## Why behind a VPN (not the original native LXC)

The first-cut native LAN-only Prowlarr (CT 122, **retired**) couldn't reach indexers — AU ISPs block
the domains from the home IP, *before* Cloudflare even applies. Routing Prowlarr (and any CF solver)
through a VPN fixes the block and keeps **one consistent exit IP** so the `cf_clearance` cookie stays
valid. See ADR-022 (revision 2026-06-27).

## How it's managed

Built alongside Jellyseerr by `provision-jellyseerr.yml` — one Docker compose on VM 125
(jellyseerr LAN-direct + gluetun + prowlarr + byparr). The 2nd ProtonVPN WireGuard config is
`prowlarr_vpn_wg_config` in the gitignored `all.yml` (parsed into Gluetun's env).

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-jellyseerr.yml
```

## First-run wiring
- **Settings → Apps →** add Sonarr (`:8989`) + Radarr (`:7878`) with their API keys → indexers sync to them.
- **Settings → Indexers → Indexer Proxies →** add **FlareSolverr**, host `http://localhost:8191`, give it a tag; tag the Cloudflare indexers (1337x) with that tag. (CF solves are slow — first hit ~15–40 s; the cookie is then cached.)
- Leave non-Cloudflare indexers (Pirate Bay, LimeTorrents) **untagged** so they stay fast + direct.

## Health / verify
- **Health:** `http://<vm-ip>:9696/ping` (200).
- **VPN egress (the whole point):** `ssh simon@<vm> 'sudo docker exec gluetun wget -qO- https://api.ipify.org'` → a ProtonVPN IP, **not** the home WAN.
- **Recovery:** reproducible → re-run `provision-jellyseerr.yml`; re-add indexers + the FlareSolverr proxy (`http://localhost:8191`); re-add Sonarr/Radarr under Apps. Any indexer credentials (registered-site logins) must be re-entered from **Vaultwarden** — they live only in Prowlarr's SQLite DB and are lost on reprovision. Verify VPN egress after rebuild.

## Related
ADR-022 (+ 2026-06-27 revision) · ADR-014 (Docker exception) · [jellyseerr.md](jellyseerr.md) · [sonarr.md](sonarr.md) · [radarr.md](radarr.md) · [qbittorrent.md](qbittorrent.md).
