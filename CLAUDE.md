# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Documentation, scripts, and configuration for Simon's homelab. The primary host is **apophis** (Proxmox VE, `YOUR_PROXMOX_IP`). All work is done from the **admin VM** (`YOUR_MGMT_VM_IP`).

## Key infrastructure

| Host | Role | IP |
|------|------|----|
| apophis | Proxmox VE hypervisor | YOUR_PROXMOX_IP |
| admin VM | This machine — git, scripts, Claude Code, future Ansible | YOUR_MGMT_VM_IP |
| home-assistant | HAOS VM (VMID 200), Zigbee2MQTT, SLZB-06 at YOUR_ZIGBEE_COORD_IP | YOUR_HA_IP |

## Repo layout

```
homelab/
  decisions/     Architecture Decision Records (ADR-NNN-title.md)
  scripts/       Bash scripts for provisioning and maintenance
  ansible/       Inventory and playbooks (not yet in active use)
  docs/          Service-specific notes
  network/       Network layout diagrams/notes
  inventory/     Hardware inventory
  backups/       Backup config/notes
decisions/       Top-level one-off decisions (e.g. admin VM sizing)
```

## Running scripts

Scripts are written for bash and assume they run from the admin VM. Always check prerequisites in the script header.

```bash
bash homelab/scripts/<target>-<action>.sh
```

## Running Ansible

Ansible is not yet active (needs `sudo apt install ansible` on the admin VM first).

```bash
ansible-playbook -i homelab/ansible/inventory/hosts.ini homelab/ansible/playbooks/<name>.yml
```

Test against a Proxmox snapshot before running against any production host. Keep secrets out of the repo — use ansible-vault or environment variables.

## Conventions

**Scripts:** Name as `<target>-<action>.sh`. Start with `set -euo pipefail`. Add a one-line header describing purpose, assumptions, and required variables. Print what the script is about to do before doing it. Prompt for confirmation before destructive/irreversible steps. Update `homelab/scripts/README.md` table.

**ADRs:** Use `homelab/decisions/template.md`. Filename: `NNN-short-title.md`. Status is `Draft → Accepted → Superseded`. Capture context, decision, and consequences — not implementation detail.

**Network:** No ports forwarded directly from the internet. Remote access via Cloudflare Tunnel (HTTP/S) or WireGuard/Tailscale (full network). All services run inside VMs or LXCs — nothing installed directly on the Proxmox host.

## Agents

Three agents assist with this homelab. Invoke them at the right moment — don't skip the gates.

| Agent | When to invoke | How |
|-------|---------------|-----|
| `infra-designer` | Before provisioning any new VM, LXC, or significant network change | "Use the infra-designer agent to review…" |
| `infra-manager` | Weekly automated (Mondays 08:00) + on-demand for a status snapshot | "Use the infra-manager agent" |
| `/security-review` | Before marking any phase complete; before committing significant config changes | `/security-review` |

**Security review gates:** run `/security-review` at the end of each phase before marking it done in PLAN.md. Also run it before committing any Ansible playbook, firewall rule, or service configuration.

## Roadmap

See `homelab/PLAN.md` for the phased build-out plan. Current phase: VLAN-aware Proxmox + UniFi firewall rules → Technitium DNS + Tailscale → Plex + Monitoring → Vaultwarden + HA expansion.
