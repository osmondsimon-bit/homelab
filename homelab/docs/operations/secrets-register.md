# Secrets register

Companion to [ADR-018](../../decisions/018-secrets-management.md) (tiered secrets model) and
[ADR-010](../../decisions/010-password-manager.md) (Vaultwarden). This is the **inventory of what
credentials exist and where each lives** — deliberately **no values and no addresses** (those live
only in Vaultwarden, Keychain, or gitignored env files per ADR-006). Keep it current when a service
is added or a credential moves tier. Account identifiers are intentionally omitted and remain with
the corresponding Vaultwarden item or protected local configuration.

Built from the access audit of 2026-06-26 (first population of Vaultwarden).

## Tier 1 — Vaultwarden (human-typed logins)

Folder layout in the vault: `Homelab/Proxmox`, `Homelab/Services`, `Homelab/Network`, `Homelab/External`.

| Credential | Notes |
|------------|-------|
| Proxmox apophis | Cluster `/etc/pve` shared with carter — same login. |
| Proxmox carter | Same cluster-wide password as apophis. |
| Proxmox oneill | **Standalone** node — independent password. |
| Proxmox Backup Server | Reset if forgotten (was prompt-only). PBS *encryption key* is Tier 2. |
| Grafana | Pasted back at `provision-monitoring.yml` prompt. |
| Technitium DNS — primary (CT 111) | Secondary shares this password (same playbook loop). |
| Technitium DNS — secondary (CT 117) | Config-identical to primary. |
| Home Assistant | HA backup *encryption key* is Tier 2. |
| HA backup share (Samba/CIFS) | Pasted back at `provision-ha-backup-share.yml` prompt. |
| Vaultwarden admin panel | Plaintext token; the Argon2id hash is what the container holds. |
| UniFi controller (UDM) | Read-only monitoring credential is Tier 3, not here. |
| SLZB-06 Zigbee coordinator | IoT VLAN web UI. |
| Google account | **Root identity** — SSO for Tailscale; Keychain anchor. |
| Tailscale | Google SSO;No separate password; pointer entry. |
| Cloudflare | Zero Trust tunnel for HA. |
| GitHub | Public IaC repo. |
| ProtonVPN Plus | Phase 6 (Gluetun/qBittorrent); WireGuard config attached. |
| ntfy alert topic | Secure note — capability-URL secret (read/post alerts). |

## Tier 2 — Keychain, **outside the lab** (bootstrapping anchors — never in Vaultwarden)

| Anchor | Why outside the lab |
|--------|---------------------|
| PBS encryption key | Needed to restore backups when the lab is down. |
| HA backup encryption key | Same — decrypt HAOS backups independently. |
| 2FA / TOTP recovery codes (per account) | A lost/desynced phone must not lock root out of Proxmox (Phase 4 401 saga). |
| Vaultwarden master password | The vault can't protect its own unlock secret. |

## Tier 3 — gitignored env files on mgmt-vm (machine tokens — not in Vaultwarden)

| Token | Consumer |
|-------|----------|
| UniFi read-only monitoring password | unpoller / Prometheus |
| PVE API scrape token | Prometheus pve exporter (cluster-wide; carter reuses apophis's) |
| HA long-lived access token | Prometheus HA exporter |

## Tier 5 — Authenticator app (second factors — not in Vaultwarden)

TOTP seeds stay in Google Authenticator + iCloud Keychain. **Deliberately not co-located** with the
Tier-1 passwords so a vault compromise doesn't also yield the second factor.

## Maintenance

- New service with a human login → add a Tier-1 row **and** a vault item (ADR-017 onboarding).
- New machine token → Tier 3 env file, add a row here (no value).
- Never record a value, address, or account identifier in this file — it is a map, not a store.
