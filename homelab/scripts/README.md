# scripts/

Shell scripts for provisioning, maintenance, and admin tasks.

## Conventions

- Scripts are written for bash unless noted otherwise.
- Each script prints what it is about to do before doing it.
- Destructive or irreversible steps prompt for confirmation.
- Scripts assume they run from the mgmt-vm (YOUR_MGMT_VM_IP) unless the filename says otherwise.

## Layout

| Script | Purpose | Runs on |
|--------|---------|---------|
| `ha-vm-migrate.sh` | Create the HAOS VM on Proxmox from a downloaded qcow2 image | Proxmox host |
| `tailscale-lxc-provision.sh` | Create an unprivileged Tailscale LXC as a subnet router | Proxmox host |
| `backup-local-config.sh` | Back up local-only config and agent context to `homelab-private`. Because the copied `group_vars/all.yml` contains machine credentials, the destination is credential-bearing recovery material pending ADR-007 remediation; never use its nested `homelab/` as a working/deployment tree. | mgmt-vm |
| `unifi-query.sh` | Read-only UniFi (UDM) query helper for config review + troubleshooting — GET-only against the controller API via a view-only account; creds in gitignored `~/.unifi-ro.env` | mgmt-vm |
| `infra-portal-generate.py` | Python generator — reads `physical_infra/` YAML/JSON, renders D2 diagrams, outputs single-page HTML for the infra portal (CT 116). Run via daily systemd timer or `systemctl start infra-portal-generate.service` (ADR-020) | mgmt-vm |
| `git-precommit-scan.sh` | Privacy/secret guard (ADR-006). Default staged mode keeps the local pre-commit hook fast; `--full-tree` audits every tracked file. GitHub Actions runs the full-tree mode on pushes, pull requests, manual dispatch, and weekly. Use `--require-gitleaks` for a strict dependency check; append `# scan-allow` to an intentional IP/MAC example. | mgmt-vm + GitHub Actions |

> Provisioning is now primarily done via Ansible (`../ansible/`, ADR-005). These
> scripts are manual fallbacks and references the playbooks encode — not the primary path.

## Adding a script

1. Name it `<target>-<action>.sh` (e.g. `proxmox-snapshot.sh`, `lxc-create-base.sh`).
2. Add `set -euo pipefail` at the top.
3. Add a one-line comment block describing purpose, assumptions, and required variables.
4. Update this table.
