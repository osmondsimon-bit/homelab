# ADR-010: Self-hosted Vaultwarden for passwords, sequenced after HA + backups

**Date:** 2026-06-14  
**Status:** Accepted

## Context

The plan listed Vaultwarden (self-hosted, Bitwarden-compatible) as a Phase-4 service. Bitwarden
Family (managed cloud) was considered as an alternative — zero ops, but a SaaS dependency and cost.
The hesitation about self-hosting was resilience: "if my hardware fails or someone walks off with
it, do I lose my passwords, and do I have to keep manual offsite copies?"

Two facts resolve that concern:
1. **Vaultwarden is zero-knowledge** — it stores only client-side-encrypted ciphertext. Physical
   theft of a node never exposes passwords (they're locked by the master password), and an
   encrypted backup is safe to store *anywhere*, including untrusted cloud — no manual physical
   offsite copies needed.
2. The **real** cost of self-hosting a password manager is *availability* (if the lab is down, the
   vault is down). But the HA cluster being built (ADR-009) solves exactly that — Vaultwarden fails
   over to another node. And Bitwarden clients cache the vault offline, so server downtime isn't an
   instant lockout.

## Decision

**Self-host Vaultwarden**, but **sequenced after** the HA cluster (ADR-009) and the backup story
are in place — by then its two weak points (availability, durability) are already solved by
infrastructure being built anyway.

- **Bridge now with Bitwarden's cloud** (free/Family) so there's a working password manager in the
  interim. Migration Bitwarden → Vaultwarden is a trivial export/import (same vault format), so
  nothing is lost by starting on their cloud.
- **Backup:** include Vaultwarden's (already-encrypted) data in the offsite backup — safe to store
  in a cloud bucket and/or the private repo because it's ciphertext. Tiny dataset; back up often.
- **Scope:** Vaultwarden is for *human* passwords only. Infra/machine secrets (the `ansible-vault`
  password, API tokens) stay in `ansible-vault` — not in Vaultwarden. (Bitwarden Secrets Manager,
  a separate product, was considered for machine secrets and declined as unnecessary.)
  *(Superseded by ADR-018 revision 2026-06-25 — `ansible-vault` was never wired in and is dropped;
  machine tokens now live in gitignored env files on the mgmt-vm, Tier 3.)*

## Consequences

- Self-hosted control without the theft/lockout risks — the cluster + backup plans neutralise both.
- A managed-cloud password manager (Bitwarden) is in use during the interim; one migration later.
- Vaultwarden placement is HA (runs on the cluster, flagged for failover) — depends on ADR-009
  being delivered first, which is why it sits in **Phase 5** (swapped ahead of Media 2026-06-25).
- Master-password strength + KDF settings matter — they are the actual protection on a stolen
  encrypted blob. Use a strong master password and modern KDF (Argon2id).
- One more dataset in the backup set; trivial in size.

## Revision — 2026-06-25 (Phase 5; reconciled to the as-built cluster)

- **Failover is MANUAL, not automatic.** ADR-009 shipped manual failover (no HA manager).
  Vaultwarden runs on **apophis**, `pvesr`-replicated to **carter** (same set as VM 200); on
  an apophis loss it's started manually on carter (Manual-failover runbook). The **offline
  client cache** covers the failover window — the availability concern is met without auto-HA.
- **Deployment:** native `vaultwarden` Rust binary in an **unprivileged LXC** (no Docker —
  keeps Phase 5 Docker-free; Docker still doesn't arrive until the media phase, ADR-014).
  Strong master password + **Argon2id** KDF. Sign-ups disabled after the operator account.
- **Exposure:** **Tailscale-only** — no Cloudflare Tunnel/public hostname (decided 2026-06-25).
- **Backup:** encrypted Vaultwarden export to PBS **and** an off-site copy — this is the
  **first off-site backup item** (ciphertext, safe in any cloud bucket), starting to close the
  standing off-site-backup SPOF.
- **Tier alignment (ADR-018):** Vaultwarden holds **Tier 1** human/admin passwords only —
  including the previously-homeless playbook admin passwords (operator pastes them at the
  prompt). The bootstrapping anchors (PBS/HA keys, 2FA recovery codes) stay in Keychain,
  **never** in Vaultwarden, so recovery is non-circular.

## As-built — 2026-06-26 (delivery changed: Docker-in-VM, not native LXC)

The "native binary in an LXC" delivery (revision above) **was abandoned** — building Vaultwarden
from source needs multi-GB transient RAM (OOM-killed in a small CT), and there is no official
native binary. **As-built: the official `vaultwarden/server:1.36.0` Docker container in a dedicated
VM (118)** — ADR-014 Docker exception, confined to that VM. Ubuntu 24.04 cloud image (a Debian cloud
image kernel-panicked on emulated CPU models — `x86-64-v2-AES` etc.), CPU `Skylake-Client-noTSX-IBRS`
(migratable). Container bound to `127.0.0.1:8080`; **Tailscale Serve** terminates TLS to
`https://vaultwarden.<tailnet>.ts.net` — tailnet-only, never on the LAN. Hardened (cap-drop ALL,
no-new-privileges, signups off, Argon2id `ADMIN_TOKEN`). Replicated apophis→carter (`pvesr` 118-0) +
PBS backup. The security posture (zero-knowledge, Tailscale-only, hardened, replicated+backed-up) is
unchanged from the plan; only the packaging differs. Build recipe: `docs/operations/runbooks.md`.
