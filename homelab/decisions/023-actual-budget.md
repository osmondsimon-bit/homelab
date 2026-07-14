# ADR-023: Actual Budget on Carter

**Date:** 2026-07-14
**Status:** Accepted; deployment codified, live rollout pending

## Context

The homelab needs a private budgeting application that works across devices without exposing
financial data to the public internet. Carter is lightly loaded, has 32 GB RAM and ZFS, and keeps
the service away from apophis's compute-heavy workload and oneill's backup/monitoring role.

Actual supports both a Node.js server CLI and an official container. The CLI requires maintaining
a separate Node.js 22 runtime. The container carries the supported runtime and matches the proven
single-purpose VM pattern used for Vaultwarden. Actual is MIT-licensed.

## Decision

Run Actual Budget as **VM 127 `actual` on Carter**:

- Ubuntu 24.04 cloud image, 1 vCPU, 2 GB RAM, 10 GB ZFS disk.
- CPU `Skylake-Client-noTSX-IBRS`, so the VM remains migratable across the Coffee Lake cluster pair.
- Official `actualbudget/actual-server` container, pinned to a stable version and updated only in a
  deliberate maintenance window.
- Persistent application data at `/opt/actual/data`; no external database.
- Container port 5006 bound to VM loopback only. Tailscale Serve terminates HTTPS on port 443;
  `tag:actual` is restricted to `group:operators`. No LAN or public application listener.
- Password login is the only permitted login method. The operator creates the server password on
  first use and enables Actual's separate end-to-end budget encryption.
- Daily encrypted PBS VM image from Carter to oneill, retaining 7 daily and 4 weekly backups. Make a
  portable Actual ZIP export before application upgrades. A no-network PBS restore drill is required.
- No ZFS replication initially. Actual is not availability-critical; restore to an available cluster
  node is proportionate. Revisit only if measured recovery is inadequate.

Australian banks are not covered by Actual's currently documented built-in bank-sync providers, so
the initial workflow uses OFX/QFX/CSV imports. Bank integration is not configured.

## Consequences

- Carter gains a small steady workload while retaining ample headroom for the existing HA and
  Vaultwarden failover role.
- Docker remains confined to a dedicated VM rather than being installed on Carter or in a service LXC.
- The VM OS, node_exporter, patching policy, Tailscale, and container definition are reproducible from
  Ansible; finance state still depends on PBS and the portable export.
- Actual becomes part of the existing off-site-backup gap: oneill remains the only backup device until
  the planned encrypted off-site copy exists.
- The end-to-end encryption password is unrecoverable by the server. It must be stored off VM 127.

## References

- [Actual Docker installation](https://actualbudget.org/docs/install/docker/)
- [Actual server configuration](https://actualbudget.org/docs/config/)
- [Actual end-to-end encryption](https://actualbudget.org/docs/getting-started/sync/)
- [Actual backup and restore](https://actualbudget.org/docs/backup-restore/backup/)
- [Actual MIT license](https://github.com/actualbudget/actual/blob/master/LICENSE.txt)
