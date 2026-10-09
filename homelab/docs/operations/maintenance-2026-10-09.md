# Maintenance record — 2026-10-09

Purpose: record the authorised maintenance window, verification evidence, rollback artifacts, and remaining operator work. Current placement and versions are owned by [PLAN.md](../../PLAN.md).

## Scope and safeguards

The operator authorised routine fleet maintenance and explicitly excluded Apophis's reboot. Host updates ran separately in the runbook order, Oneill → Carter → Apophis; recovery was checked between hosts. Primary and secondary DNS were checked before host disruption. CT 126's independent Tailscale router was online, cluster quorum and both replication jobs were healthy, and existing PBS/native HA backups were fresh.

No guests were provisioned, no firewall or Tailscale policy was changed, and the cold management and synthetic HA VMs remained stopped. Existing security-only automatic patching and deliberate-reboot policies were preserved. New storage scrubs, trims, firmware changes, destructive recovery operations, and lifecycle migrations were not triggered.

## Completed changes

| Target | Maintenance and verification |
| --- | --- |
| Oneill | PVE packages updated; rebooted into the newest installed kernel. All seven guests autostarted. DNS, PBS, Prometheus, Grafana, and independent Tailscale routing recovered. |
| Carter | PVE packages updated; controlled warm reboot succeeded. Quorum returned; normal guests autostarted while VMs 128/201 remained stopped. DNS, Minecraft, Vaultwarden, Actual, and replication passed checks. |
| Apophis | PVE packages updated and maintenance metrics refreshed. Reboot explicitly skipped; newest installed kernel remains pending. ZFS, quorum, routing, and normal guests remained healthy. |
| Running apt containers | Refreshed and reviewed all 14 guests. Updated Grafana to 13.2.3, both Tailscale routers to 1.104.1, and Minecraft's Ubuntu packages. Remaining guests were current apart from the explicitly deferred Jellyfin migration. All 14 remained enrolled in security patching. |
| Ubuntu VMs | Applied remaining packages on VMs 100/118/125/127. Actual required and completed a kernel reboot; the other VMs did not require reboot. Docker runtime updates preserved the application services. |
| Vaultwarden / Actual | Deployed reviewed stable releases 1.37.4 and 26.10.0 through the existing hardened Compose services. HTTP/runtime checks and Tailscale backend checks passed; image pins were aligned in live inventory and public defaults. |
| Media applications | Sonarr 4.0.20.3014, Radarr 6.4.4.10685, Seerr 3.5.0, and Prowlarr 2.6.5.5623-ls163 verified live. Gluetun v3.41.3 and ByParr 3.0.4 were resolved from release tags and deployed by immutable digest. VPN-dependent containers were recreated together; egress remained distinct from home WAN. |
| Radarr rebuild contract | Verified the official archive SHA-256 and matched its `Radarr.dll` to the live binary before updating version/URL/checksum pins and the provisioning marker. Updated the existing Radarr/Prowlarr regression fixture. The Renovate fixture was also corrected to include the pre-existing Node companion image annotation; detection now covers all seven existing pins, without enabling the companion. |
| DNS applications | Updated secondary CT 117, verified it, then updated primary CT 111. Both Technitium 15.6 instances passed direct normal-resolution and blocklist/NXDOMAIN probes. Existing configuration was preserved. |
| Home Assistant | Core 2026.10.0, Zigbee2MQTT 2.14.2-1, Studio Code Server 7.2.0, BOM v1.3.9, SpotifyPlus v1.0.224, and visionOS theme 4.2.2 verified installed with update state off. HAOS and Supervisor were already current. |

Release changes were reviewed against primary vendor sources before deployment: [Vaultwarden](https://github.com/dani-garcia/vaultwarden/releases/tag/1.37.4), [Actual](https://actualbudget.org/blog/release-26.10.0/), [Seerr](https://github.com/seerr-team/seerr/releases/tag/v3.5.0), [Sonarr](https://github.com/Sonarr/Sonarr/releases/tag/v4.0.20.3014), [Radarr](https://github.com/Radarr/Radarr/releases/tag/v6.4.4.10685), [Prowlarr](https://github.com/Prowlarr/Prowlarr/releases/tag/v2.6.5.5623), [Technitium](https://github.com/TechnitiumSoftware/DnsServer/releases/tag/v15.6.0), and [HA Core](https://www.home-assistant.io/blog/2026/10/07/release-202610/). The loaded HA integrations intersected the Core breaking-change list only at MQTT; its documented automation behavior remains supported.

## Verification and rollback

- HA Core API and MQTT loaded successfully, and the Zigbee bridge connection state was on. Sonarr/Radarr retained media-directory write access, qBittorrent still exited through its VPN, and Apophis retained more than 8 GiB available memory at the final sample.
- All three pools remained healthy, with zero read/write/checksum counters, no known data errors, no NVMe media errors, and no collector-reported kernel hardware events. Monthly scrub/trim and host-health timers remained active.
- Backup freshness was checked before maintenance. A fresh pre-update HA native backup landed on Oneill and its metadata proved `type=partial`, `protected=true`.
- Retained `maintenance-20261009` Proxmox snapshots for CTs 110/111/117/126/129 and VMs 100/118/125/127/200. VM 200's filesystem freeze is disabled, so its snapshot supplements the verified native backup rather than replacing it.
- Monitoring's bind mount prevented a normal CT snapshot. Prometheus/Grafana were briefly quiesced for coordinated ZFS snapshots of `rpool/data/subvol-114-disk-0` and `rpool/data/monitoring-tsdb`, named `maintenance-20261009`.
- Sonarr/Radarr were individually quiesced for matching root-filesystem ZFS snapshots. The shared USB media was not included and its existing backup decision was unchanged.
- ByParr's initial 10-second readiness probe timed out. Its released `/health` endpoint starts a browser and requests an external page; a measured probe returned HTTP 200 in about 23 seconds and passed its actual 30-second Docker timeout. Final Docker health was healthy. No application workaround or readiness configuration change was needed.
- Studio Code Server's request exceeded the client timeout, and Core's update closed the API connection during restart. Observed installed versions and cleared update states subsequently proved both completed; neither action was retriggered blindly.
- Fresh post-maintenance encrypted PBS images for VMs 100/118/127 succeeded. A second protected partial HA native backup landed after the Core update. Minecraft's post-update backup succeeded after correcting the launcher's temporary-file mask: the first restrictive umask blocked its unprivileged backup client from reading the temporary guest configuration. The retry used Proxmox's normal mask while its log stayed private. CT 129 returned running with its Minecraft service active/enabled, and the new PBS restore point was visible.

## Repository validation

The media-version regression and Renovate image-detection checks passed; the public YAML parsed with the expected immutable/versioned pins. The media-version fixture was updated after observing its stale-pin failure. The Renovate failure was traced to the existing Node annotation being absent from the original expected list.

The native Claude `/security-review` command could not run because its CLI was unauthenticated. One bounded independent reviewer instead reviewed the public configuration/test diff and rollback record, finding no material introduced security issue. The reviewer had no host, credential, ignored-inventory, or private-repository access and relied on the coordinator's runtime/provenance evidence.

## Remaining work and boundaries

- Apophis reboot is operator work from the independent console/recovery path. Its new kernel is installed. The early runbook summary and detailed recovery procedure conflict about when to lower Carter's expected votes. Resolve that wording with the operator before this separate reboot; no quorum override was performed during this window.
- Jellyfin's apt preview offered 12.2 and replaced FFmpeg 7 with FFmpeg 8. The documented major-migration review remains outstanding; no Jellyfin packages were changed. Its four pending packages remain visible deliberately.
- Ubuntu's two Open-iSCSI packages remained deferred by normal phased rollout; phasing was not overridden.
- Minecraft's BDS release pin was preserved: protocol/client acceptance is a separate deliberate update, not a blind server bump.
- The pre-existing separate `finance-dashboard` container on VM 127 remained unhealthy after its host/runtime maintenance. Actual itself passed. This application's independent repository and data were not changed.
- Vaultwarden's pre-existing OpenIPMI failure and monitoring's unsupported OpenIPMI/NVMe-oF boot units were observed; application health was checked separately. No unrelated unit cleanup was performed.
- `backup-local-config.sh` was not run: it accesses the credential-bearing `homelab-private` repository, which [AGENTS.md](../../../AGENTS.md) prohibits agents from accessing. This remains an operator-only task. No off-site backup or restore-drill claim is made.
- Rollback snapshots were retained. Review them after operator acceptance; do not remove them as part of an unreviewed cleanup.
