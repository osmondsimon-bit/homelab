# Decision 0001: Admin VM

## Decision
Create a dedicated Ubuntu Server VM called `mgmt-vm`.

## Purpose
Use it for homelab documentation, Git, SSH, scripts, Claude Code, and later Ansible.

## Rationale
Keep the Proxmox host clean and avoid installing tooling directly on the hypervisor.

## Initial sizing
- CPU: 2 cores
- RAM: 4 GB
- Disk: 64 GB
- Network: vmbr0 / Home VLAN initially

## Notes
This VM is not intended to host production services. It is an admin and automation workstation.
