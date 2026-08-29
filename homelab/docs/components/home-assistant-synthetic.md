# Home Assistant synthetic test appliance

## Purpose

VM 201 is a fresh, isolated HAOS appliance for developing Home Assistant configuration against
Git-owned mock entities while the new house is being built. It is persistent for convenience but
contains no authoritative state and can be destroyed and recreated.

**As built:** staged on Carter on 2026-08-25, then commissioned through an attended first boot for
HA-15. The exact machine, disk, NIC and exclusion contract passed idempotent validation. Fresh HAOS
contains only the Git-owned synthetic fixture and a guarded HA-MCP 8.3.0 test harness; it contains
no production restore or device binding. The VM remains on-demand with `onboot=0`.

## Placement and lifecycle

- **Node:** Carter, subordinate to its production-recovery role.
- **Shape:** q35/OVMF, 2 vCPU, 8 GiB RAM, 64 GiB thin `local-zfs`, SATA HAOS boot disk.
- **Network:** VirtIO on a dedicated isolated Test network; actual tag and address remain local-only.
- **Power:** `onboot=0`; the normal state is stopped.
- **Source:** pinned official HAOS 18.2 OVA qcow2 plus the independently synced private
  home-automation repository's synthetic package.

It must be stopped before VM 128 starts, VM 200 is recovered onto Carter, or Carter enters
maintenance/recovery. It is excluded from GuestDown and the Glance workload table because powered
off is healthy; the provisioning playbook instead proves its identity, shape, isolation gates, and
stopped staged state.

## Trust boundary

The appliance has no production backup, MQTT, coordinator, device-VLAN, cloud, notification,
tunnel, passthrough, or vendor-account authority. The first boot is an attended quarantine test.
The exact guest must prove allowed operator UI access and denied production paths before onboarding
or receiving the test fixture.

The 2026-08-25 read-only preflight initially found an empty named Test zone. After operator changes,
a same-day recheck accepted the static boundary: normal internet access and mDNS are disabled,
gateway services are narrowly selected, and External and internal destinations are blocked. Named
commissioning access is exact and stateful. App installation uses a temporary DNS/HTTP/HTTPS egress
window that must be closed and deny-tested after each attended update.

HA-MCP is an administrative exception inside this otherwise synthetic boundary. Only the exact
management client may reach TCP 9583. The app uses a secret capability path, redacts secrets,
captures per-edit backups and requires strict best-practice acknowledgement. Snapshot deletion and
raw-YAML, filesystem and custom-tool beta surfaces are disabled. Its runtime changes are disposable
experiments until reproduced from the private repository; it has no production or commissioning
authority.

The initial 2026-08-29 app window was closed and actively verified: public DNS, HTTP and HTTPS were
denied from the guest, while the exact management path to TCP 9583 remained reachable and rejected
an unauthenticated request as designed.

## Continuity

**Reproducible from code.** VM 201 is deliberately excluded from PBS and Proxmox replication. Its
continuity sources are the public VM playbook, the pinned official HAOS image and digest, and the
separately pushed private synthetic package. After commissioning, perform a destroy/recreate drill
and record the observed RTO; never restore production state to shorten recovery.

## Operations

Use `ansible/playbooks/provision-ha-synthetic.yml` and the Home Assistant synthetic VM section of
the operations runbook. The default stages a stopped VM. Start mode requires separate attended
isolation approval and a dated evidence reference. HA-MCP lifecycle, egress-window closure and the
client kill switch remain explicit operator steps because the secret path and HA runtime state do
not belong in public Ansible inventory.
