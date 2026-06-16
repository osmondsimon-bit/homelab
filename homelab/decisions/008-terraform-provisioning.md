# ADR-008: Terraform for infrastructure provisioning (Terraform creates, Ansible configures)

**Date:** 2026-06-14  
**Status:** Accepted (import **deferred** — see update)

> **Update (2026-06-16):** The `terraform import` is **deferred to cluster scale**. At 2–3 nodes
> the Ansible `provision-*.yml` playbooks already `pct create` **and** configure each LXC and
> recover them cleanly, so importing live VMs + refactoring those playbooks to config-only isn't
> worth it yet. **Ansible (pct) is the interim create+config mechanism**; the `terraform/` scaffold
> stays for when we adopt it (revisit at the 3-node cluster, ADR-009). The "Terraform creates"
> boundary below remains the *target*, not current reality.

## Context

ADR-005 made Ansible the provisioning layer, driving the LXC/VM lifecycle via `pct`/`qm` over SSH
with hand-rolled idempotency. That was the right minimal start, but it's imperative and the
idempotency is ours to maintain. As the lab grows to multiple nodes and more services (and a
3-node cluster — ADR-009), declarative infrastructure-as-code is worth adopting. Reference:
the `bpg/proxmox` Terraform provider (per the linked homelab-as-production-iac guide).

## Decision

**Terraform provisions; Ansible configures.** Clear split of responsibility:

- **Terraform** (`bpg/proxmox`, ≥ 0.95.0) owns the *existence and shape* of infrastructure — VMs,
  LXCs, their CPU/RAM/disks, NICs, and node placement. State is declarative and planned (`plan`
  before `apply`). Lives in `terraform/`.
- **Ansible** owns *configuration* — packages, services, app config, secrets delivery — applied to
  what Terraform created. ADR-005 stands for this role.
- Boundary: *Terraform = the box exists with the right shape; Ansible = the box is set up.* The
  `pct create`-via-Ansible lifecycle from ADR-005 is **superseded** by Terraform; Ansible's config
  role is unchanged.

**Conventions:**
- Provider declared in the **root module**; child modules only carry the `required_providers`
  source mapping (Terraform otherwise assumes `hashicorp/proxmox`). No `provider` block in children.
- Credentials (Proxmox API token) are passed via variables — never hardcoded. Real
  `terraform.tfvars` is gitignored (holds the API token); a `terraform.tfvars.example` is committed
  with placeholders (consistent with ADR-006).
- Existing running VMs (mgmt-vm, home-assistant, tailscale) are brought under management with
  `terraform import` — done deliberately, against live VMs, after the scaffold and token exist.

## Consequences

- Declarative, plan-before-apply, reviewable infrastructure — much better than imperative `pct`
  strings as node/VM count grows.
- New dependency: a **Proxmox API token** (and, for some `bpg/proxmox` operations like file/disk
  upload, SSH access to the node). The token is the prerequisite to first `apply`.
- The existing Ansible Tailscale playbook keeps working; over time, VM/LXC *creation* moves to
  Terraform and the Ansible playbooks shrink to config-only (or call out to roles).
- `terraform import` of live VMs is fiddly — mismatch between real VM config and the HCL must be
  reconciled carefully so a later `apply` doesn't try to recreate a running VM. Plan-only until the
  diff is clean.
- Secrets posture holds: API token in gitignored tfvars, not committed; not backed up to a repo
  (ADR-007 excludes credentials).
