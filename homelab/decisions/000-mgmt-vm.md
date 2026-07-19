# Decision 0001: mgmt-vm (admin/automation workstation)

> Originally titled "Admin VM" — the role description. The VM was named **mgmt-vm**;
> "Admin VM" is not a separate machine. See `homelab/PLAN.md` for current state.

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

## Independent cold secondary (revised 2026-07-19)

VM 128 `mgmt-vm2` on Carter is a separately built Ubuntu management workstation, normally powered
off. It is not a clone or continuously synchronized replica of VM 100. That avoids duplicate
machine IDs, SSH host keys, MAC addresses, hostnames, and accidental simultaneous use of the same
working tree.

The secondary contains a credential-free read checkout plus the gitignored Ansible inventory copied
from the primary at provisioning time. It generates its own automation key, which is authorized on
the PVE hosts and can be revoked independently. A second distinct SSH key is generated for use as a
write-enabled deploy key on only the public homelab repository; the primary account key is never
copied. It is sized at 2 cores, 8 GB RAM and a 64 GB thin disk; `onboot=0` and Proxmox VM protection
make activation and removal deliberate.

The recovery baseline includes both AI command-line clients without their authentication state:
Claude Code comes from Anthropic's signed stable apt channel, while Codex comes from OpenAI's
official npm package in Simon's unprivileged user-local prefix. Each client is authenticated
interactively on the secondary when needed. This makes AI assistance available during a primary
management outage without copying credentials, sessions, caches, or the primary home directory.

This improves control-plane recovery but does not bootstrap its own power-on. If Apophis is down,
the operator must first reach Carter, deliberately restore single-node quorum, and start VM 128.
Remote network routing survives through Tailscale CT 126 on Oneill, but Carter authentication remains
a separate prerequisite.

The first build and live validation passed on 2026-07-18: unique machine ID and SSH host key,
operator-desktop and primary-management login keys, key-only SSH, passwordless sudo, DNS, clean Git
checkout, QEMU guest agent, and Ansible connectivity to Apophis/Carter/Oneill. The VM then returned to
`stopped` with `onboot=0` and protection enabled. Its 64 GB zvol has no refreservation (2.28 GB actual
at build time), avoiding a 65 GB reservation on Carter for a normally-off recovery guest.
