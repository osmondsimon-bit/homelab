# Maintenance record — 2026-11-06

Purpose: record the approved fleet patching, controlled restarts, Glance correction, recovery
evidence and final management-VM reboot procedure. Current deployment facts belong in
[PLAN.md](../../PLAN.md).

## Scope and safeguards

The operator approved snapshots and package updates on all three Proxmox hosts, fourteen running
LXCs and four Ubuntu VMs, including the available Jellyfin/Grafana packages. Oneill and Carter
were restarted separately, followed by Apophis's running guests. Apophis itself remained running;
cold VMs 128/201 remained stopped. HAOS/Core and pinned application-version upgrades were excluded.
The management VM's reboot was explicitly approved as the last step, ending the agent session.

Preflight found 18/18 monitoring targets up and three overdue host-security alerts. Both DNS
resolvers answered directly; the control node had both configured. Both subnet routers were online,
all pools were healthy with zero device error counters, both cluster votes were present,
replication was healthy and all five recurring backup groups were within their freshness budgets.
Remaining guests had no unrelated pending configuration to apply during restart.

Signed apt metadata and simulations were reviewed. Updates used `--no-remove`, retained existing
configuration and old kernels, respected Ubuntu package phasing and preserved application image
identities. Retain `maintenance-20261106` rollback checkpoints for all 21 apt targets. Native
Proxmox snapshots were used where supported; bind-mounted LXCs received root-dataset ZFS snapshots.
Media applications were stopped for coherent database checkpoints; Grafana was stopped for its
checkpoint. External bind-mounted data keeps its existing backup decision. Package-manager logs
remain private on each target at `/var/log/homelab-maintenance-20261106-apt.log`.

These local checkpoints supplement existing recovery decisions. This window changes no recurring
backup scope and establishes no new restore-drill evidence. The credential-bearing recovery
repository and `backup-local-config.sh` were not accessed.

## Completed work and recovery

- Oneill and Carter received their host/guest updates and returned with new boot identities.
  Oneill's seven LXCs and Carter's normal guests recovered. Cluster quorum returned automatically;
  no expected-vote override was used.
- Apophis received its host packages without a reboot, preserving its original boot identity.
  Its five LXCs and VM 125 completed individual verified restarts after the host update. Docker
  runtime updates retained the original application image identities on VMs 118/125/127.
- Jellyfin's updated public API version was verified. Two-second VAAPI and QuickSync synthetic
  encodes passed as its service user. Grafana's health API reported a healthy database; its
  anonymous user API retained HTTP 401.
- qBittorrent's first service-stop request was canceled by systemd. Inspection found it running
  with its VPN/firewall active and no queued jobs; a retry stopped it successfully for its
  checkpoint. After restart, all three required services and firewall drop policies passed;
  its IPv4 egress differed from ordinary host egress.
- Seerr/Prowlarr HTTP checks, Seerr/Gluetun health and ByParr's configured health probe passed.
  Gluetun's egress differed from ordinary VM egress. Vaultwarden and Actual passed application
  checks and retained online private Tailscale backends.
- HA's Proxmox ACPI restart request timed out. Its supported `hassio.host_shutdown` action then
  completed a graceful shutdown; `qm start 200` produced a new QEMU process. Authenticated,
  certificate-verified HA readiness returned with the pre-existing Core version preserved.
  The fallback is recorded in [the patching runbook](runbooks.md#patching--updates-adr-015).
- The management VM received its package updates and passed its package, SSH/exporter and
  maintenance-timer checks. Its reboot remains the final step below.

Reviewed primary vendor notes: [Jellyfin 12.4](https://github.com/jellyfin/jellyfin/releases/tag/v12.4),
[Grafana 13.3](https://grafana.com/docs/grafana/latest/whatsnew/whats-new-in-v13/whats-new-in-v13-3/),
[Tailscale](https://tailscale.com/changelog) and
[Docker 29.9.3](https://docs.docker.com/engine/release-notes/29/#2993).

## Glance correction and final verification

Update Review displayed older rendered pins despite the inventory and running applications already
having newer versions. The existing Glance playbook validated and refreshed its configuration,
correcting the Vaultwarden, Seerr and Actual labels. The component guide now records the required
[refresh after pin deployment](../components/glance.md#how-its-managed). Glance's binary pin and
monitoring thresholds were preserved; no alerts were silenced.

All three Glance pages rendered without widget errors. All nineteen service checks passed from
Glance, including Minecraft's deliberately source-restricted health endpoint. Fresh monitoring
reported 18/18 targets up, zero firing alerts in Prometheus and Alertmanager, zero eligible pending
or security packages across all 21 targets, fourteen enrolled LXC security timers, and five fresh
backup groups. Only Apophis retained the intentional host-reboot flag.

Both split-direction replication jobs completed fresh successful runs with `FailCount 0`, `State OK`.
Authenticated PBS storage access passed on both cluster nodes; the HA backup-share service and
listener were active. All pools retained zero device errors, host-health/scrub/trim timers remained
active, and Apophis retained approximately 12.8 GiB available memory, above its 3 GiB guardrail.

## Final control-node reboot and remaining boundaries

After the documentation commit and sync, arm the one-shot management-VM reboot verifier staged on
Apophis at `/root/homelab-maintenance-20261106-mgmt-reboot.py`. A short delay allows the final report
to reach the operator before VM 100 restarts. The helper checks Apophis's original boot identity,
quorum, pending VM configuration and the package audit before issuing the approved `qm reboot 100`.
It then verifies a new guest boot identity, active SSH/exporter services, a clean package audit and
refreshed maintenance metrics. It never reboots Apophis.

The independent result is recorded on Apophis in the root-only
`/var/log/homelab-maintenance-20261106-mgmt-reboot.log`. A `VERIFIED` line is the evidence for this
last restart; the agent session's fleet verification above precedes that final control-node cycle.

Apophis kernel activation remains an out-of-band operator task. Four legitimate pinned-version
reviews remain separate from this OS maintenance window. Existing security-audit and restore-drill
work stays open. Pre-existing unsupported OpenIPMI unit failures were preserved; the separate
finance-dashboard's unhealthy preflight baseline was outside the approved application-update scope.
Retain rollback artifacts pending operator acceptance.
