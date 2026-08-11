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
