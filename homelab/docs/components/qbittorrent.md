# qBittorrent (CT 121)

Torrent client — Phase 6b, ADR-021. All egress is forced through a **ProtonVPN WireGuard** tunnel
with an **nftables killswitch**; torrents also bind to `wg0`. A tunnel drop = **zero leak**.
**LAN + Tailscale only — no inbound from the internet** (peer connections arrive via the
NAT-PMP-forwarded port through the tunnel).

| | |
|---|---|
| Host / CTID | **apophis** / CT 121 (unprivileged Debian 13 LXC, `nesting=1`; `/dev/net/tun` passed in for WireGuard) |
| IP | `YOUR_QBITTORRENT_IP` (static; reserved in UniFi) — Web-UI on `:8080` |
| Shape | 2 GB / 2 cores / 8 GB rootfs |
| VPN | ProtonVPN WireGuard `wg0` (P2P server); config is the secret `qbittorrent_wg_config` (gitignored). qBittorrent binds torrents to `wg0`. |
| Killswitch | `nftables` default-drop **output** — only `lo`, established, `wg0`, and the WG handshake to the Proton endpoint leave; **DNS forced through the tunnel** (no LAN/clearnet DNS) |
| Port forward | `natpmpc` renewal timer (every 45 s) keeps a Proton NAT-PMP port alive; set qBittorrent's listen port to match |
| Storage | downloads bind-mounted from the USB SSD — `/mnt/usb-media/downloads` → `/media/downloads` (shared with Jellyfin) |
| Backup | **NONE by design** — downloads are replaceable; config not imaged (not a `BackupAbsent` target) |
| Runtime | qBittorrent 5 from Debian 13 stable; upgraded from Debian 12's qBittorrent 4.5.2 after its resume checker wedged on a partial torrent |

## How it's managed

Provisioned **and** configured by `homelab/ansible/playbooks/provision-qbittorrent.yml` (idempotent;
refuses to run until `qbittorrent_ip` + `qbittorrent_wg_config` are set in the gitignored `all.yml`):

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-qbittorrent.yml --limit apophis
```

qBittorrent runs as root **inside the unprivileged CT** (so it can write the shared
`/media/downloads`, owned by the container-root host mapping) — the container boundary is the
security control, not the in-container user. The `lxc.*` tun-passthrough lines use `lineinfile`
(pct strips comment markers).

> **First-run hardening (do immediately):** this qBittorrent version ships the **default login
> `admin` / `adminadmin`** and the Web-UI is on the LAN → log in at `http://YOUR_QBITTORRENT_IP:8080`
> and **change the password** (Tools → Options → Web UI). Then set the incoming-connection **port to
> the NAT-PMP forwarded port** (`journalctl -u natpmp-renew`).

## Health / operations

- **Leak-test (run before trusting, and after any VPN/killswitch change):** see
  [operations/runbooks.md → qBittorrent](../operations/runbooks.md). Proven ✅ 2026-06-27 — CT egress
  was a ProtonVPN IP (≠ home WAN), and dropping `wg0` blocked both curl and DNS.
- **Glance:** monitor tile (`http://…:8080`). **GuestDown** covers `lxc/121`.
- **Tunnel status:** `pct exec 121 -- wg show wg0`. **Logs:** `pct exec 121 -- journalctl -u qbittorrent`.

## Recovery

Reproducible from code → re-run `provision-qbittorrent.yml` (needs `qbittorrent_wg_config` +
`qbittorrent_ip` in the gitignored `all.yml`). Not imaged; downloads on the USB SSD persist. If the
ProtonVPN config is rotated, update `qbittorrent_wg_config` and re-run.

The one-time Debian 12→13 migration is codified in `upgrade-qbittorrent-debian13.yml`. It requires
`-e qbittorrent_upgrade_confirm=true`, retains the direct ZFS rootfs snapshot
`rpool/data/subvol-121-disk-0@pre-debian13-qbittorrent5`, preserves the Proxmox CT config at
`/root/ct-121-pre-debian13.conf`, and reruns the VPN route plus negative killswitch checks. A normal
Proxmox CT snapshot is unavailable because of the bind mount. To roll back, stop CT 121, run
`zfs rollback -r rpool/data/subvol-121-disk-0@pre-debian13-qbittorrent5`, then start CT 121. The
bind-mounted media SSD is outside that snapshot; do not interpret a rootfs rollback as a media rollback.

qBittorrent 5 needs both `Session\Interface=wg0` and `Session\InterfaceName=wg0` in its configuration.
The provisioning and migration playbooks enforce both; startup logs must say it is trying to listen on
`wg0`, not `0.0.0.0`. During a negative leak test, stop `natpmp-renew.timer` and qBittorrent before
stopping WireGuard. The NAT-PMP service requires `wg-quick@wg0` and can otherwise race the stop by
starting WireGuard again.

## Related

ADR-021 (media stack) · ADR-003 (no inbound; VPN egress) · ADR-017 (observability/continuity) ·
[jellyfin.md](jellyfin.md) (shares `/media/downloads`) · [operations/runbooks.md](../operations/runbooks.md).
