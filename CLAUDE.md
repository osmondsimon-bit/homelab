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
  terraform/     Terraform — creates VMs/LXCs (bpg/proxmox, ADR-008)
  ansible/       Ansible — configures what Terraform creates (ADR-005)
  scripts/       Bash scripts (fallbacks/utilities, e.g. backup-local-config.sh)
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

## Provisioning: Terraform creates, Ansible configures

**Terraform** (`bpg/proxmox`, ADR-008) owns VM/LXC *existence and shape* — see `homelab/terraform/` (scaffold; import existing VMs is the next step). **Ansible** (ADR-005) owns *configuration*. Boundary: Terraform = the box exists with the right shape; Ansible = the box is set up.

Run playbooks from the mgmt-vm:

```bash
cd homelab/ansible && ansible-playbook playbooks/<name>.yml
```

First time? See `homelab/ansible/README.md` for the one-time bootstrap (install Ansible, authorise the mgmt-vm on apophis). Test against a Proxmox snapshot before any production host. Secrets are prompted at runtime or stored with ansible-vault — never committed.

## Conventions

**Scripts:** Name as `<target>-<action>.sh`. Start with `set -euo pipefail`. Add a one-line header describing purpose, assumptions, and required variables. Print what the script is about to do before doing it. Prompt for confirmation before destructive/irreversible steps. Update `homelab/scripts/README.md` table.

**ADRs:** Use `homelab/decisions/template.md`. Filename: `NNN-short-title.md`. Status is `Draft → Accepted → Superseded`. Capture context, decision, and consequences — not implementation detail.

**Network:** No ports forwarded directly from the internet. Remote access via Cloudflare Tunnel (HTTP/S) or Tailscale (full network; WireGuard is superseded — see ADR-003). All services run inside VMs or LXCs — nothing installed directly on the Proxmox host.

**Local config backup:** Real config and `.claude/` agents/memory live only on the mgmt-vm (ADR-006). Back them up to the private `homelab-private` repo with `bash homelab/scripts/backup-local-config.sh` after changing local config and at session close (ADR-007). Never back up credentials. VM-level Proxmox backups are still pending (see PLAN.md).

**Single source of truth (two-tier):** Logical facts — which hosts/VMs/LXCs exist, VMIDs, RAM budget, phase/service status, canonical hostnames — are owned by `homelab/PLAN.md`; other docs link to it. **Real network addresses (IPs, subnets, MACs) are never published** — they live only in the gitignored Ansible config (`ansible/inventory/`, `group_vars/`) and the operator's private notes. Committed files use `YOUR_*` placeholders only (ADR-006).

## Agents

Reviewers assist with this homelab (four agents + the `/security-review` skill). Invoke them at the right moment — don't skip the gates.

| Reviewer | When to invoke | How |
|-------|---------------|-----|
| `infra-designer` | Before provisioning any new VM, LXC, or significant network change | "Use the infra-designer agent to review…" |
| `infra-manager` | Weekly automated (Mondays 08:00) + on-demand for a status snapshot | "Use the infra-manager agent" |
| `doc-auditor` | On-demand, and before marking a phase complete — checks docs for drift/contradictions vs PLAN.md | "Use the doc-auditor agent" |
| `continuity-reviewer` | Before marking a phase complete, after changing what's backed up, and periodically to run a restore drill | "Use the continuity-reviewer agent" |
| `/security-review` | Before marking any phase complete; before committing significant config changes | `/security-review` |

**Security review gates:** run `/security-review` at the end of each phase before marking it done in PLAN.md. Also run it before committing any Ansible playbook, firewall rule, or service configuration.

## Roadmap

See `homelab/PLAN.md` for the phased build-out plan (authoritative for current phase/status). Current position: **Phase 2 ✓ complete** (Tailscale CT 110 + Technitium CT 111 live on oneill/NUC) — **starting Phase 3**, whose entry task is VM-level backups, then Terraform import → Monitoring → Homepage. Order: 1 VLANs ✓ → 2 Tailscale + Technitium ✓ → 3 backups + Terraform + Monitoring + Homepage → 4 Multi-node cluster + HA (NUC + ThinkCentre, ZFS replication) → 5 Plex + media → 6 Vaultwarden + HA expansion. Cross-cutting: backups + patching.
