# Index

Machine-readable navigation for AI agents. Load only what is relevant to your task — do not load everything at once.

Before using this index, read [AGENTS.md](AGENTS.md) for behaviour rules and [CLAUDE.md](CLAUDE.md) for Claude-specific guidance.

---

## Repo map

```
homelab/
  PLAN.md              # Authoritative service plan, RAM budget, phase order
  decisions/           # Architecture Decision Records (ADR-NNN-title.md)
  terraform/           # Terraform — creates VMs/LXCs (bpg/proxmox, ADR-008)
  ansible/             # Ansible — configures what Terraform creates (ADR-005)
  scripts/             # Bash fallbacks/utilities (e.g. backup-local-config.sh)
decisions/             # Top-level one-off decisions (mgmt-vm sizing etc.)
docs/
  components/          # Per-service operational reference — one .md per deployed service
  operations/
    runbooks.md        # Common procedures: restarts, health checks, recovery
  phases/              # Phase completion records — written when a phase is marked done
  tech-radar.md        # Capabilities evaluated, adopted, deferred, or monitoring
.claude/
  agents/
    infra-designer.md  # On-demand: review infra proposals before execution
    infra-manager.md   # Weekly scheduled + on-demand: status report
    doc-auditor.md     # On-demand + phase-gate: documentation drift/conflict check
    continuity-reviewer.md  # On-demand + phase-gate: backup/restore continuity check
README.md              # Human-facing overview (GitHub landing page)
AGENTS.md              # AI agent behaviour rules (all tools)
CLAUDE.md              # Claude Code specific guidance and agent table
index.md               # THIS FILE
```

---

## By task

### "What should I work on next?"
→ `homelab/PLAN.md` — check current phase and what's next

### "I want to propose a new service or infrastructure change"
→ Use the `infra-designer` agent first. Then write an ADR in `homelab/decisions/`.

### "What architecture decisions have been made?"
→ `homelab/decisions/` for infra ADRs  
→ `decisions/` for top-level decisions (VM sizing etc.)

### "How do I provision a service?"
→ `homelab/terraform/` — Terraform creates the VM/LXC (ADR-008)  
→ `homelab/ansible/` — Ansible configures it (ADR-005)

### "What are the conventions for this repo?"
→ `AGENTS.md` (all-agent rules) + `CLAUDE.md` (Claude-specific)

### "Which agent should I use for this task?"
→ `CLAUDE.md` Agents section

### "Are the docs consistent / is anything contradictory or stale?"
→ Use the `doc-auditor` agent

### "How do I do X operationally (restart, recover, check health)?"
→ `docs/operations/runbooks.md`

### "What services are running or planned?"
→ `homelab/PLAN.md` current infrastructure + planned VMs/LXCs tables

### "What does this specific service do and how is it configured?"
→ `docs/components/<service>.md` — written when that service is deployed

### "What capabilities have been evaluated and deferred?"
→ `docs/tech-radar.md`

### "What changed recently?"
→ `git log --oneline --since='30 days ago'`

### "What phase are we in and what's the history?"
→ `homelab/PLAN.md` phase order  
→ `docs/phases/` for completion records once written

---

## Document responsibilities

| File | Audience | Covers | Do not use for |
|------|----------|--------|----------------|
| `README.md` | Humans | Quick overview, key links | Detail — link to PLAN.md instead |
| `AGENTS.md` | All AI agents | Behaviour rules, commit style, stack | Navigation — use index.md |
| `CLAUDE.md` | Claude Code | Claude-specific rules, agent table | Replacing AGENTS.md |
| `index.md` | All AI agents | Where to find things | Behaviour rules — use AGENTS.md |
| `homelab/PLAN.md` | Humans + AI | Services, phases, RAM, decisions | Per-service detail — use docs/components/ |
| `docs/tech-radar.md` | Humans + AI | Capability tracking, re-evaluation triggers | Day-to-day work |

**Single source of truth (two-tier):** Logical facts — hosts/VMs/LXCs, VMIDs, RAM budget, phase/service status, canonical hostnames — live in `homelab/PLAN.md`; every other doc links to it. **Real network addresses (IPs, subnets, MACs) are never committed** — they live only in the gitignored Ansible config and the operator's private notes; committed files use `YOUR_*` placeholders (ADR-006). The `doc-auditor` agent enforces both rules.

---

## Scaling notes

This index grows as the homelab grows. When a new service is deployed:
1. Add a row to the planned → running table in `homelab/PLAN.md`
2. Create `docs/components/<service>.md`
3. Update this index under "By task" if a new lookup pattern is needed
4. Write a `docs/phases/<N>-<name>.md` completion record when the phase is done

Future hosts (second server, NAS) will get their own sections in `homelab/PLAN.md` and entries here.
