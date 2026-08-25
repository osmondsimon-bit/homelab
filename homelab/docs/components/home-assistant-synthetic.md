# Home Assistant synthetic test appliance

## Purpose

VM 201 is a fresh, isolated HAOS appliance for developing Home Assistant configuration against
Git-owned mock entities while the new house is being built. It is persistent for convenience but
contains no authoritative state and can be destroyed and recreated.

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

As of the 2026-08-25 read-only preflight, UniFi has an empty named Test zone rather than an attached
Test network. Default Test-to-External and Test-to-Gateway permits must be overridden before VM
allocation; this page does not claim that live isolation is already deployed.

## Continuity

**Reproducible from code.** VM 201 is deliberately excluded from PBS and Proxmox replication. Its
continuity sources are the public VM playbook, the pinned official HAOS image and digest, and the
separately pushed private synthetic package. After commissioning, perform a destroy/recreate drill
and record the observed RTO; never restore production state to shorten recovery.

## Operations

Use `ansible/playbooks/provision-ha-synthetic.yml` and the Home Assistant synthetic VM section of
the operations runbook. The default stages a stopped VM. Start mode requires separate attended
isolation approval and a dated evidence reference.
