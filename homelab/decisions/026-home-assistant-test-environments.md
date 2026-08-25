# ADR-026: Home Assistant test environments

**Date:** 2026-08-21
**Status:** Accepted — synthetic environment designed; live commissioning pending

## Purpose

This decision separates repeatable automation development from disaster-recovery proof. Both use
Home Assistant OS, but they have different trust, lifecycle, and data boundaries.

## Decision

Maintain two distinct Home Assistant test environment types:

1. The **Synthetic Home Assistant environment** is a persistent but rebuildable HAOS VM on Carter.
   Its behavior comes from Git-owned mock helpers, template entities, and disabled automations. It
   never contains a production backup, production credentials, a coordinator connection, vendor
   cloud access, production MQTT, or a route to device networks.
2. A **recovery replica** is a short-lived, operator-attended restore drill. It is isolated before
   first boot, exists only to prove backup recovery, and is destroyed after evidence is captured.
   It is not the development baseline.

The synthetic VM uses VMID 201, two vCPUs, 8 GiB RAM, a 64 GiB thin `local-zfs` disk, q35/OVMF,
and a VirtIO NIC on a dedicated Test network. It is `onboot=0`, excluded from Proxmox replication and
backup jobs, and starts only after a separate attended isolation approval. Public configuration
uses a `YOUR_TEST_VLAN_TAG` placeholder; the actual tag remains in gitignored inventory.

The initial 2026-08-25 read-only UniFi preflight found that the named Test zone existed without an
attached network. After operator changes, a same-day recheck confirmed a dedicated network with
internet access and mDNS disabled. Higher-priority rules block Test-to-External and all non-DHCP
Test-to-Gateway traffic, while existing internal-zone blocks remain effective. A named
commissioning client has TCP 8123 access using any ephemeral source port and automatic return
traffic. This satisfies the static stopped-staging gate; exact-guest active deny evidence remains a
separate pre-onboarding gate.

Home Assistant OS 18.2 is pinned for initial parity with the current live appliance. The official
[OVA qcow2 release asset](https://github.com/home-assistant/operating-system/releases/tag/18.2)
SHA-256 is verified before import. A later version change is a deliberate reviewed update, not an
implicit `latest` download.

## Carter recovery precedence

The synthetic guest is lower priority than Carter's recovery duties. Keep it stopped before:

- activating cold management VM 128;
- recovering or running production Home Assistant VM 200 on Carter; or
- Carter maintenance, constrained-capacity operation, or a recovery drill.

The VM does not auto-start. Provisioning and activation must preserve at least 3 GiB of Carter
`MemAvailable` after its 8 GiB allocation. The playbook rejects active Carter recovery guests and
ambiguous VMID ownership rather than trying to rearrange workloads.

## Authority boundary

The persistent VM proves automation and dashboard semantics against synthetic entities. It cannot
act on production switches, sensors, MQTT, Zigbee, Matter, cameras, locks, water controls, cloud
integrations, notifications, or tunnels. Loading a production backup into it is prohibited.

First boot is only a quarantine validation step. Before adding the private Git-owned test fixture,
the exact guest must produce active deny evidence for internal networks and production endpoints.
Only the Home Assistant UI path deliberately opened from an operator network is allowed.

## Consequences

- Automation work can proceed during the house build without buying or controlling every device.
- The VM is inexpensive to recreate, so PBS and replication capacity remain reserved for real state.
- Synthetic success does not prove hardware behavior; the live two-switch pilot remains the later
  hardware-in-loop gate.
- Backup restoration remains a separate, disposable and more tightly attended exercise.
