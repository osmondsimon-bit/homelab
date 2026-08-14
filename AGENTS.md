# Homelab agent instructions

## Project

This public repository documents and provisions Simon's Proxmox homelab. Project files live under
`homelab/`; `/home/simon` is the authoritative working and deployment tree. Use `index.md` for
navigation, `homelab/PLAN.md` for current state, and ADRs for accepted architecture decisions.

For work involving Git remotes, nested repositories, `physical_infra/`, home automation, shared
skills, or repository selection, read [ADR-025](homelab/decisions/025-repository-boundaries.md)
before editing or committing. A parent status, commit, or push never includes a nested repository.

The stack is primarily Bash, YAML, Ansible, Terraform, and Markdown. Services run in VMs or LXCs.
Remote administration uses Tailscale; only Home Assistant uses a Cloudflare Tunnel. Real network
addresses remain in gitignored inventory and committed documentation uses `YOUR_*` placeholders.

`/home/simon/homelab-private` is a separate credential-bearing recovery repository. Never read,
edit, search, or print its contents. Never use its nested snapshot as a working or deployment tree.

## Instruction hierarchy

1. This `AGENTS.md` defines repository-wide boundaries and working rules.
2. `homelab/PLAN.md`, ADRs, and scoped runbooks own project facts and accepted decisions.
3. `CLAUDE.md` is a Claude-specific entry point and cannot weaken this file.
4. [The shared workflow](homelab/docs/agents/shared-workflow.md) governs central skills and delegated work.
5. A work packet is subordinate to all project rules and cannot expand authority.

When two project documents genuinely conflict, stop and ask rather than guessing which is stricter.

## Working rules

- Inspect the relevant files and current Git state before changing anything. Preserve unrelated work.
- Ask only when a missing decision materially changes scope, architecture, privacy, cost, or risk.
- For material, ambiguous, or destructive work, present a short plan and obtain confirmation first.
  Proceed directly on clear, routine work already authorised by the user.
- Prefer the simplest change that satisfies the request. Avoid speculative flexibility and unrelated cleanup.
- Use red/green tests for behaviour changes. Scale checks to risk for documentation and mechanical edits.
- Keep durable context in the existing authoritative document; link to it instead of duplicating facts.
- Update affected documentation in the same focused change. New files start with a short purpose statement.
- Use minimal dependencies, verify new dependency licences, and avoid emojis in code and logs.

## Agent use

Default to one capable agent completing the task. Do not delegate routine questions, small edits, or
deterministic checks. Use a bounded subagent only when independent judgment materially reduces risk,
or large separable work can return a short result. Ask before using more than two subagents for one
task unless the user explicitly requested broader multi-agent review. Specialist homelab gates still
apply at the triggers documented in `CLAUDE.md` and the shared workflow.

## Safety and delivery

- Prompt before destructive or irreversible infrastructure operations and test against a snapshot where applicable.
- Assume private hosts are unreachable until Tailscale access is confirmed; otherwise the user runs SSH commands.
- Do not expose secrets, credentials, private addresses, or credential-bearing files in output or Git.
- No direct internet port forwarding. Keep the Terraform-creates / Ansible-configures boundary.
- After a completed and verified task, make a focused commit and sync it unless the user says not to.
  Use an imperative subject and explain what changed and why in the body.
