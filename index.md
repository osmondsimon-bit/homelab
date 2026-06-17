# Index

Machine-readable navigation + the repo's structure rules. Load only what's relevant to your task — don't load everything.

Before using this index, read [AGENTS.md](AGENTS.md) for behaviour rules and [CLAUDE.md](CLAUDE.md) for Claude-specific guidance.

---

## Structure architecture (the rule we abide by)

**`homelab/` is the project. Everything homelab-related lives under it.** The git root
(`$HOME`) holds only repo **meta**: `README.md`, `CLAUDE.md`, `AGENTS.md`, `index.md`,
`.gitignore`. There is **exactly one** `decisions/` and **one** `docs/`, both under
`homelab/`. No duplicate folders at two levels; no empty placeholder dirs.

```
/home/simon/                 git root ($HOME) — meta only
  README.md  CLAUDE.md  AGENTS.md  index.md  .gitignore
  homelab/                   ← THE project root
    PLAN.md                  single source of truth (phases, VMIDs, status, RAM)
    decisions/               ALL ADRs — NNN-title.md (000-mgmt-vm … 015-patching)
      template.md
    docs/                    ALL narrative docs:
      components/<svc>.md     one per deployed service (what it is, how configured)
      operations/runbooks.md  operational procedures (health, restart, recovery)
      phases/<N>-<name>.md     phase completion records
      tech-radar.md           capability tracking (adopted/deferred/monitoring)
      <topic>.md              flat files for hardware, network, etc. when needed
    ansible/                 configures (ADR-005); inventory/ + playbooks/ live here
    terraform/               creates VMs/LXCs (bpg/proxmox, ADR-008)
    scripts/                 bash fallbacks/utilities (backup-local-config.sh, …)
```

### Where does X go? (decision rules)

| You're adding… | Put it in | Not |
|----------------|-----------|-----|
| An architecture decision | `homelab/decisions/NNN-title.md` | a second decisions/ anywhere |
| Per-service reference (what/how) | `homelab/docs/components/<svc>.md` | PLAN.md |
| An operational procedure | `homelab/docs/operations/runbooks.md` | a service file |
| A phase completion record | `homelab/docs/phases/<N>-<name>.md` | PLAN.md |
| Hardware / network / topology notes | a flat file `homelab/docs/<topic>.md` | a new top-level dir |
| Ansible/Terraform/script code | `homelab/ansible|terraform|scripts/` | docs/ |
| A live fact (IP, VMID, status, hostname) | `homelab/PLAN.md` only (others link) | duplicated prose |

**Don't create a new top-level directory** for a single file or an empty "we might need
it" placeholder — use a flat file under `homelab/docs/`. Create a subdirectory only when a
topic genuinely has multiple files.

**Path-reference convention:** prose/backtick paths are written relative to the `homelab/`
project root (e.g. `docs/operations/runbooks.md`, `decisions/011-dns-engine.md`). Meta
files at the git root use full paths from the root (e.g. `homelab/docs/...`). Clickable
markdown links are relative to the file that contains them.

---

## By task

### "What should I work on next?"
→ `homelab/PLAN.md` — current phase + backlog

### "Propose a new service / infra change"
→ Use the `infra-designer` agent first, then write an ADR in `homelab/decisions/`.

### "What architecture decisions exist?"
→ `homelab/decisions/` (all ADRs, `NNN-title.md`)

### "How do I provision a service?"
→ `homelab/terraform/` creates the VM/LXC (ADR-008); `homelab/ansible/` configures it (ADR-005)

### "Repo conventions?"
→ `AGENTS.md` (all agents) + `CLAUDE.md` (Claude-specific)

### "Which agent for this task?"
→ `CLAUDE.md` Agents section (infra-designer, infra-manager, doc-auditor, continuity-reviewer + `/security-review`)

### "Are docs consistent / anything stale?"
→ Use the `doc-auditor` agent

### "How do I do X operationally (restart, recover, health)?"
→ `homelab/docs/operations/runbooks.md`

### "What does a specific service do / how is it configured?"
→ `homelab/docs/components/<service>.md`

### "What capabilities are evaluated/deferred?"
→ `homelab/docs/tech-radar.md`

### "What phase are we in / phase history?"
→ `homelab/PLAN.md` phase order; `homelab/docs/phases/` for completion records

### "What changed recently?"
→ `git log --oneline --since='30 days ago'`

---

## Document responsibilities

| File | Audience | Covers | Don't use for |
|------|----------|--------|---------------|
| `README.md` | Humans | Quick overview, key links | Detail — link to PLAN.md |
| `AGENTS.md` | All AI agents | Behaviour rules, commit style | Navigation — use index.md |
| `CLAUDE.md` | Claude Code | Claude-specific rules, agent table | Replacing AGENTS.md |
| `index.md` | All AI agents | Where things go + how to find them | Behaviour rules — use AGENTS.md |
| `homelab/PLAN.md` | Humans + AI | Services, phases, RAM, status | Per-service detail — use docs/components/ |
| `homelab/docs/tech-radar.md` | Humans + AI | Capability tracking | Day-to-day work |

**Single source of truth (two-tier):** Logical facts — hosts/VMs/LXCs, VMIDs, RAM, phase/service status, canonical hostnames — live in `homelab/PLAN.md`; every other doc links to it. **Real network addresses (IPs, subnets, MACs) are never committed** — they live only in the gitignored Ansible config (`homelab/ansible/inventory/`) and the operator's private notes; committed files use `YOUR_*` placeholders (ADR-006). The `doc-auditor` agent enforces both rules.

---

## When a new service is deployed
1. Add/update its row in `homelab/PLAN.md` (current infrastructure).
2. Create `homelab/docs/components/<service>.md`.
3. Add a `homelab/docs/operations/runbooks.md` section (health/restart/recovery).
4. Add a "By task" lookup here only if a new pattern is needed.
5. Write `homelab/docs/phases/<N>-<name>.md` when the phase completes.
