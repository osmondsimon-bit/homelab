# ADR-022: Media automation — Prowlarr + Sonarr + Radarr + Jellyseerr on apophis

**Date:** 2026-06-27
**Status:** Accepted (infra-designer-reviewed 2026-06-27 — Jellyseerr = Docker VM; required changes folded in below)

## Context

Phase 6 delivered the media *plumbing*: Jellyfin (CT 120, QuickSync) serves a library, qBittorrent
(CT 121, VPN killswitch) acquires into `/media/downloads`. The manual loop — find a release, add it
to qBittorrent, then rename/move the file into `/media/library/{movies,tv}` so Jellyfin matches it —
is the tedious part. The standard automation ("the *arr stack") closes that loop:

- **Prowlarr** — indexer manager: configure torrent indexers once, it syncs them to Sonarr/Radarr.
- **Sonarr** / **Radarr** — monitor wanted TV/movies, grab via Prowlarr's indexers, hand to
  qBittorrent, then **import + rename** into the library (hardlinked).
- **Jellyseerr** — the request front-end ("I want this show/movie") that talks to Jellyfin (library +
  users) and Sonarr/Radarr (fulfilment).

The deciding constraint is **hardlinks**: for an import to be instant and not double disk usage,
the download dir and the library must be on the **same filesystem** and visible to the *arr app
under a common mount. qBittorrent's `/media/downloads` and Jellyfin's `/media/library` are both on
the apophis USB SSD (`/mnt/usb-media`, ext4) — so the *arr apps **must be co-located on apophis**
(running them on oneill/carter would force a network share = cross-filesystem = no hardlinks).

## Decision

Four **unprivileged LXCs on apophis**, each bind-mounting the media as the existing CTs do
(`/mnt/usb-media` → `/media`, owned by the container-root host mapping). Provisioned + configured by
per-service playbooks; ADR-017 onboarding each.

| Service | CTID | Packaging | Media mount |
|---|---|---|---|
| Prowlarr | 122 | **native** (Servarr install, systemd) | none (indexer manager only) |
| Sonarr | 123 | **native** | `/media` (downloads + `library/tv`) |
| Radarr | 124 | **native** | `/media` (downloads + `library/movies`) |
| Jellyseerr | 125 (VM) | **Docker VM** (official image; Ubuntu 24.04, like Vaultwarden VM 118) | none (API coordinator only) |

- **Native for the trio:** Prowlarr/Sonarr/Radarr ship clean official Linux installs (systemd
  units, pinned versions) — no Docker, matching the lab's native-binary norm.
- **Docker for Jellyseerr (2nd ADR-014 exception) — in a dedicated VM (VMID 125):** Jellyseerr is
  distributed Docker-first; the native path is a fragile Node-from-source build (the pnpm/Node-drift
  problem ADR-014 rejected for Homepage). It runs the official container in a **dedicated Ubuntu 24.04
  VM, same pattern as Vaultwarden (VM 118)** — keeping ADR-014's "Docker confined to single-purpose
  VMs" principle exact and avoiding the `nesting=1`/`keyctl` kernel surface of Docker-in-unprivileged-
  LXC (infra-designer decision 2026-06-27). Jellyseerr needs no media mount and no privileges, so the
  VM loses nothing; ~1 GB RAM.
- **Hardlinks / ownership:** Sonarr/Radarr run **as root inside their unprivileged CTs** (same as
  qBittorrent) so they own and can hardlink across `/media/downloads` → `/media/library/*` (same
  ext4, host UID 100000). qBittorrent categories (`tv`, `movies`) map to subpaths the *arr apps watch.
- **Networking / exposure:** **LAN + Tailscale only, no inbound.** **Only qBittorrent stays behind
  the VPN** — the *arr apps + Jellyseerr run on the LAN and reach qBittorrent's API; Prowlarr's
  indexer queries go clearnet (standard; can be routed via the VPN CT later if wanted). Remote
  Jellyseerr requests (Cloudflare Tunnel) are a **separate future decision**, not in scope here.
- **Wiring:** Prowlarr → indexers → Sonarr/Radarr; Sonarr/Radarr → qBittorrent (download client) +
  root folders on `/media/library`; Jellyseerr → Jellyfin + Sonarr + Radarr. Cross-app API keys are
  auto-generated; qBittorrent's Web-UI password (Sonarr/Radarr need it) + indexer creds live in the
  gitignored vars / are set post-provision.
- **Sizing:** right-size small — Prowlarr ~512 MB, Sonarr/Radarr ~1 GB, Jellyseerr ~1 GB (~3.5 GB
  total). VMIDs 122–125; operator reserves four IPs in UniFi before provisioning.

## Consequences

- **Second Docker exception (Jellyseerr).** Docker now exists in two confined spots (Vaultwarden VM,
  Jellyseerr CT) — the service-LXC-native norm otherwise holds. Consistency vs the "Docker in VMs"
  wording of ADR-014 is the main thing for the gate to rule on (LXC vs VM for Jellyseerr).
- **Four more guests on apophis to monitor + patch.** Justified by the automation payoff; offset by
  small footprints. Pushes apophis RAM to ~28 GB of 32 — workable but the tightest the node has been;
  a future rebalance (or the long-deferred storage/NAS move) may be needed if the stack grows.
- **Hardlinks depend on getting the shared ownership right** (the unprivileged-LXC shared-storage
  detail the infra-designer flagged in ADR-021). If wrong, imports silently fall back to slow copies
  + double disk use — must be verified at provisioning (hardlink test: import a file, confirm inode
  link count > 1).
- **Some indexers need FlareSolverr** (Cloudflare challenge solver) — deferred as an optional add-on
  CT if specific indexers require it, not built up front.
- **Jellyseerr is the natural future Cloudflare-Tunnel candidate** (requesting media while away) —
  recorded as the likely first remote-exposure case, to be its own ADR + security review if pursued.
- New playbooks: `provision-prowlarr.yml`, `provision-sonarr.yml`, `provision-radarr.yml`,
  `provision-jellyseerr.yml`. Gated by the infra-designer review + `/security-review` before build.

## infra-designer review — 2026-06-27 (APPROVE-WITH-CONCERNS; required before provisioning)

Architecture sound; co-location on apophis for hardlinks confirmed mandatory. RAM fits: 24.25 GB
committed today + ~3.5 GB (*arr trio) + ~1 GB (Jellyseerr VM) ≈ **28.75 GB of 32**; ZFS ARC contracts
under peak load — accepted (same as ADR-021; ext4-on-USB isn't ARC-cached anyway). Jellyseerr → **VM**
(resolved above).

**Blocking before provisioning:**
1. **Close Phase 6 first** — set the qBittorrent Web-UI password + run `/phase-gate` before wiring
   Sonarr/Radarr to qBit's API (else they're configured against an un-hardened qBit).
2. **Media-ownership model — THIS ALREADY BIT US (2026-06-27).** The shared `/media` must be
   **readable by Jellyfin** (uid 100103) **and writable by qBittorrent + Sonarr/Radarr** (root = host
   100000) so imports **hardlink**. `provision-jellyfin.yml` currently chowns the library to
   `100000:100000`, which **broke Jellyfin reads** — the operator manually chowned the library tree to
   `100103`; left as-is, re-running that playbook would revert the fix AND block *arr writes. **Fix
   before Phase 7:** a shared **media group** (a gid mapped into CT 120/121/123/124), media dirs
   `chown :media` + `chmod 2775` (setgid) so new files inherit the group; jellyfin + each *arr root
   joined to it. **Do NOT re-run `provision-jellyfin.yml` until this lands** (it would clobber the
   manual chown).

**Required at provisioning (per CT 122–125):** ADR-017 onboarding — Glance tiles + `glance_release_repos`,
GuestDown id-map, `docs/components/{prowlarr,sonarr,radarr,jellyseerr}.md`, backup-freshness exclusion
(reproducible-from-playbook, not imaged), reprovision drill recorded. Enable **"Use Hardlinks"** in
Sonarr/Radarr + verify the inode link-count (`= 2`, same inode) on first import. Reserve 4 UniFi IPs
first. FlareSolverr deferred (own CT if an indexer needs it).

**Recorded risk:** Prowlarr indexer queries egress the **home WAN IP** (not the VPN) — logged by the
indexers, separate from torrent traffic. Accepted; route Prowlarr via the VPN CT later if wanted.
*(Superseded by the revision below — Prowlarr was moved behind a VPN.)*

## Revision — 2026-06-27 (Prowlarr moved behind a VPN — AU ISP site-blocking)

As-built, the native-LXC Prowlarr (CT 122, LAN-only) **could not reach many indexers**: Australian
ISPs site-block the indexer domains, so queries from the home WAN IP fail *before* Cloudflare even
applies. The fix (per Servarr/TRaSH guidance + the `cf_clearance` cookie-IP rule): **Prowlarr must
egress via a VPN** — which also keeps a consistent exit IP for any Cloudflare solver.

**As-built change:** Prowlarr is now a **Docker container behind Gluetun on VM 125** (the Jellyseerr
VM already runs Docker), `network_mode: service:gluetun`, on a **2nd ProtonVPN WireGuard exit** (no
port-forwarding). Its WebUI is published on the VM IP `:9696`; Gluetun's `FIREWALL_OUTBOUND_SUBNETS`
lets it still reach Sonarr/Radarr on the LAN. **The native Prowlarr CT 122 is retired** (`.21` freed).
Egress verified = ProtonVPN exit, not the home WAN. **ByParr/FlareSolverr dropped** — the VPN alone
fixes the blocking; a CF solver is only added back (behind the same Gluetun) if a specific indexer
demands it. This supersedes the "Prowlarr native LXC, LAN-only" parts of the decision above. The
`provision-prowlarr.yml` native playbook is removed; VM 125 is built by `provision-jellyseerr.yml`.
