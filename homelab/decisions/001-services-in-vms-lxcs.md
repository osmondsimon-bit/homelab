# ADR-001: Run all services in VMs or LXCs, not on the Proxmox host

**Date:** 2026-06-12  
**Status:** Accepted

## Context

The Proxmox host (apophis) is the single point of control for all virtualisation. Installing services
directly on it risks breaking the hypervisor, makes upgrades dangerous, and couples unrelated
concerns to the host OS.

## Decision

All user-facing and infrastructure services run inside VMs or LXC containers managed by Proxmox.
The host itself only runs Proxmox VE and its dependencies. No apt installs of services on the host
without explicit review.

## Consequences

- Slightly more resource overhead per service (acceptable on modern hardware).
- Snapshots and backups are straightforward via Proxmox.
- Host upgrades are safer because services are isolated.
- Requires deciding VM vs LXC per service (see future ADR if the pattern becomes complex).
