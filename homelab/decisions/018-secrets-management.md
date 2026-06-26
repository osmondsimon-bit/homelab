# ADR-018: Tiered secrets management model

**Date:** 2026-06-19  
**Status:** Accepted

## Context

Until now there has been no deliberate secrets model — credentials have accumulated
ad-hoc across ansible-vault prompts, gitignored env files, and mental notes. With
Vaultwarden being planned (ADR-010) and the credential surface growing (Proxmox,
PBS, Grafana, HA, UniFi, API tokens), a clear, documented policy is needed so every
new service knows where its secret lives and why.

Two requirements shape the design:

1. **Bootstrapping anchor:** the tools needed to recover the lab must not themselves
   live inside the lab. If everything is down, recovery creds must still be reachable.
2. **Human vs machine:** human-operated admin passwords (logins you type) belong in a
   password manager. Machine-to-machine tokens (API keys, service accounts) are
   different in threat model and rotation cadence; they belong closer to where they're
   used.

## Decision

**Five tiers — one home per credential class:**

| Tier | What lives here | Where |
|------|-----------------|--------|
| 1. Personal + admin passwords | Browser logins, personal accounts, human-operated infra admin logins (Grafana, PBS, HA, UniFi, Proxmox root, Technitium) | **Vaultwarden** (self-hosted, ADR-010). During interim: Bitwarden cloud. |
| 2. Bootstrapping anchors | ~~`ansible-vault` master password~~ (dropped — see 2026-06-25 revision); PBS encryption key; HA backup encryption key; 2FA/TOTP recovery codes | **Google/iCloud Keychain** — kept *outside the lab on purpose*. Never moved to Vaultwarden. |
| 3. Agent-accessible tokens | API tokens for read-only or scoped machine access (UniFi RO, PVE API tokens, Prometheus scrape tokens) | **Scoped gitignored env files on mgmt-vm** (`~/.*.env`, `chmod 600`). One file per service, never committed (ADR-006). |
| 4. Short-lived playbook secrets | Passwords prompted at provisioning time (new service admin passwords, one-time setup) | **`vars_prompt` at runtime** — never stored, never committed. |
| 5. 2FA / TOTP | App-based second factors | **Google Authenticator + iCloud Keychain** (no change). |

**Relationship to ADR-010 (Vaultwarden scope):**

ADR-010 stated "infra/machine secrets stay in ansible-vault, not Vaultwarden."
This ADR refines that: *human-operated* infra admin passwords go in Vaultwarden
(Tier 1); machine-to-machine tokens and the vault password go in Tier 2/3. The
distinction is: if a human types it into a UI to log in, it's Tier 1. If a script
or daemon reads it from an env file or ansible-vault, it stays in Tier 2/3.

**Vaultwarden placement:**

Host placement is **open** pending the new-node arrival and cluster topology review
(see ADR-010 and Phase 4 cluster work). The deployment will target the HA cluster
once available. The tiered model above is independent of placement and takes effect
immediately as a policy.

## Consequences

- **Bootstrapping is non-circular:** the `ansible-vault` password and PBS/HA
  encryption keys (Tier 2) never live in Vaultwarden. If the lab is fully down,
  recovery credentials are reachable from Keychain without needing the lab. This is
  the DR rule: *the keys needed to restore the lab live outside the lab.*
- **Bitwarden offline cache** means Vaultwarden downtime during maintenance does not
  instantly lock out admin credentials — clients have a local encrypted copy.
- **Credential migration:** when Vaultwarden is stood up, existing service admin
  passwords should be migrated from wherever they currently live into Tier 1. The
  Bitwarden export/import format is identical so Bitwarden cloud → Vaultwarden is a
  one-step migration.
- **Tier 3 is intentionally narrow:** env files on the mgmt-vm are a single point of
  access. The mgmt-vm itself is backed up by PBS (ADR-012), so loss of the VM doesn't
  mean loss of the tokens — but a compromise of the mgmt-vm does expose Tier 3. Keep
  the principle of least privilege on token scopes (read-only where possible).
- **No Bitwarden Secrets Manager / Vault / external secrets operator** — unnecessary
  complexity at this scale. `ansible-vault` + gitignored env files covers machine
  secrets adequately.
- **SSH keys** are not passwords but are part of the access surface. A separate SSH
  audit (enumerate authorized_keys across all guests + both PVE hosts; confirm
  key-only root login on hosts; inventory where the mgmt-vm private key is backed up)
  is a follow-on action — tracked in PLAN.md.

## Revision — 2026-06-25 (Phase 5 planning; reconciled to as-built + a state survey)

A survey of what's actually deployed found the model partly aspirational. Three changes:

1. **`ansible-vault` dropped — it was never wired in.** No vault password file, no encrypted
   vars, no playbook uses it. Tier 2 no longer lists an "ansible-vault master password."
   Persistent *admin* passwords that playbooks prompt for (Grafana, PBS, Technitium ×2,
   HA-backup-share) — which today live **nowhere durable** (a forgotten one blocks a
   re-converge) — become **Tier 1**: they live in Vaultwarden and the operator pastes them
   at the `vars_prompt`. Machine tokens stay Tier 3 (gitignored env files / `group_vars`).
   Runs stay manual/interactive; nothing secret is stored encrypted-in-repo. Rationale: the
   lab is small and hand-driven; vault was a moving part with no user. (Revisit only if
   non-interactive/CI runs are ever needed.)

2. **Vaultwarden availability is MANUAL failover, not auto-HA.** ADR-009 shipped manual
   failover (no HA manager/fencing), so the original "fails over to another node" assumption
   in ADR-010/018 is wrong. Vaultwarden is a `pvesr`-replicated guest (apophis→carter); a
   node loss means a *manual* start on the survivor. The **offline client cache** is what
   covers that window — acceptable for a vault.

3. **2FA recovery codes are now an explicit Tier 2 anchor** (Keychain, outside the lab). The
   Phase 4 cluster-join 401 saga showed a lost/desynced phone can lock root out of Proxmox;
   each account's TOTP recovery codes must be saved to Keychain so 2FA is itself recoverable.

**Exposure:** Vaultwarden is **Tailscale-only** (no public surface). The phone syncs over the
tailnet; the app's offline cache still lets you *read* passwords when off-tailnet. Decided
2026-06-25.

Updated Tier 2 anchors (outside the lab, in Keychain): **PBS encryption key · HA backup
encryption key · 2FA/TOTP recovery codes**. (No ansible-vault password — removed.)
*2FA recovery keys saved to Keychain 2026-06-26* — Proxmox Recovery Keys for `root@pam` (cluster),
`simon@pve`, and oneill's standalone `root@pam`.

The live, value-free inventory of every credential and its tier is maintained at
[`docs/operations/secrets-register.md`](../docs/operations/secrets-register.md) (first populated
2026-06-26 when Vaultwarden was loaded).
