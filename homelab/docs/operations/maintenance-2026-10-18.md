# Maintenance record — 2026-10-18

Purpose: record authorised routine package patching and host reboots, verification, rollback artifacts, and the remaining restart work. Current infrastructure state belongs in [PLAN.md](../../PLAN.md).

## Scope and safeguards

The operator requested routine patching. Signed apt metadata was refreshed and upgrade simulations
reviewed on three Proxmox hosts, fourteen running LXCs, and four Ubuntu VMs. Package plans were
rechecked immediately before installation; upgrades used `--no-remove`, preserved existing
configuration, and retained Ubuntu's normal package-phasing behavior. Hosts were patched separately
in Oneill → Carter → Apophis order, with service, storage, guest-state, quorum and replication checks
between nodes. Ubuntu VMs were patched separately with application checks between targets.

Fresh PBS/native HA backups, both DNS resolvers, and CT 126's independent Tailscale router were
verified before proceeding. Every changed target has a retained `maintenance-20261018` rollback
snapshot: host root datasets on all three PVE nodes, VMs 100/118/125/127, CT 129, and CT 114's root
dataset. Grafana was briefly stopped for its database-consistent root snapshot; Prometheus and its
separate TSDB remained running. Snapshots supplement the established backup/rebuild decisions.

## Completed changes

| Target | Package changes and result |
| --- | --- |
| Oneill, Carter, Apophis | Installed the reviewed Debian security packages, PVE storage/QEMU-management fixes, and kernel `7.0.14-24-pve`. At the end of package installation all still ran `7.0.14-23-pve`; the subsequent approved Oneill/Carter reboots are recorded below. All host apt queues were clear. |
| Ubuntu VMs 100/118/125/127 | Applied ordinary OS packages, including the now-eligible Open-iSCSI update, AppArmor and timezone data. VM 100 also received Node.js `24.22.0`. No pending apt packages or VM reboot requirements remain. |
| Docker runtimes on VMs 118/125/127 | Updated Docker to `29.9.1` and containerd to `2.4.2`. Containers restarted during runtime maintenance; application image identities match their pre-update baselines. |
| Monitoring CT 114 | Updated Grafana from `13.2.3` to `13.2.4`. Database quick-check passed before and after, with unchanged dashboard/data-source counts; health returned HTTP 200 and anonymous `/api/user` remained HTTP 401. All seven checked monitoring services are active. |
| Minecraft CT 129 | Updated three Ubuntu OS packages. The game-server release pin was preserved and its service remains active. |
| Other running LXCs | Package previews were current apart from Jellyfin's previously deferred major migration. Its four candidate packages were left pending. |

Reviewed primary vendor patch notes: [Grafana 13.2.4](https://github.com/grafana/grafana/releases/tag/v13.2.4)
and [Docker Engine 29.9.1](https://docs.docker.com/engine/release-notes/29/#2991).

## Verification after package updates

- All three pools are healthy with zero reported read/write/checksum counters. Both cluster members
  remain quorate; replication jobs `118-0` and `200-0` are enabled, `State OK`,
  `FailCount 0`. Normal guests remain running and cold VMs 128/201 remain stopped. Apophis's final
  `MemAvailable` sample exceeded 14 GiB, above its 3 GiB guardrail.
- All nine changed targets passed `dpkg --audit` and post-update apt simulation, with no pending
  packages and no new failed units. The fourteen container security timers and four Ubuntu VM
  security timers remain enabled/active. Maintenance metrics were refreshed on all hosts and VMs.
- Vaultwarden, Actual, Seerr, Prowlarr and Grafana returned HTTP 200. Vaultwarden and Actual's
  Tailscale backends remain online. qBittorrent's three required services are active, all three
  loaded killswitch chains retain drop policies, and its IPv4 VPN egress differs from the control
  host's. Gluetun's egress also differs from its VM's ordinary egress.
- ByParr's first automatic probe ran during startup and failed to connect. Its configured interval
  is fifteen minutes; Docker still reported `starting` at the end of the package pass. A manual run of
  the unchanged configured health probe subsequently passed. Seerr and Gluetun reported healthy;
  Prowlarr remained running and its ping endpoint passed.
- Prometheus reports 18/18 targets up and no firing alerts; the pre-existing security-update alert
  cleared. All five recurring backup groups remain within their 36-hour freshness budget. Freshness
  and local snapshots do not constitute a new restore drill.

Package-manager logs are retained on each changed target at
`/var/log/homelab-maintenance-20261018-apt.log` with restrictive permissions.

## Approved reboot follow-up

The operator subsequently approved Oneill and Carter reboots. Both routers were online, the
secondary DNS resolver answered directly from mgmt-vm, backup freshness passed, and no backup or
management tasks were active at preflight. Oneill was rebooted first; its complete guest/service
recovery, primary DNS, independent router, PBS access and monitoring were verified before Carter
was rebooted. Each normal reboot returned a new boot identity and verified SSH in 50 seconds;
ordered guest startup and application readiness were checked afterward.

| Node | Verified recovery |
| --- | --- |
| Oneill | Running kernel `7.0.14-24-pve`; all seven LXCs running, with DNS, PBS proxy, Samba, all seven checked monitoring services, Glance, nginx and the independent Tailscale router active. Primary DNS answered from mgmt-vm and Apophis authenticated to PBS storage successfully. |
| Carter | Running kernel `7.0.14-24-pve`; quorum returned automatically. CTs 117/129 and VMs 118/127 running, with VMs 128/201 still stopped. Secondary DNS answered from mgmt-vm; Vaultwarden and Actual returned HTTP 200 with online Tailscale backends, and Vaultwarden's container reported healthy. Minecraft and nftables are active, with loaded input/forward drop policies. |

After Carter returned, existing jobs `118-0` Carter→Apophis and `200-0` Apophis→Carter were each
triggered once and completed fresh successful syncs, enabled with `FailCount 0`, `State OK`.
All three pools remained healthy with zero read/write/checksum counters, all normal guests
recovered, and Prometheus reported 18/18 targets up with no firing alerts. All five recurring backup
groups remained fresh. Refreshed maintenance metrics show reboot-required `0` on Oneill/Carter and
all nine of their LXC security timers enrolled.

Apophis retains its preflight boot identity and running kernel `7.0.14-23-pve`; its installed
`7.0.14-24-pve` still awaits the separate out-of-band reboot. Existing application pins, backup
scope and the accepted manual quorum model are unchanged.

## Remaining work

- Activate Apophis's new kernel through a separately approved out-of-band reboot, following the
  independent-console/recovery procedure in the runbook. Oneill and Carter's reboots are complete.
- HA Core is live at `2026.10.1`, with `2026.10.2` offered. Apply it after a fresh native backup and
  approval for its restart. HAOS `18.3` and Supervisor `2026.10.2` are current.
- Jellyfin was deferred during this fleet window; its subsequently approved migration is complete
  in the [separate Jellyfin record](maintenance-jellyfin-2026-10-18.md). Pinned application-image
  updates and Minecraft protocol/client acceptance remain separate deliberate work.
- Existing OpenIPMI/unsupported guest boot-unit failures and the separate finance-dashboard's
  unhealthy state remain unchanged. VM 127 has about 1.38 GiB free after its reviewed 74 MiB package
  download; image/data cleanup remains separately scoped.
- Rollback snapshots remain retained. The credential-bearing recovery repository and production
  local-config backup script were not accessed; backup scope and off-site recovery decisions are
  unchanged. Security-audit findings and disruptive failure/restore tests remain open.
