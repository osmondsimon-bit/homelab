# Maintenance record — 2026-10-22

Purpose: record the requested monthly package maintenance, Oneill/Carter restarts, recovery checks,
and remaining operator work. Current infrastructure state belongs in [PLAN.md](../../PLAN.md).

## Scope and safeguards

The operator authorised monthly maintenance, including patching and restarting Oneill and Carter.
Preflight verified both DNS resolvers directly from mgmt-vm, both online Tailscale subnet routers,
healthy pools with zero read/write/checksum counters, two-node quorum, successful replication, and
no active host management tasks. All five recurring backup groups were within their 36-hour budget.
Prometheus initially reported 18/18 targets up and security-update warnings for Oneill and Carter.

Signed apt metadata and simulations were reviewed across three hosts, fourteen running LXCs, and
four Ubuntu VMs. Updates used `--no-remove`, retained existing configuration and old kernels, and
respected Ubuntu package phasing. Application image identities were compared before and after
Docker runtime updates. No pinned application images or Minecraft server version were changed.
No open Renovate or other pull requests were present when the maintenance queue was checked.

Retained `maintenance-20261022` snapshots cover host root datasets and changed guests: VMs
100/118/125/127, CTs 110/126/129, and CT 121's root dataset. These local rollback points supplement
the existing backup/rebuild decisions; this window does not establish new restore-drill evidence.

## Completed work

- Oneill received Debian security updates and the new PVE kernel, then completed a normal reboot.
  Verified SSH returned with a new boot identity in 44 seconds; configured guest startup completed
  afterward. All seven LXCs recovered. Primary DNS, PBS proxy and authenticated backup-storage
  access, Samba, monitoring, Glance and the portal passed checks. Grafana reported its database
  healthy, returned HTTP 200 for health, and retained HTTP 401 for anonymous user access.
- Carter received the same host packages and completed its normal reboot, returning verified SSH
  with a new boot identity in 49 seconds. Quorum returned automatically; CTs 117/129 and VMs
  118/127 recovered, while cold VMs 128/201 remained stopped. Secondary DNS, Minecraft's process
  and listener probe, Vaultwarden's healthy container, Actual's HTTP endpoint, and both tailnet
  backends passed. Both restarted hosts now run kernel `7.0.14-25-pve`.
- Apophis received the same host packages without a reboot. Its boot identity is unchanged and
  it continues running `7.0.14-24-pve`, with `7.0.14-25-pve` installed for later console activation.
  Preflight showed that the previous kernel had already been activated since the last record;
  this window did not perform that earlier reboot.
- Both subnet-router LXCs received Tailscale's security patch separately, with an online alternate
  router available. Both subsequently returned to `Running` with online backends.
- Ubuntu VMs 100/118/125/127 received their eligible ordinary OS packages. The management VM was
  patched through its existing QEMU guest agent because local noninteractive sudo required a
  password; Node.js updated to `24.22.1`. Docker updated to `29.9.2` on VMs 118/125/127, with all
  application image identities preserved. No Ubuntu VM requested a kernel reboot.
- Minecraft's five eligible Ubuntu packages and qBittorrent's three Debian DNS-library packages
  were updated. The other ten LXCs had no eligible package changes.
- Vaultwarden, Actual, Seerr and Prowlarr passed HTTP checks after their runtime updates.
  Gluetun's egress remained distinct from ordinary VM egress. ByParr's unchanged configured health
  probe passed manually while its fifteen-minute automatic check still reported `starting`.
  qBittorrent's three required services were active, its three loaded killswitch chains retained
  drop policies, and its IPv4 egress differed from ordinary host egress.

Reviewed primary vendor notes: [Tailscale 1.104.2](https://tailscale.com/changelog) and
[Docker 29.9.2](https://docs.docker.com/engine/release-notes/29/#2992), both addressing certificate
trust changes. Package-manager logs remain private on changed targets at
`/var/log/homelab-maintenance-20261022-apt.log`.

## Verification

Both split-direction replication jobs were triggered separately after Carter returned and
completed fresh successful syncs, enabled with `FailCount 0`, `State OK`. Quorum recovered without
an expected-vote override. All three pools remain healthy with zero device error counters, and
Apophis retains more than 10 GiB available memory, above its 3 GiB guardrail.

Final package audits passed on all three hosts, fourteen LXCs and four Ubuntu VMs. There are no
eligible pending apt packages or pending security packages; Ubuntu's phased packages remain
deferred normally. Refreshed metrics report reboot-required `0` on Oneill/Carter and every Ubuntu
VM, and `1` on Apophis. Prometheus reports 18/18 targets up and no firing alerts. All five recurring
backup groups remain within their 36-hour budget; the oldest is approximately 15.6 hours old.

All fourteen LXC security timers remain enrolled, and the four Ubuntu VMs retain their existing
automatic-security/no-automatic-reboot policy. Monthly scrub/trim and homelab host-health timers
remain active. Carter's stock SMART exporter timer is enabled but condition-skipped on its
NVMe-only host; its separate NVMe-capable homelab host-health service completed successfully.

## Remaining boundaries

- Activate Apophis's newly installed kernel through the runbook's independent-console procedure;
  its reboot remains out of scope for this control-node session.
- HA appliance updates and deliberate pinned application-version changes remain separate from
  this routine OS package window. Existing security-audit and restore/failure-drill work remains
  open; this maintenance does not close those findings.
- Existing OpenIPMI/unsupported guest boot-unit failures and the separate finance-dashboard's
  unhealthy baseline were observed. Actual itself passed its application checks. No unrelated
  service configuration or image/data cleanup was performed.
- The credential-bearing recovery repository and `backup-local-config.sh` were not accessed;
  that backup remains operator-only under [AGENTS.md](../../../AGENTS.md). Backup scope and
  off-site recovery decisions remain unchanged. Retain rollback snapshots pending acceptance.
