# ADR-004: Home Assistant as a Proxmox VM running HAOS

**Date:** 2026-06-12  
**Status:** Accepted — migration complete 2026-06-12, Zigbee confirmed working

## Context

Home Assistant is currently running as Home Assistant OS (HAOS) on a dedicated machine at
YOUR_HA_IP. The goal is to migrate it onto apophis so the dedicated machine can be retired,
reducing hardware and simplifying management.

## Decision

Run HAOS as a KVM virtual machine on apophis using the official HAOS qcow2 disk image. This is
the approach recommended by the Home Assistant project and preserves full add-on and supervisor
support.

### VM specification

| Setting | Value |
|---------|-------|
| CPU | 2 cores (socket 1) |
| RAM | 4 GB |
| Disk | 64 GB (imported from haos_ova-17.3.qcow2, on local-lvm) |
| Network | vmbr0, untagged (Home VLAN) |
| Machine type | q35 |
| BIOS | OVMF (UEFI) |
| NIC model | VirtIO |
| Migration IP | YOUR_HA_TEMP_IP (temporary) |
| Permanent IP | YOUR_HA_IP (reclaimed after old machine is retired) |

apophis total resources: Intel i7 8700T, 16 GB RAM, ~500 GB SSD.
After admin VM (4 GB) and host overhead (~2 GB), ~10 GB remains — 4 GB for HA is comfortable.

## Key addresses

| Device | IP |
|--------|----|
| HA VM (temporary) | YOUR_HA_TEMP_IP |
| HA VM (permanent) | YOUR_HA_IP |
| SLZB-06 Zigbee coordinator | YOUR_ZIGBEE_COORD_IP |

The coordinator is on a different subnet (a separate (IoT/Zigbee) subnet) — routing from the Home VLAN must reach it.

## Why Home VLAN, not IoT VLAN

Home Assistant acts as the integration hub for all IoT devices, trusted clients (phones, tablets),
and local automations. Isolating it in a separate VLAN would require firewall rules for every
device it talks to. The simpler and correct long-term placement is the Home VLAN, where it can
reach everything. Revisit if a strict IoT VLAN is introduced later.

## Lessons from migration

- OVMF does not scan VirtIO SCSI devices during EFI fallback boot — disk must be attached as SATA for HAOS to boot correctly on first provision.
- The `ha-vm-migrate.sh` script is updated to use SATA accordingly.

## Consequences

- The dedicated HA machine (YOUR_HA_IP) can be decommissioned after a verified migration.
- Weekly Proxmox VM snapshots cover HA backups for now (local storage).
- HAOS supervisor and add-ons continue to work as normal.
- The VM is sized conservatively; RAM and disk can be increased online if needed.
