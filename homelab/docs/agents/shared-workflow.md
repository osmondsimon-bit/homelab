# Shared agent workflow

This workflow applies when homelab work uses central skills, executors, or independent reviewers.
`AGENTS.md` defines repository rules; `PLAN.md`, ADRs, and runbooks own project facts and decisions;
`CLAUDE.md` is a tool-specific entry point; central policies and approved work packets are subordinate.
If project sources conflict, stop and ask rather than guessing which is stricter.

Default to one coordinating agent. It may design, implement, run deterministic checks, integrate,
commit, and push routine work without delegation. Do not delegate small documentation or configuration
edits, ordinary bug fixes, repository navigation, or routine test runs.

Use one bounded subagent when a task has a large separable component that can return a short result,
or when independent judgment materially reduces risk. Ask before using more than two subagents for
one task unless the user explicitly requested broader multi-agent review. Follow the central
[agent and model routing policy](/home/simon/agent-workflows/policies/model-routing.md).

Use `design-work` for material ambiguity, not as ceremony for an already clear small change. An
approved packet may go to one Terra executor using `execute-work-packet`; the coordinating agent
owns integration, commit, and push. One reviewer may cover multiple review lanes unless a project
gate requires genuine separation.

Keep the existing specialist triggers: `infra-designer` for new guests or significant network
changes; `doc-auditor`, `continuity-reviewer`, `/security-review`, and `/phase-gate` at their documented
phase, backup, security, or continuity gates. Do not invoke the full set for ordinary tasks.

Executors never access `homelab-private` or gitignored credential-bearing inventory and never deploy.
They escalate design, security, privacy, destructive, or authority ambiguity to the coordinator.

## Matt Pocock skill compatibility

When a Matt Pocock engineering skill is used for this homelab, treat `homelab/` as the project root
and preserve the project's existing sources of truth. Domain terms belong in the relevant scoped
design or component document; current state belongs in `PLAN.md`; architectural decisions use the
existing `decisions/NNN-short-title.md` template. Do not create `CONTEXT.md`, `CONTEXT-MAP.md`, or a
parallel `docs/adr/` tree.

Run `setup-matt-pocock-skills` before the first tracker-backed flow, but adapt its proposed files to
these paths and obtain approval before it writes. Before publishing tracker items, verify that the
configured tracker has the canonical triage labels plus `wayfinder:map` and the four
`wayfinder:<type>` labels; creating labels or issues is an external write and requires the user's
authorization. The subagent limits above apply when a skill requests parallel research or review.
