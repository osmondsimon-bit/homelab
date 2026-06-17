---
name: phase-gate
description: Run the homelab phase-completion gate before marking a phase done — doc-auditor + continuity-reviewer + /security-review, then update PLAN.md and write the phase completion record. Use when finishing/closing out a phase in homelab/PLAN.md.
when_to_use: When a phase's work is complete and you're about to mark it done in homelab/PLAN.md.
---

# Phase gate

The mandatory completion gate for a homelab phase (see CLAUDE.md "Agents" + "Security
review gates"). **Do not mark a phase done in PLAN.md until this passes.** Follow the
subagent discipline in CLAUDE.md ("Context, subagents & effort"): ask each reviewer for
conclusions + `file:line` refs, not transcripts, and verify any claim before acting on it.

## Steps

1. **Name the phase** being closed (from `homelab/PLAN.md` → Phase order). State it explicitly.

2. **Run the gates and collect findings:**
   - **`doc-auditor`** agent — docs drift/consistency vs PLAN.md (real IPs must be `YOUR_*`
     placeholders per ADR-006; hostnames, VMIDs, phase/service status all consistent).
   - **`continuity-reviewer`** agent — backups/recovery for anything new this phase.
   - **`/security-review`** — pending changes on the branch.
   Launch the two agents **in parallel** (read-only, disjoint); then run `/security-review`.

3. **Triage:** fix blockers / HIGH findings now; record any accepted deferrals in PLAN.md
   so they're tracked, not lost.

4. **Only when clean:** update `homelab/PLAN.md` (mark the phase ✓ in Phase order + the
   relevant status lines) and write `homelab/docs/phases/<N>-<name>.md` — what shipped, key
   decisions/ADRs, verification done, and items carried forward.

5. **Pre-commit:** scan committed files for real private IPs (must be `YOUR_*` placeholders).
   Then commit and sync according to the repo's AGENTS.md rules.

Report: gate verdicts (one line each), what was fixed, what was deferred, and the commit ref.
