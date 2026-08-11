# Shared agent workflow

This workflow routes homelab work between coordinating, specialist, and executor agents while preserving the project's existing review gates.

Project `AGENTS.md`, `CLAUDE.md`, `PLAN.md`, ADRs, and existing specialist gates govern all shared-skill use; if guidance conflicts, the stricter rule wins. Central shared-skill policies are available at [`/home/simon/agent-workflows/policies/`](/home/simon/agent-workflows/policies/), but the project remains authoritative.

1. Use `design-work` for ambiguous or material changes. Base proposals and implementation language on the existing `PLAN.md`, ADRs, and established domain vocabulary.
2. Approved work packets may go to Terra executor agents using `execute-work-packet`.
3. The root/coordinating agent owns integration, commit, and push.
4. Keep the existing specialist and gate responsibilities: invoke `infra-designer`, `doc-auditor`, and `continuity-reviewer` at their existing gates; use `/phase-gate` and `/security-review` at their existing gates.

Lower-cost executors must never access `homelab-private` or gitignored credential-bearing inventory, and must never deploy. They must escalate any design, security, or destructive ambiguity to the coordinating agent.
