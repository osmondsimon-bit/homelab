# Maintenance record — 2026-11-08

Purpose: record the requested monthly apt package updates, rollback checkpoints, service checks
and outstanding kernel activation. Current deployment facts belong in [PLAN.md](../../PLAN.md).

## Scope and safeguards

The operator authorised all routine monthly packages shown in Glance. Signed apt metadata and
no-removal simulations were reviewed across three Proxmox hosts, fourteen running LXCs and four
Ubuntu VMs. The refreshed plans contained 128 package operations across eight targets; thirteen
LXCs were already current. HA appliance updates, pinned application-image changes and reboots
were outside this package-only pass.

Preflight confirmed both subnet routers, all monitoring targets, fresh recurring backups,
healthy pools, two-vote cluster quorum and successful replication. Existing unsupported
OpenIPMI unit failures were preserved. `maintenance-20261108` checkpoints cover changed host
root datasets, CT 121's root dataset and VMs 100/118/125/127. External bind-mounted media keeps
its existing backup decision. Updates retained existing configuration, installed kernels and
application images; no package removals were permitted.

These local checkpoints supplement existing recovery decisions. This window changes no recurring
backup scope and establishes no new restore-drill evidence. The credential-bearing recovery
repository and local-config backup script were not accessed. Package-manager logs remain private
on changed targets at `/var/log/homelab-maintenance-20261108-apt.log`.

## Completed work

- Oneill, Carter and Apophis were updated separately, with guest/service health checked before
  advancing. Corosync and Proxmox management packages were included. Both cluster votes remained
  present after each clustered host update. No host reboot was required or performed.
- Apophis already ran its newest installed kernel at preflight, resolving the earlier documented
  pending activation. This window did not perform that intervening reboot.
- CT 121 received its zlib security package. qBittorrent, WireGuard and its timers remained active;
  the input/forward/output killswitch chains retained drop policies, the tunnel handshake was
  recent, and VPN egress differed from ordinary host egress.
- Ubuntu kernel packages were installed on all four apt VMs while preserving their application
  images and running state. Actual's constrained root filesystem received an apt download-cache
  cleanup, restoring approximately 1.4 GiB available space without removing installed kernels.

Reviewed primary vendor notes: [Corosync 3.2.0](https://github.com/corosync/corosync/releases/tag/v3.2.0).

## Final verification

All 21 apt targets passed `dpkg --audit` and post-update simulation with zero eligible pending
packages. Refreshed Prometheus metrics independently report zero pending packages and zero pending
security packages. All fourteen LXC security timers and all four Ubuntu VM security timers remain
enabled and active. Changed targets retained their boot identities and existing failed-unit baseline.

Prometheus reports 18/18 targets up, no firing alerts, no low-filesystem series and no stale backup
groups. Both DNS resolvers answered directly, both subnet routers passed their health endpoints,
both cluster votes are present, and both replication jobs remain enabled with `FailCount 0`,
`State OK`. Authenticated PBS storage access passed on both cluster nodes. All three Glance pages
rendered without template errors, with the Active Alerts panel reporting no firing alerts.

Vaultwarden and Actual passed their application checks with online Tailscale backends. Seerr and
Prowlarr passed HTTP checks; Gluetun's egress differed from ordinary VM egress. qBittorrent's VPN
and killswitch checks passed. Management SSH/exporter services remained active. Application image
identities and container running states were unchanged on the three Docker VMs.

## Remaining work

Ubuntu VMs 100/118/125/127 still run their previous kernels and require deliberate restarts to
activate the installed kernel packages. Their four reboot flags are expected; package installation
does not activate a new running kernel. Restart service VMs separately and verify recovery between
them. The management VM restart ends the control session and must be handled as a final, separately
approved step with independent verification. No Proxmox host reboot is required.

Retain the rollback checkpoints pending operator acceptance. HA appliance updates, pinned
application-version reviews, existing security-audit findings and restore/failure drills remain
separate work.
