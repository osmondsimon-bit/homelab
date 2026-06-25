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

## Consequences

- Self-hosted control without the theft/lockout risks — the cluster + backup plans neutralise both.
- A managed-cloud password manager (Bitwarden) is in use during the interim; one migration later.
- Vaultwarden placement is HA (runs on the cluster, flagged for failover) — depends on ADR-009
  being delivered first, which is why it sits in **Phase 5** (swapped ahead of Media 2026-06-25).
- Master-password strength + KDF settings matter — they are the actual protection on a stolen
  encrypted blob. Use a strong master password and modern KDF (Argon2id).
- One more dataset in the backup set; trivial in size.
