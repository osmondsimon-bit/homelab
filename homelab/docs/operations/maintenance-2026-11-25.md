# Maintenance record — 2026-11-25

Purpose: record the requested patching checks, staged package maintenance, validation and remaining
operator actions. Current deployment facts belong in [PLAN.md](../../PLAN.md).

## Scope and safeguards

The operator requested that patching and maintenance tasks be checked and executed. Native approval
confirmed each material host stage before installation. This window applies ordinary signed apt
packages with no package removals, distribution upgrades, forced phasing or automatic reboots.
Pinned application images, HA appliance updates, credential handling, firewall changes and recovery
drills remain separate decisions. The credential-bearing recovery repository and relay state/token
files are outside the task.

Preflight reached all three Proxmox hosts with verified SSH identities. All pools were healthy and
both cluster nodes were quorate. Both replication jobs reported zero failures. Monitoring had all
18 targets up; the only pending/firing alerts concerned host security packages. All five recurring
backup groups were fresh, approximately 10–13 hours old, so the November 16 PBS catch-ups no longer
required action.

Signed apt metadata refreshes, no-removal upgrade simulations and clean package-database audits
covered all 21 running apt targets. Eighteen guest security timers were enabled and active. The
reviewed plans contained 353 package changes across ten machines. Eleven targets had no eligible
pending packages. Actual had 915 MiB free and needs additional space consideration before its
full update. The separately approved cleanup below resolved that constraint. Cold guests and
HAOS are excluded from apt work.

## Staged execution

| Target | Reviewed changes | Status |
| --- | ---: | --- |
| Oneill | 73 | Completed; clean package audit and no pending packages |
| Monitoring CT 114 | 1 | Grafana 13.3.2 installed and verified |
| Carter | 73 | Completed; clean package audit and no pending packages |
| Minecraft CT 129 | 13 | Completed; clean package audit and no pending packages |
| Vaultwarden VM 118 | 35 | Completed; clean package audit and no pending packages |
| Actual VM 127 | 33 | Completed; clean package audit and no pending packages |
| Apophis | 73 | Completed; clean package audit and no pending packages |
| qBittorrent CT 121 | 2 | Completed; clean package audit and no pending packages |
| Management VM 100 | 17 | Completed; clean package audit and no pending packages |
| Seerr VM 125 | 33 | Completed; clean package audit and no pending packages |

Rollback checkpoints use `maintenance-20261125`. Host roots and bind-mounted container roots use
ZFS snapshots. Grafana was stopped briefly while its root checkpoint was taken and immediately
restarted. Its external Prometheus time-series mount remains outside that root checkpoint under
the existing non-critical-history recovery decision. Package output stays in private target-local
maintenance logs. An existing maintenance marker requires inspection before another installation;
an interrupted action is not automatically retried. All ten reviewed package stages completed:
353 package changes, clean package audits and zero remaining simulated package changes.

The operator separately approved deleting exactly two unused Actual server images:
`actualbudget/actual-server:26.7.0` and `actualbudget/actual-server:26.9.0`. Their full image IDs were
rechecked against the recorded candidates and all running/stopped container references before
non-forced deletion. The current image, immediate 26.10.0 rollback image, application data and
Proxmox checkpoints were preserved. No finance worker or dashboard images were removed. Actual
had 1,947 MiB free after patching.

## Package-stage verification

Oneill and all seven containers retained their boot identities. No new failed systemd units
appeared. Both Technitium resolvers answered direct DNS checks. The independent Tailscale router
remained online. Grafana reported version 13.3.2, database `ok` and HTTP 200; Prometheus and
Alertmanager readiness returned HTTP 200. Oneill's new installed kernel requires a deliberate
reboot before its kernel fixes take effect.

Carter and Apophis retained quorum, healthy pools and zero replication failures after their
package stages. No new failed systemd units appeared. Vaultwarden and Actual returned HTTP 200;
their container and image identities, network modes and Tailscale state were preserved. The
existing finance-dashboard unhealthy Docker status predates this window and remains separate.

Seerr returned HTTP 200. All four media-stack container/image identities and shared-network
references were preserved. Gluetun remained healthy and its verified egress differed from ordinary
VM egress. ByParr was initially `starting` under its slow Docker probe. qBittorrent and WireGuard
were active and the loaded input, forward and output firewall policies remained default-drop.

## Controlled restarts and final checks

Oneill and Carter each completed a separately approved single controlled reboot. Preflight checked
fresh backups, the alternate DNS resolver and Tailscale subnet router, healthy storage, and
autostart for every expected running guest. Recovery verified changed host and guest boot identities,
the newest installed host kernel `7.0.14-30-pve`, both DNS resolvers and no new failed units. All
seven Oneill containers and all four Carter guests returned. Vaultwarden and Actual run their
newest installed Ubuntu kernel `6.8.0-151-generic`, respond with HTTP 200 and retain their container
and image identities. Two-vote quorum returned without an expected-vote override.

Final package simulations and clean package-database audits passed on all 21 targets, with zero
eligible pending packages/security packages and all eighteen guest security timers active. The
maintenance collectors were refreshed on all three hosts and four Ubuntu VMs. Pools remain healthy,
both replication jobs report zero failures, authenticated PBS status checks succeeded, and all hosts
remain above the 3 GiB available-memory guardrail. Minecraft's process/listener health endpoint,
Jellyfin health, Sonarr/Radarr ping and ByParr's direct configured health probe returned success;
ByParr's Docker status is now healthy.

All eighteen monitoring targets are up and every collected blackbox probe succeeds. All five
backup groups are fresh, approximately 12–15 hours old. The host security-update alerts cleared;
there are no firing alerts. Three `DeliberateRebootOverdue` alerts are pending for Apophis,
management and Seerr, matching the remaining operator restart below. No alert thresholds or
silences were changed.

Apophis's console reboot remains an operator action under the
[patching runbook](runbooks.md#patching--updates-adr-015); no automated Apophis reboot is armed.
It still runs `7.0.14-28-pve` with `7.0.14-30-pve` installed. Management and Seerr retain their
deliberate reboot flags and will cycle with HA during the host reboot. CT 121 also retains a guest
reboot marker, but an LXC shares its host's kernel and does not need a separate kernel reboot.
Post-Apophis recovery, quorum and replication checks remain unperformed.

## Vendor review

- [Grafana 13.3.2](https://github.com/grafana/grafana/releases/tag/v13.3.2) fixes two published
  vulnerabilities; the official apt candidate was reviewed before installation.
- [Docker Engine 29.10.1](https://docs.docker.com/engine/release-notes/29/#29101) includes security
  fixes. Docker package updates preserve the pinned application images; container identity and
  health must be checked afterward.
- [Bubblewrap releases](https://github.com/containers/bubblewrap/releases) and
  [upstream advisories](https://github.com/containers/bubblewrap/security/advisories) were reviewed.
  The local 0.13.1 package remains the recorded approved build. Ubuntu's
  [USN-8779-2](https://ubuntu.com/security/notices/USN-8779-2) documents a reverted traversal fix;
  a lower-version vendor package is not assumed to replace the local build safely. Exact static
  dependency patch-level verification remains separate; this window does not claim a complete
  runtime vulnerability clearance.
- The connected GitHub query returned no open homelab pull requests. This does not claim that every
  pinned application is current; deliberate application/appliance upgrades remain a separate stage.
