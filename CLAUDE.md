# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. General AI agent behaviour rules (all tools) are in [AGENTS.md](AGENTS.md). Use [index.md](index.md) to navigate the repo — load only what's relevant to your task.

## What this repo is

Documentation, scripts, and configuration for Simon's homelab. The primary host is **apophis** (Proxmox VE, `YOUR_PROXMOX_IP`). All work is done from the **mgmt-vm** (`YOUR_MGMT_VM_IP`).

## Key infrastructure

| Host | Role | IP |
|------|------|----|
| apophis | Proxmox VE hypervisor | YOUR_PROXMOX_IP |
| mgmt-vm | This machine — git, scripts, Claude Code, Ansible control node | YOUR_MGMT_VM_IP |
| home-assistant | HAOS VM (VMID 200), Zigbee2MQTT, SLZB-06 at YOUR_ZIGBEE_COORD_IP | YOUR_HA_IP |

## Repo layout

```
homelab/
  decisions/     Architecture Decision Records (ADR-NNN-title.md)
  scripts/       Bash scripts for provisioning and maintenance
  ansible/       Ansible control node — inventory + playbooks (ADR-005)
  docs/          Service-specific notes
  network/       Network layout diagrams/notes
  inventory/     Hardware inventory
  backups/       Backup config/notes
decisions/       Top-level one-off decisions (e.g. mgmt-vm sizing)
```

## Running scripts

Scripts are written for bash and assume they run from the mgmt-vm. Always check prerequisites in the script header.

```bash
bash homelab/scripts/<target>-<action>.sh
```

## Running Ansible

Ansible is the primary provisioning layer (ADR-005). Run playbooks from the mgmt-vm:

```bash
cd homelab/ansible && ansible-playbook playbooks/<name>.yml
```

First time? See `homelab/ansible/README.md` for the one-time bootstrap (install Ansible, authorise the mgmt-vm on apophis). Test against a Proxmox snapshot before any production host. Secrets are prompted at runtime or stored with ansible-vault — never committed.

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
