# ADR-026: Home Assistant test environments

**Date:** 2026-08-21
**Status:** Accepted — synthetic environment commissioned for on-demand HA-15 development

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

VM 201 was created on Carter and independently revalidated in its stopped state on 2026-08-25. Its
generated MAC enabled a local-only DHCP reservation and destination-rule refinement. A later
attended start commissioned fresh HAOS, loaded only the Git-owned synthetic fixture and retained
the VM-level `onboot=0`, backup-exclusion and replication-exclusion contract.

A subsequent read-only comparison confirmed the UniFi fixed-address record matches the generated
VM NIC and the stateful TCP 8123 rule is narrowed to that reservation. This closes the reservation
gate but does not grant first-boot authority or replace post-boot exact-guest deny probes.

On 2026-08-29, HA-15 added stable HA-MCP 8.3.0 as a Synthetic-only administrative test harness.
It is reachable from one exact management source on TCP 9583 and has no route from the internet or
to production/device networks. Secret redaction, automatic per-edit backups and strict
best-practice gating are enabled; snapshot deletion and raw-YAML, filesystem and custom-tool beta
surfaces are disabled. Its capability URL lives only in the management client's mode-0600 global
configuration. Runtime MCP edits remain non-authoritative until exported to the private repository,
reviewed and reproduced by its renderer and tests. This exception does not authorize production
MCP, production credentials, production restore or physical-device control.

Installing or updating HAOS apps uses a separately attended egress window: only the selected DNS,
NetworkManager HTTP connectivity check and HTTPS artifact fetch are opened, then closed and
actively re-proved denied. Normal operation retains only the exact management-to-MCP path. The
kill switch is to stop or uninstall the app, remove that network rule and remove the client entry.
The initial 2026-08-29 installation closed with public DNS, HTTP and HTTPS all timing out from the
exact guest while the management-to-MCP path still returned the expected unauthenticated denial.

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
