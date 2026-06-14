# scripts/

Shell scripts for provisioning, maintenance, and admin tasks.

## Conventions

- Scripts are written for bash unless noted otherwise.
- Each script prints what it is about to do before doing it.
- Destructive or irreversible steps prompt for confirmation.
- Scripts assume they run from the admin VM (YOUR_MGMT_VM_IP) unless the filename says otherwise.

## Layout

| Script | Purpose | Runs on |
|--------|---------|---------|
| `ha-vm-migrate.sh` | Create the HAOS VM on Proxmox from a downloaded qcow2 image | Proxmox host |
| `tailscale-lxc-provision.sh` | Create an unprivileged Tailscale LXC as a subnet router | Proxmox host |

## Adding a script

1. Name it `<target>-<action>.sh` (e.g. `proxmox-snapshot.sh`, `lxc-create-base.sh`).
2. Add `set -euo pipefail` at the top.
3. Add a one-line comment block describing purpose, assumptions, and required variables.
4. Update this table.
