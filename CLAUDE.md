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

**Everything homelab lives under `homelab/`** — it is the project root. Only repo
meta (`README.md`, `CLAUDE.md`, `AGENTS.md`, `index.md`, `.gitignore`) sits at the
git root. There is exactly one `decisions/` and one `docs/`; no per-domain top-level
dirs (hardware/network/backup notes are files under `homelab/docs/`).

```
homelab/                  ← the project (paths in prose are relative to here)
  PLAN.md                 Single source of truth (phases, VMIDs, status)
  decisions/              All Architecture Decision Records (ADR-NNN-title.md)
  docs/                   All narrative docs:
    components/<svc>.md    per-service reference (one per deployed service)
    operations/runbooks.md operational procedures
    phases/<N>-<name>.md   phase completion records
    tech-radar.md          capability tracking
    <topic>.md             hardware, network, etc. as flat files when needed
  ansible/                Ansible — configures (ADR-005); inventory/ lives here
  terraform/              Terraform — creates VMs/LXCs (bpg/proxmox, ADR-008)
  scripts/                Bash fallbacks/utilities (e.g. backup-local-config.sh)
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

**New infrastructure (observability & continuity by default — ADR-017):** every new guest/node/storage gets monitoring, alerting, a recorded backup *decision* (+ backup-freshness registration), and a restore drill **as part of provisioning** — follow the "Onboarding a new guest / node / storage" checklist in `homelab/docs/operations/runbooks.md`. Adding a service to the dashboards is a one-line edit to `glance_services` / `glance_release_repos` in group_vars.

**Network:** No ports forwarded directly from the internet. Remote access via Cloudflare Tunnel (HTTP/S) or Tailscale (full network; WireGuard is superseded — see ADR-003). All services run inside VMs or LXCs — nothing installed directly on the Proxmox host.

**Local config backup:** Real config plus local Claude/Codex agent config live only on the mgmt-vm (ADR-006). Back them up to the private `homelab-private` repo with `bash homelab/scripts/backup-local-config.sh` after changing local config and at session close (ADR-007). Never back up credentials. PBS now covers the mgmt-vm; HA native backup and off-site backup remain tracked in PLAN.md.

**Single source of truth (two-tier):** Logical facts — which hosts/VMs/LXCs exist, VMIDs, RAM budget, phase/service status, canonical hostnames — are owned by `homelab/PLAN.md`; other docs link to it. **Real network addresses (IPs, subnets, MACs) are never published** — they live only in the gitignored Ansible config (`ansible/inventory/`, `group_vars/`) and the operator's private notes. Committed files use `YOUR_*` placeholders only (ADR-006).

**Doc hygiene (keep docs fresh as you work):** When a service's config changes (VLAN, port, RAM, purpose), update its `docs/components/<svc>.md` in the same commit. When a capability moves from planned → live, move it in `docs/tech-radar.md`. Do not leave "still to be confirmed" or "Phase X" triggers in the radar past the phase they were due. The `doc-auditor` enforces this at phase gates — but fixing drift mid-phase is cheaper than a batch cleanup later.

## Agents

Reviewers assist with this homelab (four agents + the `/phase-gate` and `/security-review` skills). Invoke them at the right moment — don't skip the gates.

| Reviewer | When to invoke | How |
|-------|---------------|-----|
| `infra-designer` | Before provisioning any new VM, LXC, or significant network change | "Use the infra-designer agent to review…" |
| `infra-manager` | Weekly automated (Mondays 08:00) + on-demand for a status snapshot | "Use the infra-manager agent" |
| `doc-auditor` | On-demand, and before marking a phase complete — checks docs for drift/contradictions vs PLAN.md | "Use the doc-auditor agent" |
| `continuity-reviewer` | Before marking a phase complete, after changing what's backed up, and periodically to run a restore drill | "Use the continuity-reviewer agent" |
| `/phase-gate` | Before marking any phase complete; runs doc, continuity, and security gates | `/phase-gate` |
| `/security-review` | Before marking any phase complete; before committing significant config changes | `/security-review` |

**Security review gates:** run `/security-review` at the end of each phase before marking it done in PLAN.md. Also run it before committing any Ansible playbook, firewall rule, or service configuration.

## Context, subagents & effort

Two goals: **stretch session runway** (minimize token/compute cost without adding real risk) and **keep the main agent's context clean** (unneeded tool/work output stays out of it).

- **Offload to a subagent when the work is large but the answer needed back is small** — broad searches, multi-file reads, noisy tool runs, research. Ask it for **conclusions, uncertainty, and `file:line` refs — not transcripts or dumps**. **Verify a subagent's claims** (read the cited lines) before relying on them.
- **Tight guidance + constraints; pass minimal context.** Don't feed history/prior context into a subagent unless essential — it biases results and burns tokens.
- **Parallelize disjoint work** (multiple subagents at once when their targets don't overlap). **Sequence** anything that might touch the same files — "parallel-safe" means disjoint write targets.
- **Pick the cheapest model/effort that does the job reliably:** comprehension *difficulty → model tier*; labor *volume → effort*. When Claude Code is doing the work, prefer Claude models. When Codex/OpenAI is doing the work, prefer the Codex/OpenAI model with the matching tier.

| Model Family | Model | Efforts | Wrapping Skill (if present) | Model Ref | Capability Tier | Cost |
|--------------|-------|---------|-----------------------------|-----------|-----------------|------|
| Claude | Haiku 4.5 | n/a | n/a | `claude-haiku-4-5-20251001` | Low | Low |
| Claude | Sonnet 4.6 | low, medium, high, max | n/a | `claude-sonnet-4-6` | Medium | Medium |
| Claude | Opus 4.8 | low, medium, high, xhigh, max | n/a | `claude-opus-4-8` | High | High |
| Claude | Fable 5 | low, medium, high, xhigh, max | n/a | `claude-fable-5` | Epic | Epic |
| Codex | GPT 5.3 | low, medium, high, xhigh | `codex-gpt53-plan`, `codex-gpt53-do` | `gpt-5.3-codex-spark` | Low | ~Zero |
| Codex | GPT 5.5 | low, medium, high, xhigh, max | `codex-gpt55-plan`, `codex-gpt55-do` | `gpt-5.5` | High | High |
| Qwen | Qwen 3.6 27B Coder | n/a | `qwen-qwen36-plan`, `qwen-qwen36-do` | `llama.cpp/Qwen-Qwen3.6-27B-IQ4_XS.gguf` | Medium | Zero |

  - Low tier/cost: simple, mechanical, well-specified tasks.
  - Medium tier: most coding, research, and doc work.
  - High tier: hard reasoning, architecture/security reviews, and risky cross-cutting changes. The reviewer agents above are this class.
  - Epic tier: reserve for work that is both high-risk and unusually ambiguous or complex.
  - Set the Agent tool's `model` or wrapping skill to the right tier. Where a model/skill exposes **effort**, scale it to labor volume (more steps/output → higher effort), not to difficulty.

## Roadmap

See `homelab/PLAN.md` for the phased build-out plan (authoritative for current phase/status). Current position: **Phase 3 CLOSED 2026-06-17** (Foundation + observability: PBS, Monitoring, Glance, all backup carry-forwards clear). **Phase 4 next** (new node ~2026-06-26). Terraform import deferred to cluster scale (ADR-008). Order: 1 VLANs ✓ → 2 Tailscale + Technitium ✓ → 3 Foundation + observability ✓ → 4 Multi-node cluster + HA (oneill joins cluster, 2nd ThinkCentre, ZFS replication) → 5 Jellyfin + media → 6 Vaultwarden + HA expansion. Cross-cutting: backups + patching.
