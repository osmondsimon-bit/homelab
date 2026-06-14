# ADR-002: Single untagged VLAN to start, VLANs later

**Date:** 2026-06-12  
**Status:** Accepted

## Context

A full VLAN segmentation strategy (IoT, servers, management, trusted clients) is the long-term
goal, but adds complexity before any services are running. Getting services up first is higher
priority.

## Decision

All hosts start on a single untagged network (YOUR_LAN_CIDR) via vmbr0. VLANs will be introduced
once the core services (Home Assistant, monitoring, backups) are stable.

Key addresses:
- Gateway: YOUR_GATEWAY_IP
- Proxmox host (apophis): YOUR_PROXMOX_IP
- Admin VM: YOUR_MGMT_VM_IP

> **Note (2026-06-14, superseded detail):** The "Admin VM" is now named **mgmt-vm** at **YOUR_MGMT_VM_IP**. This ADR records the original plan; see `homelab/PLAN.md` for current addressing.

## Consequences

- IoT and trusted devices share the same broadcast domain initially — acceptable short-term risk.
- Adding VLANs later will require reconfiguring vmbr0 and reassigning VM network interfaces.
- Static IPs should be assigned per host now so the eventual VLAN migration is cleaner.
