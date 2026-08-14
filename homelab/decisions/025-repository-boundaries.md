# ADR-025: Repository boundaries and private design workspace

**Date:** 2026-08-14  
**Status:** Accepted

## Context

The local working tree brings logical infrastructure, private physical design data, reusable agent
workflows, and unrelated applications onto one desktop. Git nesting makes that convenient but also
makes it easy to commit in the wrong repository or assume that a parent push includes a nested
repository.

Home-automation design needs room and device detail that must remain private. The infrastructure
portal needs to read that detail locally, while the public homelab repository must remain safe to
publish. Credential-bearing recovery material needs a stronger boundary than ordinary private
design data.

## Decision

Use these independent Git repositories:

| Repository | Local working tree | Purpose and visibility | Operating boundary |
| --- | --- | --- | --- |
| `osmondsimon-bit/homelab` | `/home/simon` | Public homelab code, sanitised documentation, and repository meta | `homelab/physical_infra/` remains ignored; public commits must not contain room/device detail, credentials, or real addresses. |
| `osmondsimon-bit/home-automation` | `/home/simon/homelab/physical_infra/home_automation` | Private house automation design, inventories, generated projections, research, and later HA configuration | This is a nested standalone repository with its own `.git`, `origin`, `main`, commits, tests, and pushes. A parent homelab commit or push never includes it. |
| `osmondsimon-bit/homelab-private` | `/home/simon/homelab-private` | Private credential-bearing recovery material | Keep separate from design data. Agents do not access this working tree; operators manage it directly. |
| `osmondsimon-bit/agent-workflows` | `/home/simon/agent-workflows` | Reusable shared agent workflow and skill catalogue | Change and publish it independently; installing or consuming a skill does not make it part of homelab history. |
| `osmondsimon-bit/finance-dashboard` | `/home/simon/finance-dashboard` | Separate finance application | It is outside the homelab project and has its own lifecycle. |

The nested home-automation repository is intentionally not a Git submodule. The public checkout
must not require private repository access, and the local portal may enrich itself from private data
only when that working tree is present.

The rest of `homelab/physical_infra/`—including house, network, rack, and compute design data—remains
local-only and is protected by the mgmt-VM PBS backup under ADR-019/ADR-012. It is not included when
`home-automation` is pushed. Cross-repository references in the home-automation design therefore
assume the authoritative `/home/simon/homelab/physical_infra/` layout is present locally.

## Working procedure

Resolve the target repository before editing or publishing:

```bash
git -C TARGET_PATH rev-parse --show-toplevel
git -C TARGET_PATH status -sb
```

Commit, verify, and push in that same working tree. The common project commands are:

```bash
# Public infrastructure and portal code
git -C /home/simon status -sb
git -C /home/simon push

# Private home-automation design
git -C /home/simon/homelab/physical_infra/home_automation status -sb
git -C /home/simon/homelab/physical_infra/home_automation push

# Shared workflow catalogue
git -C /home/simon/agent-workflows status -sb
git -C /home/simon/agent-workflows push
```

Run status in both homelab working trees after a task that changes portal code and private design
data. Make focused commits in each repository; one repository being clean says nothing about the
other. Untracked inputs are not backed up by Git until deliberately reviewed and committed.

## Consequences

- Private home-automation history can be synced without exposing it through the public repository.
- The portal can combine public generator code with private local design data at generation time.
- A change spanning portal code and home-automation data normally produces two commits and two
  pushes.
- A clone of `home-automation` alone cannot validate sibling house/network/rack references; the
  complete local physical-design surface or a future export mechanism is required.
- Moving the remaining physical-infrastructure data to GitHub would require a separate privacy and
  repository migration decision; this ADR does not silently broaden the current publication scope.
