# CLAUDE.md

This is the Claude-specific entry point. Read [AGENTS.md](AGENTS.md) first; it defines the binding
repository rules and instruction hierarchy. Use [index.md](index.md) to navigate the repo and load
only the context relevant to the task. For central skills or delegated work, read
[the shared workflow](homelab/docs/agents/shared-workflow.md).

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

**Terraform** (`bpg/proxmox`, ADR-008) owns VM/LXC *existence and shape*. **Ansible** (ADR-005)
owns *configuration*. Boundary: Terraform creates the box; Ansible configures it.

Run playbooks from the mgmt-vm:

```bash
cd homelab/ansible && ansible-playbook playbooks/<name>.yml
```

For bootstrap and production safeguards, read `homelab/ansible/README.md` and ADR-018.

## Conventions

**Scripts:** Name as `<target>-<action>.sh`. Start with `set -euo pipefail`. Add a one-line header describing purpose, assumptions, and required variables. Print what the script is about to do before doing it. Prompt for confirmation before destructive/irreversible steps. Update `homelab/scripts/README.md` table.

**ADRs:** Use `homelab/decisions/template.md`. Filename: `NNN-short-title.md`. Status is `Draft → Accepted → Superseded`. Capture context, decision, and consequences — not implementation detail.

**New infrastructure (observability & continuity by default — ADR-017):** every new guest/node/storage gets monitoring, alerting, a recorded backup *decision* (+ backup-freshness registration), and a restore drill **as part of provisioning** — follow the "Onboarding a new guest / node / storage" checklist in `homelab/docs/operations/runbooks.md`. Adding a service to the dashboards is a one-line edit to `glance_services` / `glance_release_repos` in group_vars.

**Doc hygiene (keep docs fresh as you work):** When a service's config changes (VLAN, port, RAM, purpose), update its `docs/components/<svc>.md` in the same commit. When a capability moves from planned → live, move it in `docs/tech-radar.md`. Do not leave "still to be confirmed" or "Phase X" triggers in the radar past the phase they were due. The `doc-auditor` enforces this at phase gates — but fixing drift mid-phase is cheaper than a batch cleanup later.

## Agents

These specialists are risk gates, not the default workflow for ordinary tasks.

| Reviewer | When to invoke | How |
|-------|---------------|-----|
| `infra-designer` | Before provisioning any new VM, LXC, or significant network change | "Use the infra-designer agent to review…" |
| `infra-manager` | Weekly automated (Mondays 08:00) + on-demand for a status snapshot | "Use the infra-manager agent" |
| `doc-auditor` | On-demand, and before marking a phase complete — checks docs for drift/contradictions vs PLAN.md | "Use the doc-auditor agent" |
| `continuity-reviewer` | Before marking a phase complete, after changing what's backed up, and periodically to run a restore drill | "Use the continuity-reviewer agent" |
| `/phase-gate` | Before marking any phase complete; runs doc, continuity, and security gates | `/phase-gate` |
| `/security-review` | Before marking any phase complete; before committing significant config changes | `/security-review` |

**Security review gates:** run `/security-review` at the end of each phase before marking it done in PLAN.md. Also run it before committing any Ansible playbook, firewall rule, or service configuration.

## Agent and model use

Use one agent by default. Delegate only at the risk and workload thresholds in the shared workflow;
one independent reviewer may cover multiple applicable review lanes. Return conclusions and file
references rather than transcripts, and verify delegated claims before relying on them. The central
[agent and model routing policy](/home/simon/agent-workflows/policies/model-routing.md) is the single
source for model defaults.
