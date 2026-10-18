# Maintenance record — 2026-10-18

Purpose: record authorised routine package patching, verification, rollback artifacts, and the remaining restart work. Current infrastructure state belongs in [PLAN.md](../../PLAN.md).

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
| Oneill, Carter, Apophis | Installed the reviewed Debian security packages, PVE storage/QEMU-management fixes, and kernel `7.0.14-24-pve`. All still run `7.0.14-23-pve`; reboots remain pending. All host apt queues are clear. |
| Ubuntu VMs 100/118/125/127 | Applied ordinary OS packages, including the now-eligible Open-iSCSI update, AppArmor and timezone data. VM 100 also received Node.js `24.22.0`. No pending apt packages or VM reboot requirements remain. |
| Docker runtimes on VMs 118/125/127 | Updated Docker to `29.9.1` and containerd to `2.4.2`. Containers restarted during runtime maintenance; application image identities match their pre-update baselines. |
| Monitoring CT 114 | Updated Grafana from `13.2.3` to `13.2.4`. Database quick-check passed before and after, with unchanged dashboard/data-source counts; health returned HTTP 200 and anonymous `/api/user` remained HTTP 401. All seven checked monitoring services are active. |
| Minecraft CT 129 | Updated three Ubuntu OS packages. The game-server release pin was preserved and its service remains active. |
| Other running LXCs | Package previews were current apart from Jellyfin's previously deferred major migration. Its four candidate packages were left pending. |

Reviewed primary vendor patch notes: [Grafana 13.2.4](https://github.com/grafana/grafana/releases/tag/v13.2.4)
and [Docker Engine 29.9.1](https://docs.docker.com/engine/release-notes/29/#2991).

## Verification

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
  is fifteen minutes; Docker still reported `starting` at the final observation. A manual run of
  the unchanged configured health probe subsequently passed. Seerr and Gluetun reported healthy;
  Prowlarr remained running and its ping endpoint passed.
- Prometheus reports 18/18 targets up and no firing alerts; the pre-existing security-update alert
  cleared. All five recurring backup groups remain within their 36-hour freshness budget. Freshness
  and local snapshots do not constitute a new restore drill.

Package-manager logs are retained on each changed target at
`/var/log/homelab-maintenance-20261018-apt.log` with restrictive permissions.

## Remaining work

- Activate the new kernel through separately approved, controlled host reboots. Apophis remains
  subject to the independent-console/recovery procedure in the runbook. No node was rebooted here.
- HA Core is live at `2026.10.1`, with `2026.10.2` offered. Apply it after a fresh native backup and
  approval for its restart. HAOS `18.3` and Supervisor `2026.10.2` are current.
- Jellyfin's major migration, pinned application-image updates and Minecraft protocol/client
  acceptance remain separate deliberate work.
- Existing OpenIPMI/unsupported guest boot-unit failures and the separate finance-dashboard's
  unhealthy state remain unchanged. VM 127 has about 1.38 GiB free after its reviewed 74 MiB package
  download; image/data cleanup remains separately scoped.
- Rollback snapshots remain retained. The credential-bearing recovery repository and production
  local-config backup script were not accessed; backup scope and off-site recovery decisions are
  unchanged. Security-audit findings and disruptive failure/restore tests remain open.
