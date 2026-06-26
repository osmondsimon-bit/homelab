# Vaultwarden (VM 118)

Self-hosted, Bitwarden-compatible password manager — the Tier-1 credential store (ADR-010,
ADR-018). Zero-knowledge: the server holds only ciphertext. **Tailnet-only — never exposed on the
LAN or the internet.**

| | |
|---|---|
| Host / VMID | **apophis** / VM 118 (Ubuntu 24.04 cloud-image VM, **not** an LXC) |
| IP | `YOUR_VAULTWARDEN_IP` (static; reserve in UniFi) |
| Shape | 2 GB / 1 core / 10 GB; CPU `Skylake-Client-noTSX-IBRS` (migratable across the Coffee-Lake pair) |
| Runtime | Official `vaultwarden/server` **Docker container** (pinned tag), Docker **confined to this VM** — ADR-014 exception |
| Bind | container published to `127.0.0.1:8080` only |
| TLS / access | **Tailscale Serve** terminates TLS → `https://vaultwarden.<tailnet>.ts.net`; tailnet ACL restricts it to `group:operators` (node tagged `tag:vaultwarden`, default-deny) |
| Hardening | container `cap_drop: ALL` + `no-new-privileges`; **signups OFF**; **Argon2id `ADMIN_TOKEN`** (hash only on the VM) |
| Redundancy | `pvesr` job `118-0` → carter (15 min); manual failover (no HA manager) |
| Backup | PBS daily job on apophis (with vm/100); data volume `/opt/vaultwarden/data`. **Restore drill: pending.** |

## Why a VM running Docker (not a native LXC)

Vaultwarden ships only as a container. The native-from-source build OOM-killed a small LXC
(multi-GB transient Rust build), and a Debian cloud-image VM kernel-panicked on the emulated CPU
models — so the as-built is an **Ubuntu 24.04 VM running the official container**, with Docker
deliberately contained to this one guest (oneill's service LXCs stay Docker-free). See ADR-014.

## How it's managed

Provisioned **and** configured by `homelab/ansible/playbooks/provision-vaultwarden.yml` (idempotent;
two plays — create the VM on apophis, then configure Docker + Tailscale + the container over SSH):

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-vaultwarden.yml --limit apophis
```

Prompts for a Tailscale auth key + the admin-panel token (neither is stored). First-run account
bootstrap uses `-e vaultwarden_signups_allowed=true` once to register, then a re-run locks signups.
The hand-built recipe is retained in [operations/runbooks.md](../operations/runbooks.md) for reference.

> **Tailnet prerequisites (one-time, admin console):** HTTPS + Serve enabled on the tailnet; then
> approve the node, disable key expiry, and keep it ACL'd to operator devices
> (`ansible/files/tailscale-acl.hujson`).

## Health / operations

- **Health:** `curl https://vaultwarden.<tailnet>.ts.net/alive` (from a tailnet device).
- **Glance:** a **link-tile** under *Admin Links → Tailnet-only* (not a monitor tile — the 100.x
  tailnet address isn't reachable from the LAN where Glance runs).
- **Logs / restart:** `cd /opt/vaultwarden && sudo docker compose logs` / `… restart`.
- **Lock signups after registering:** `SIGNUPS_ALLOWED=false`, then `docker compose up -d --force-recreate`.

## Related

ADR-010 (password manager) · ADR-014 (Docker confinement exception) · ADR-018 (tiered secrets) ·
[secrets-register.md](../operations/secrets-register.md) · [tailscale-acl.hujson](../../ansible/files/tailscale-acl.hujson).
