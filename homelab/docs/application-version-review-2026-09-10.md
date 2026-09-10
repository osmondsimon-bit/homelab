# Application version review — 2026-09-10

Purpose: inventory the application, runtime, container, operating-system, and tooling versions
managed by the public homelab repository, compare explicit pins with first-party upstream releases,
and recommend deliberate updates. This is a repository review only: it did not inspect live hosts,
the gitignored real inventory, `physical_infra/`, or `homelab-private`.

## Executive recommendation

Schedule one tested application-update window for **Vaultwarden, Actual Budget and its companion,
Seerr, Glance, Node 24, and D2**. Vaultwarden and Glance have the clearest urgency because their
newer releases contain client-compatibility and security-relevant fixes. Keep Home Assistant OS,
Gitleaks, Pico CSS, and the supported OS major releases as they are. Do not update opaque container
digests blindly: let Renovate resolve new digests, identify the represented release, review its
notes, and deploy one service at a time.

The repository does not pin or record deployed versions for several applications. Add a version
capture step before calling those services current. In particular, Sonarr, Radarr, Technitium,
Tailscale, Jellyfin, qBittorrent, the monitoring stack, PBS, and related exporters are installed
from `latest`, vendor scripts, or unversioned apt/pip sources.

## Exact application and container pins

| Component | Repository value | First-party current release | Recommendation |
| --- | --- | --- | --- |
| Home Assistant OS synthetic VM | `18.2` plus image SHA-256 | `18.2` | **Keep.** This is the current stable OVA version and upstream recommends it; the release includes security-bearing Buildroot updates and Docker 29.6.2. Preserve the checksum gate. [HAOS releases](https://github.com/home-assistant/operating-system/releases) · [stable channel](https://github.com/home-assistant/version/blob/master/stable.json) |
| Minecraft Bedrock Dedicated Server | `1.26.45.1` plus URL and SHA-256 | Not independently enumerable through a stable first-party release API | **Verify before deployment, otherwise keep.** The pin is reproducible, but Microsoft's download page is a mutable latest-download surface. At each attended upgrade, resolve the current Linux URL, verify the version and checksum, stage it, then run the existing compatibility checks. [official Bedrock server download](https://www.minecraft.net/en-us/download/server/bedrock) |
| Vaultwarden | `vaultwarden/server:1.36.0` | `1.37.2` | **Update promptly to 1.37.2.** Upstream says 1.37.2 is required for clients 2026.8.0 and newer. Take/verify the existing backup first, update the exact tag, then test login, sync, attachments, admin access, and current clients. [Vaultwarden releases](https://github.com/dani-garcia/vaultwarden/releases) |
| Actual Budget server | `actualbudget/actual-server:26.7.0` | `26.9.0` | **Update to 26.9.0**, coordinating the companion's `@actual-app/api` at the same version. Back up first and test sync, import/export, and the AI snapshot path. [Actual releases](https://github.com/actualbudget/actual/releases/tag/v26.9.0) |
| Glance | `v0.8.5` | `v0.8.6` | **Update to v0.8.6.** It is a patch release, but includes a fix for spoofed `X-Forwarded-For` bypassing auth rate limiting. Re-run the dashboard tests and check custom API, release, and service widgets. [Glance v0.8.6](https://github.com/glanceapp/glance/releases/tag/v0.8.6) |
| Seerr | `ghcr.io/seerr-team/seerr:v3.3.0` | `v3.4.1` | **Update to v3.4.1** after reading the 3.4 migration notes and backing up its config/database. The installed 3.3.0 is newer than the earlier security-fix releases, but is still behind the current stable patch. Test Jellyfin authentication, requests, and Sonarr/Radarr connections. [Seerr releases](https://github.com/seerr-team/seerr/releases) |
| D2 diagram renderer | `v0.6.9` | `v0.9.0` | **Update in a separate compatibility change.** This spans multiple minor releases in a pre-1.0 project. Render the full portal fixture set and compare output before deployment. [D2 v0.9.0](https://github.com/d2lang/d2/releases/tag/v0.9.0) |
| Gluetun container | `latest` locked to `sha256:d180…7321b` | Digest does not expose a semantic version in repository text | **Review the next Renovate digest proposal**, confirm upstream release/image provenance and architecture, then test VPN reachability, DNS, killswitch, and port publishing. Do not replace the digest with a floating tag. [Gluetun releases](https://github.com/qdm12/gluetun/releases) |
| LinuxServer Prowlarr container | `latest` locked to `sha256:3950…ae9f` | Digest does not expose a semantic version in repository text; upstream application release is `v2.5.2.5491` | **Review through Renovate.** Confirm the image's embedded Prowlarr version after pull, then test indexers and Gluetun networking. [Prowlarr releases](https://github.com/Prowlarr/Prowlarr/releases/tag/v2.5.2.5491) · [LinuxServer image](https://github.com/linuxserver/docker-prowlarr) |
| ByParr container | `latest` locked to `sha256:01a4…cfb0` | Upstream application release `v3.0.4` | **Review through Renovate** and deploy only if the service is enabled/needed. Record the application version represented by the accepted digest. [ByParr releases](https://github.com/ThePhaseless/Byparr/releases/tag/v3.0.4) |

Source of managed values: `ansible/inventory/group_vars/all.yml.example` lines 41–43, 67–69,
128–129, 146–147, 242, 319, and 395–405. Renovate detects the six annotated Docker declarations
and deliberately does not automerge them (`renovate.json`).

## Actual Insights runtime and dependencies

| Item | Repository value | Current first-party/registry value | Recommendation |
| --- | --- | --- | --- |
| Node base image | `node:24.18.0-bookworm-slim`; engine `>=24.15 <25` | latest Node 24 is `24.21.0`; Node 24 is supported LTS | **Update within Node 24 to `24.21.0-bookworm-slim`** and run the app tests. Stay on LTS 24 rather than moving production to Current 26. [Node release index](https://nodejs.org/dist/index.json) · [release policy](https://nodejs.org/en/about/previous-releases) |
| `@actual-app/api` | `26.7.0` | `26.9.0` | **Update with the Actual server to 26.9.0**, regenerate the lockfile, and test sync/snapshot behavior. [npm registry](https://www.npmjs.com/package/@actual-app/api) |
| `@picocss/pico` | `2.1.1` | `2.1.1` | **Keep.** [npm registry](https://www.npmjs.com/package/@picocss/pico) |
| OpenAI JavaScript SDK | `7.3.0` | `7.13.0` | **Update within major 7** and run request, structured-output, error, and timeout tests. Review changelogs because the companion handles sensitive derived financial data. [official SDK releases](https://github.com/openai/openai-node/releases) |
| `adm-zip` override | `0.6.0` | `0.6.0` | **Keep** until the upstream dependency no longer needs the override. [npm registry](https://www.npmjs.com/package/adm-zip) |
| `better-sqlite3` install-script allowance | `12.11.1` | `13.0.3` | **Do not bump independently.** It is transitive through Actual's API and major-version compatibility must come from that dependency tree. Reassess the narrowly allowed install script after regenerating the lockfile. [npm registry](https://www.npmjs.com/package/better-sqlite3) |
| Application package | `0.1.0` | Local package, no upstream release | **Keep** unless the project adopts its own release process. |
| OpenAI model identifier | `gpt-5.6-terra` | Runtime configuration, not an application package | Review separately against the supported model catalogue and cost/quality requirements; do not treat it as a software upgrade. |

Managed values are in `apps/actual-insights/package.json`, its lockfile, Dockerfile, and the Ansible
defaults. The lockfile is npm lock format 3 and should be regenerated only by the intended npm
update, not hand-edited.

## Floating or package-managed applications

These installations are managed, but no exact desired version exists in the repository. Therefore
this review can identify the current upstream release but cannot establish whether the live service
needs an update.

| Service | Repository behavior | Current upstream reference | Recommendation |
| --- | --- | --- | --- |
| Jellyfin | unversioned vendor apt package on Debian 12 | `v12.0` | Capture `dpkg-query` output and review the 12.0 migration notes before a major upgrade; keep package origin and OS compatibility explicit. [Jellyfin releases](https://github.com/jellyfin/jellyfin/releases/tag/v12.0) |
| qBittorrent | Debian 13 stable package; only major 5 is asserted | distro-managed | Record the installed package version and Debian candidate. Prefer Debian security/stable updates; do not replace it with an arbitrary upstream binary. [Debian package tracker](https://tracker.debian.org/pkg/qbittorrent) |
| Sonarr | latest GitHub asset on first install | `v4.0.19.2979` | Record installed version, compare, back up config/database, then use Sonarr's supported updater or a deliberate pin. [Sonarr release](https://github.com/Sonarr/Sonarr/releases/tag/v4.0.19.2979) |
| Radarr | master updatefile on first install | `v6.3.0.10514` | Same approach as Sonarr; a `master` URL is not a reproducible desired state. [Radarr release](https://github.com/Radarr/Radarr/releases/tag/v6.3.0.10514) |
| Technitium DNS | unversioned vendor install script | `v15.4.0` | Inventory both resolver versions and upgrade one at a time, proving DNS before touching the second. Consider pinning an artifact and checksum. [Technitium release](https://github.com/TechnitiumSoftware/DnsServer/releases/tag/v15.4.0) |
| Tailscale | unversioned vendor install script | `v1.102.3` | Inventory both routers and update sequentially so one subnet router remains available. Retest advertised routes and ACL reachability. [Tailscale release](https://github.com/tailscale/tailscale/releases/tag/v1.102.3) |
| Prometheus | distro package | `v3.14.0` upstream | Compare installed and apt candidate, not just upstream, because the repository intentionally consumes distro packages. [Prometheus release](https://github.com/prometheus/prometheus/releases/tag/v3.14.0) |
| Grafana | distro/vendor apt package | `v13.2.1` upstream | Capture installed/candidate versions and review major-version migration notes before updating dashboards and plugins. [Grafana release](https://github.com/grafana/grafana/releases/tag/v13.2.1) |
| Alertmanager, blackbox exporter, node exporter, PVE exporter, unpoller, PBS | unversioned apt/pip or latest-release installation | varies | Add their installed versions to the maintenance collector or a version audit command. Apply security updates through the configured package source; pin downloaded release artifacts where reproducibility matters. |
| Codex CLI on secondary management VM | `@openai/codex@latest` | floating | Replace `latest` with an explicitly reviewed version if rebuild reproducibility matters; otherwise record installed version after convergence. |

## OS, platform, and infrastructure constraints

| Item | Repository value | Assessment and recommendation |
| --- | --- | --- |
| General LXC and legacy Tailscale helper | Debian 12 template `12.12-1` | Debian 12 is in LTS through June 2028. **Keep for existing services**, apply LTS security updates, and plan Debian 13 migrations service by service rather than changing the shared template globally. [Debian releases](https://www.debian.org/releases/) · [Debian LTS](https://wiki.debian.org/LTS) |
| qBittorrent LXC | Debian 13 template `13.6-1`, Trixie suites | **Keep.** Debian 13 is the current stable major; refresh the appliance template when Proxmox publishes a newer point image, while still applying in-guest security updates. [Debian 13 release information](https://www.debian.org/releases/trixie/) |
| Minecraft LXC and service VMs | Ubuntu 24.04 / Noble; LXC template `24.04-2` or floating current cloud image | **Keep the 24.04 LTS major** and patch it. For reproducible rebuilds, record the resolved cloud-image serial/checksum instead of relying only on mutable `current`. Ubuntu 24.04 standard security maintenance runs through May 2029. [Ubuntu release cycle](https://ubuntu.com/about/release-cycle) · [cloud images](https://cloud-images.ubuntu.com/releases/noble/) |
| PBS and Jellyfin guest base | Debian 12 Bookworm repositories | **Keep and patch** under Debian LTS; plan migration before June 2028. |
| Terraform/OpenTofu CLI | `>= 1.6` | This is a compatibility floor, not a reproducible tool version. Define and CI-test an upper bound or a documented tested version before major upgrades. [Terraform version constraints](https://developer.hashicorp.com/terraform/language/expressions/version-constraints) |
| `bpg/proxmox` provider | `>= 0.95.0`; no committed `.terraform.lock.hcl` found | Current is `0.112.0`. **Do not jump implicitly.** Restore the documented lockfile workflow, initialize with the chosen CLI, review provider changes from 0.95 through 0.112, and commit the generated lockfile in the owning repository. [provider releases](https://github.com/bpg/terraform-provider-proxmox/releases/tag/v0.112.0) · [dependency lock file](https://developer.hashicorp.com/terraform/language/files/dependency-lock) |
| Gitleaks CI binary | `8.30.1` plus verified SHA-256 | **Keep.** It matches the current release and official Linux x64 checksum. [Gitleaks releases](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) |
| `actions/checkout` | commit SHA annotated `v4.2.2` | **Keep SHA pinning**; let dependency automation propose reviewed commit updates. A moving major tag would weaken reproducibility. [checkout releases](https://github.com/actions/checkout/releases) |

## Suggested update order

1. Capture live installed versions and backup status; this closes the evidence gap for package-managed services.
2. Update Vaultwarden to 1.37.2 and validate current clients.
3. Update Glance to 0.8.6 and run the existing dashboard test suite.
4. Update Actual server, `@actual-app/api`, Node 24, and the OpenAI SDK together; regenerate the npm lockfile and run all companion tests.
5. Update Seerr, with database/config backup and integration tests.
6. Test D2 0.9.0 against complete portal output before accepting it.
7. Review Renovate's three digest proposals independently; record the embedded application version for each accepted digest.
8. Add/version a non-mutating audit that reports installed application and package versions, and restore the Terraform provider lockfile.

## Review limits

- “Current” means the latest stable first-party release or official registry response observed on
  2026-09-10. It does not mean every upstream release is compatible with this deployment.
- Digest-only images were not reverse-mapped to a multi-architecture application version; their
  currency should be resolved by the configured Renovate workflow and verified from image metadata.
- Mutable vendor pages and distro repositories can change. Re-resolve versions and checksums at the
  start of the actual maintenance window.
- No live host, private address, secret, real inventory, private repository, deployment, or version
  pin was read or changed during this review.
