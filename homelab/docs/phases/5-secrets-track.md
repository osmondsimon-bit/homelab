# Phase 5 — Secrets track ✓ CLOSED 2026-06-26

Closed via `/phase-gate` (doc-auditor + continuity-reviewer + security-review). Records what
shipped, key decisions, verification, and carry-forwards. Authoritative status: `PLAN.md`.

> **Scope note — Phase 5 was split at this gate.** Phase 5 was framed "Secrets + HA expansion."
> The **Secrets track** (this record) is closed. The **HA-expansion sub-track** (HACS done;
> Node-RED, ESPHome, HA → Grafana, wall-tablet kiosk) is **deferred to a standalone project** and
> is **not** part of this close — see `PLAN.md` Phase order step 7.

## What shipped

- **Vaultwarden self-hosted password manager — VM 118 on apophis.** Ubuntu 24.04 cloud-image VM
  running the official **`vaultwarden/server` Docker container** (Docker **confined to this one VM**
  — ADR-014 exception; oneill's service LXCs stay Docker-free). Container cap-drop ALL +
  no-new-privileges, bound to `127.0.0.1:8080`; **Tailscale Serve** terminates TLS →
  `https://vaultwarden.<tailnet>.ts.net` — **tailnet-only, never on the LAN**. Signups OFF,
  **Argon2id `ADMIN_TOKEN`**. Codified in `provision-vaultwarden.yml` (idempotent, two-play).
- **Tailnet ACL lockdown** — node tagged `tag:vaultwarden`, default-deny so only `group:operators`
  reach it on `:443`. Versioned reference `ansible/files/tailscale-acl.hujson`.
- **Tiered secrets model live (ADR-018, revised).** `ansible-vault` dropped (never wired in);
  human-typed admin passwords → Vaultwarden (Tier 1); machine tokens → gitignored env files (Tier 3);
  bootstrapping anchors (PBS/HA keys, **2FA recovery codes**) → Keychain (Tier 2), outside the lab.
- **Access audit + first vault population** — 18 Tier-1 items imported (Proxmox ×3, PBS, Grafana,
  Technitium ×2, HA, ha-backup-share, Vaultwarden token, UniFi, SLZB-06, + external accounts).
  Value-free inventory recorded in `docs/operations/secrets-register.md`.
- **SSH access audit + host hardening** — `harden-ssh.yml` set **key-only root** on apophis/carter/
  oneill; removed a stale cluster `authorized_keys` entry.
- **Client KDF → Argon2id** on the vault; the loose `/root/vw-admin-token.txt` deleted (hash-only on VM).
- **Monitoring/Glance onboarding** — Vaultwarden link-tile (tailnet-only bookmark, not a monitor
  tile); `dani-garcia/vaultwarden` tracked in Latest Releases.

## Key decisions / ADRs

- **ADR-010 / ADR-014 (revised 2026-06-26):** Vaultwarden ships only as a container, and the native
  build OOMs a small LXC + a Debian cloud-image VM kernel-panics on emulated CPUs → as-built is an
  **Ubuntu VM running the official container**, Docker contained to that guest.
- **ADR-018 (revised 2026-06-25):** 5-tier model; `ansible-vault` dropped; 2FA recovery codes added
  as an explicit Tier 2 anchor; Vaultwarden is Tailscale-only with the client offline cache covering
  the manual-failover window.
- CPU `Skylake-Client-noTSX-IBRS` for VM 118 (migratable across the Coffee-Lake pair).

## Verification done

- **`/security-review`** of the codified playbook + the branch — no findings.
- **VM 118 PBS restore drill — ✅ PASS 2026-06-26:** `qmrestore` of the daily image → throwaway
  VM 119 (NIC stripped), guest agent up, vault `db.sqlite3` (272 KB) + `rsa_key.pem` intact, 119
  destroyed, live 118 untouched. Recovery is proven, not assumed.
- **Replication** job `118-0` apophis→carter healthy (15 min); **PBS** daily job images vm/118.
- **2FA recovery codes** generated (Proxmox Recovery Keys for `root@pam` cluster, `simon@pve`,
  oneill `root@pam`) + saved to Keychain.
- **Carter-rebuild runbook** written (the failover target now has a documented DR path).
- Monitoring clean — 0 firing alerts (the stale `ct/110` smoke-test snapshot was pruned).
- Doc-auditor: drift reconciled (Vaultwarden LXC→VM pivot swept across PLAN/ADRs/runbooks/radar).

## Carried forward

- **HA-expansion sub-track** → standalone project (HACS done; Node-RED/ESPHome/HA→Grafana/wall-tablet).
- **Off-site backup unresolved** — oneill is still the sole home for PBS images + the HA share.
  First concrete step is an encrypted Vaultwarden export off-site (operator deferred for now).
- **CT 111/117 reprovision drills** — reproducibility untested (non-gating; CT 117 covers DNS).
- **Node-down alert drill** — `GuestDown`/`TargetDown` behaviour under a node outage unverified
  (PLAN; recommended before Phase 6).
- **Manual-failover failback commands** still implicit in the runbook (PLAN backlog).
- **Verify** the Technitium admin password is actually populated in Vaultwarden (carter-rebuild
  step 8 depends on it).

## Next

**Phase 6 — Media:** Jellyfin (QuickSync) + qBittorrent/Gluetun on apophis. Low priority.
