# Maintenance record — 2026-11-13

Purpose: record the requested OS/security package maintenance, controlled restarts, recovery
evidence and remaining operator Apophis reboot. Current deployment facts belong in
[PLAN.md](../../PLAN.md).

## Scope and safeguards

The operator authorised fleet patching and planned restarts, reserving Apophis's host reboot for
themselves. They subsequently confirmed that HAOS/Core and pinned application-version upgrades
remain outside this window. Cold VMs 128/201 remained stopped. Management VM 100 and HA VM 200
remain running for the final operator host reboot; no delayed management reboot was armed.

Preflight confirmed access to all three hosts, both online Tailscale subnet routers, direct answers
from both DNS resolvers, fresh recurring backups, healthy pools with zero device error counters,
two-vote quorum and successful replication. The previous management restart's independent log
also confirmed its successful completion on November 8.

Refreshed signed apt metadata and no-removal simulations covered all 21 running apt targets:
three hosts, fourteen LXCs and four Ubuntu VMs. The reviewed plans contained 49 package upgrades
across ten machines. Updates retained existing configuration, installed kernels and Ubuntu package
phasing. No package removals or distribution upgrades were performed. Package logs remain private
on each changed target under `/var/log/homelab-maintenance-20261113/`.

Retain `maintenance-20261113` rollback checkpoints for the ten changed machines. Host roots and
CT 114's root use ZFS dataset snapshots; native Proxmox checkpoints cover CTs 110/126 and VMs
100/118/125/127. Grafana was stopped for its consistent checkpoint and restarted immediately.
CT 114's bind mount prevents native Proxmox snapshots, so only its root dataset was checkpointed.
Existing external-data and recurring-backup decisions remain unchanged.

## Completed updates and restarts

- All three hosts received their Vim security packages. Their installed and running PVE kernels
  already matched; this window installed no host kernel.
- Oneill received the Grafana and backup-router packages, then rebooted. All seven LXCs returned
  with new boot identities. Secondary DNS continued answering during the outage, and management
  name resolution remained functional.
- Carter and its two running Ubuntu VMs received their packages, then Carter rebooted. DNS,
  Minecraft, Vaultwarden and Actual recovered; all four running guests have new boot identities.
  Two-vote quorum returned automatically without an expected-vote override.
- Apophis received its packages while preserving its host boot identity. Its five running LXCs
  and Seerr VM subsequently completed separate graceful restarts with verified recovery.
- All four Ubuntu VMs received their GNU C Library security updates. Their other eligible packages
  included Docker runtime/tooling, Tailscale and management tooling. The three service VMs cleared
  their reboot flags after restart. Management retains its deliberate reboot flag for the
  operator's Apophis cycle.
- Actual's downloaded apt cache was cleaned, recovering space without removing packages,
  installed kernels or application data.

Primary vendor references reviewed: [Ubuntu GNU C Library security notice](https://ubuntu.com/security/notices/USN-9065-1),
[Grafana patch release](https://github.com/grafana/grafana/releases/tag/v13.3.1) and
[Tailscale changelog](https://tailscale.com/changelog).

## Recovery and final verification

All 21 apt targets passed clean package audits and no-removal simulations with zero eligible
pending packages or security packages. Ubuntu's phased rollout deferrals remain respected.
All eighteen guest security timers are enabled and active. Nineteen apt targets have new boot
identities; Apophis and management intentionally retain theirs. No newly failed units appeared.
Existing unsupported-unit failures and the separate finance-dashboard container's pre-existing
unhealthy baseline remain outside this package-maintenance scope.

Grafana's database health passed, and anonymous user access remained HTTP 401. Jellyfin's HTTP
health and VAAPI device access passed. Sonarr, Radarr, Seerr, Prowlarr, Vaultwarden and Actual
passed their application checks; Docker application image identities were preserved.

qBittorrent recovered with its required VPN/firewall services active, loaded input/forward/output
default-drop policies, a recent WireGuard handshake and working LAN-bound Web UI. Its VPN egress
differed from ordinary host egress. Gluetun's VPN egress likewise differed from ordinary VM egress.
Seerr and Gluetun reported healthy. ByParr's configured health probe passed when invoked directly;
its fifteen-minute Docker probe interval leaves the displayed health state at `starting` until
the next scheduled probe.

Refreshed maintenance metrics report 18/18 monitoring targets up, zero pending packages/security
packages, fourteen enrolled LXCs, five fresh backup groups and only management's reboot flag.
Prometheus has no firing alerts and Alertmanager's alert list is empty. The original three overdue
host-security alerts cleared through patching; no alert rules, thresholds or silences were changed.
All configured Glance monitor endpoints returned HTTP 200, and all three dashboard page routes
rendered. Home Assistant's authenticated monitoring scrape remains healthy.

Both DNS resolvers and subnet routers recovered. Authenticated PBS access passed from both cluster
nodes. Both replication jobs completed fresh successful runs with `FailCount 0`, `State OK`.
Pools remain healthy, two-vote quorum is present, and Apophis remains above its memory guardrail.
Every normal Apophis guest has autostart enabled.

## Operator handover

Apophis's out-of-band console reboot remains the operator's final step under the
[patching runbook](runbooks.md#patching--updates-adr-015). This will also restart management and
Home Assistant and activate management's pending library changes. Their final recovery and the
post-Apophis quorum/replication checks have not yet occurred; do not infer them from this record.

Retain rollback artifacts pending operator acceptance. HA appliance updates, pinned application
upgrades, existing security-audit findings and destructive recovery drills remain separate work.
