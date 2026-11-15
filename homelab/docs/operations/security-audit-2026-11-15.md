# Estate vulnerability triage — 2026-11-15

Purpose: record current advisory matches, unresolved security risks, and the evidence needed to
confirm live exposure. [PLAN.md](../../PLAN.md) owns current infrastructure state; the
[October audit](security-audit-2026-10-11.md) owns its original findings and remediation evidence.

## Scope and evidence

The initial assessment reviewed the tracked homelab tree at `45918fa`, the separate finance-dashboard
repository at `cf88a05`, existing maintenance/security records, and current
maintainer advisories. Both repositories were initially clean. Fresh npm advisory queries used
only committed manifests/lockfiles in temporary directories, without installation or lifecycle
scripts. That initial stage did not access finance data, private inventory, credentials, private
physical-design data, or the credential-bearing recovery repository.

**Live follow-up completed after the operator confirmed access.** Verified-key SSH reached all
three PVE hosts; `pct exec` and QEMU guest-agent commands collected read-only evidence from all
14 running LXCs and four running Linux VMs. The collection covered 9,655 installed binary-package
records, selected active application versions, listeners, SSH policy, image identities and controls.
Only host/user fields from local `hosts.ini` were used internally to resolve SSH destinations;
credential-bearing group variables and the recovery repository remained untouched. No private
addresses, credential values, user financial data or device identifiers were emitted.

The verified official Apache-2.0 Grype **0.121.3** archive matched release SHA-256
`e9da18cc1429e786722e32161288103600efffd8e483c90761f90485bd1bec85` and ran from `/tmp`, without
installation on production. Its valid database was built **2026-11-14 06:19:25 UTC**. Sanitized
source-package/version manifests were matched against their Debian 12/13 or Ubuntu 24.04
distribution; six immutable public image digests observed on running containers were scanned from
the registry on the control node. Selected image findings were then checked inside existing
containers. No production data volume was scanned or copied. The custom finance image was not
exported or scanned, and stopped VMs 128/201 remained stopped.

No exploit, load test, authentication guessing, provisioning, package-list refresh, update,
restart, firewall change, or recovery operation ran against production. This is a live inventory
and vulnerability assessment with explicit applicability checks, not a penetration test or proof
that every scanner match is exploitable.

## Remediation follow-up

The operator approved and completed the [2026-11-15 remediation](security-remediation-2026-11-15.md).
That record owns the deployed versions, health checks, source fixes, rollback checkpoints and
remaining accepted/conditional findings. The sections below preserve the original assessment
baseline; their original vulnerable versions are not a claim about the post-rollout state.

## Priority findings

Priority reflects remediation urgency; upstream severity does not by itself establish a reachable
exploit in this estate.

### V01 / P1 — Finance worker retains critical and high dependency advisories

**Confirmed lockfile finding; production exploitability unproven.** The independent
`/home/simon/finance-dashboard/package-lock.json` locks Handlebars **4.7.9**, adm-zip **0.6.0**,
and csv-parse **6.2.1** through Actual API/core **26.7.0**. Fresh `npm audit` reports **five affected
package entries: one critical, one high, and three moderate**. This count includes dependency
ancestors; it is not a count of five distinct CVEs.

- [Handlebars AST type confusion](https://github.com/handlebars-lang/handlebars.js/security/advisories/GHSA-8r5x-fm3f-whwj)
  is critical (CVSS 9.8), fixed in **4.7.10**. An untrusted AST reaching compilation can execute
  JavaScript. The maintainer excludes applications that compile only template strings. The
  [own-property bypass](https://github.com/handlebars-lang/handlebars.js/security/advisories/GHSA-p8wg-vrv2-v86f)
  is also reported. Neither required application input flow was established here.
- npm reports multiple high adm-zip findings, including decompression resource exhaustion,
  preserved SUID/SGID bits and asynchronous decompression crashes; its reported affected range
  includes **0.6.0**, with **0.6.1** the patch floor. See the
  [decompression-bomb bypass](https://github.com/advisories/GHSA-rcw4-f5rp-g42v).
  Their prerequisites differ; the unprivileged, restricted worker is not evidence of a root
  escalation path. The manifest currently overrides adm-zip to the affected 0.6.0 release.
- [csv-parse prototype replacement](https://github.com/advisories/GHSA-8cw4-87c7-c6xx)
  is reported for versions below **7.0.2**; exploitability in the worker was not established.

`Dockerfile.worker` copies production dependencies and runs the manual Actual extraction worker,
which handles downloaded/decrypted budget state. The dashboard `Dockerfile` copies only its
serving closure and static assets, **without node_modules**. Its compose definition is networkless
and capability-restricted. Consequently this is a worker/build dependency finding, not demonstrated
unauthenticated RCE in the serving dashboard. Live VM 127 checks confirm the serving container is
networkless, read-only, drops all capabilities and uses no-new-privileges. Worker images are
present but no worker was running; their image contents/SBOM were not inspected or executed.

Correct dependencies in the finance repository, verify Actual API/server compatibility and worker
regressions, and rebuild the worker deliberately before the next extraction. An npm-suggested
Actual API upgrade is not sufficient while an explicit vulnerable ZIP override remains.
Do not use `npm audit fix --force` or perform a real finance extraction as a security test.

### V02 / P1 — Both live DNS installations predate a network DoS fix

**Live version match confirmed.** CTs 111 and 117 both have `DnsServerApp/15.6` and
`DnsServerCore/15.6.0.0` installed with `dns.service` active. Both listen on wildcard UDP/TCP 53
and TCP 5380. The
[maintainer changelog](https://github.com/TechnitiumSoftware/DnsServer/blob/master/CHANGELOG.md#version-1562)
records an October 17 fix in **15.6.2** for resource exhaustion caused by streams of empty UDP
packets. It also fixes zone authorization boundaries for a user holding zone-write privileges.
No vendor severity score is assigned here.

A reachable attacker could disrupt name resolution through the affected UDP receive path.
Running the same vulnerable release on both resolvers weakens redundancy against the same input.
Internet reachability was not demonstrated. November's apt maintenance does not prove this native
application was upgraded: the provisioning task installs Technitium separately and skips installation
when `dns.service` is already enabled.

Arrange a reviewed upgrade to at least 15.6.2, one resolver at a time, preserving a working alternate
and checking resolution after each change. No packet flood or denial-of-service reproduction ran.

### V03 / P1 — Credential-bearing Git backup risk remains unresolved

**Existing high-impact risk, reaffirmed from public documentation only.**
[ADR-007](../../decisions/007-local-config-backup.md#implementation-reality-and-interim-handling--2026-07-21)
and PLAN explicitly record plaintext machine credentials in private recovery Git history. The
tracked backup script still copies the secret-bearing inventory into that backup set. Private
visibility is access control rather than encryption; an authorized repository/clone compromise
could expose multiple service credentials. This review did not access the recovery repository
or establish that any credential was stolen.

Resolve the existing operator-owned encryption/separation/acceptance decision, including history
and rotation requirements. Do not delete history or rotate credentials as an implicit audit action.

### V04 / P2 — Internal trust still permits a large lateral attack surface

**Live controls reaffirm the internal-trust risk.** All three hosts report PVE firewall
`disabled/running`, with wildcard SSH and TCP 8006 listeners. Monitoring has wildcard TCP 9090/9093
listeners; anonymous local requests to Prometheus queries and Alertmanager alerts returned 200.
Grafana's anonymous user API returned 401. This rechecks listeners and local API authorization;
it does not prove admission from every VLAN or the internet. All 14 LXCs and the management/Seerr
VMs report `PasswordAuthentication yes`, while root password login is separately prohibited.
The two remaining VM SSH effective-policy checks returned no result, not evidence of hardening.
The current [Tailscale reference](../../ansible/files/tailscale-acl.hujson) still grants operators
`*:*`; subsequent port-443 rules do not narrow that grant. Live console policy remains unverified.

The accepted Minecraft offline-auth exception means any source admitted to its game port can
claim a player name; it is not a new bypass. Preserve its disabled operator privileges and verify
the restricted family grant before relying on it. The broader Home-to-IoT/camera rules and
negative VLAN/ACL tests remain open in PLAN and the October audit. Design scoped access with
tested management, cluster, monitoring and recovery paths before changing rules.

### V05 / P1 — New security update pending on every PVE host

**Installed-version and available-fix match confirmed.** All three hosts have `libcares2`
**1.34.5-1+deb13u1**, with **1.34.9-1~deb13u1** available in their existing signed security-package
metadata. The read-only apt simulations each propose this one security-labelled update.
[Debian's CVE-2026-69184 record](https://security-tracker.debian.org/tracker/CVE-2026-69184) marks
exactly the installed Trixie version vulnerable and that security version fixed. A malicious DNS
response can cause excessive decompression work and stall the c-ares resolver event loop; the
record does not claim memory corruption or data disclosure. The database also matches
**CVE-2026-33630** in the same library/update. A specific loaded host consumer was not proved.

Apply the reviewed security update on each host and identify/restart affected consumers in a
maintenance window. This finding is newer than the November 13 clean maintenance snapshot;
it is not evidence that that maintenance failed. Package metadata was not refreshed by this audit.

### V06 / P1 — ByParr's internet-facing browser and CA bundle are outdated

**Live component versions confirmed; individual exploit paths/backports unproven.** The existing
ByParr container reports Firefox **151.0** (build `20260817150018`) in its installed browser
metadata and certifi **2026.7.22** from its Python environment. Its pinned image contains the same
browser and CA bundle. Mozilla documents subsequent browser memory-safety and other security
fixes, including [the Firefox 152 security release](https://www.mozilla.org/en-US/security/advisories/mfsa2026-57/).
Windows/Android-only advisories and every later Firefox finding are not automatically applicable
to this custom Linux browser build; an independently verified downstream-backport inventory was
not available. Browsing untrusted internet content makes the browser-version gap a priority.

[certifi's critical emSign advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)
identifies **2026.10.18** as the release removing the compromised trust chain. The installed bundle
predates that removal. Exploitation requires the relevant certificate/traffic-interception path;
no MITM or observed compromise was established. Browser and Python trust stores are distinct.

Rebuild/upgrade the supported ByParr browser stack and CA bundle together, verify browser provenance
and successful indexer operation, and retain a deliberate rollback. Do not assume a host apt update
changes either component inside the image.

### V07 / P1 — Pinned application images retain vulnerable runtime dependencies

**Image/package matches confirmed; application exploitability remains conditional.** Live Seerr
runs Node **22.23.2**, Next.js **16.2.6** and Sharp **0.34.5** (libheif **1.20.2**). Actual runs
Node **24.21.0**. The ByParr image also contains a Playwright driver built on Node **24.15.0**.
[Node's October security release](https://nodejs.org/en/blog/release/v24.22.1) fixes DNS/TLS
validation issues and the Brotli decoder issue **CVE-2026-111497**; the relevant patch floors are
**22.23.4 / 24.22.1**, or newer supported security releases. The Node maintainer rates the Brotli
fix high, while the scanner imports a critical rating. Required malformed input/application flows
were not exercised.

Seerr's image also contains Handlebars **4.7.8**, so V01's compiler prerequisites matter there too.
Its Next.js version matches several critical advisories. Applicability must be kept specific:

- [The SVG optimizer advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2464-fhr4-w9xw)
  specifies glibc-based Linux; this image is Alpine/musl and its live `dangerouslyAllowSVG` is false.
- [The cache-component advisory](https://github.com/vercel/next.js/security/advisories/GHSA-673q-mjm6-r5xr)
  needs the relevant App Router cache functions; live `cacheComponents` and `useCache` are false.
- [The AVIF/libheif optimizer advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4)
  remains a priority conditional match. Optimization is enabled with four allowed remote patterns.
  The `image/webp` output setting does not establish that AVIF input is refused. No AVIF payload
  or optimizer-exploit test was sent.
- Actual's and Seerr's **proxy-addr 2.0.7** image matches require
  [particular trusted-proxy subnet configuration](https://github.com/jshttp/proxy-addr/security/advisories/GHSA-jqcg-44mw-7w3h).
  That trust configuration was not established; the package label alone does not prove spoofed
  access or bypass of Tailscale/application authentication.

Gluetun's live OpenSSL libraries are **3.5.7-r0**; its scanned base has Go **1.25.11**. Prowlarr's
live image has Brotli **1.2.0-r1** and curl/libcurl **8.22.0-r0**. These also need maintained image
rebuilds, but critical labels are not automatically estate severity. For example, OpenSSL rates
[CVE-2026-63073 and CVE-2026-75803 low](https://openssl-library.org/news/vulnerabilities/index.html),
with CMP/specialized-cipher prerequisites. Go's [HTTP/2 flow-control issue](https://pkg.go.dev/vuln/GO-2026-6612)
requires the affected server path. Curl's [FTP callback issue](https://curl.se/docs/CVE-2026-92388.html)
requires that FTP wildcard/handle-reuse flow. Those paths were not established in these services.

Update/rebuild reviewed application images and retest their functional/VPN boundaries. Do not
patch running containers in place or infer fixed base dependencies from an unchanged app tag.
The password-manager image also has package matches despite its app-level fixes; preserve the
same backup, compatibility and deliberate-rollout safeguards when updating it.

### V08 / P2 — System bubblewrap remains vulnerable outside the managed relay runtime

**Installed package confirmed.** Management VM 100 has Ubuntu bubblewrap **0.9.0-1ubuntu0.3**;
`/usr/bin/bwrap --version` reports **0.9.0**. Ubuntu still marks Noble vulnerable to
[CVE-2026-87766](https://ubuntu.com/security/CVE-2026-87766), a setup-time symlink escape that can
write outside the sandbox as its launching user. Review other sandbox callers and their selected
helper rather than treating zero pending apt updates as clearance.

The managed relay's separate patched helper and two Codex executable hashes match the reviewed
pins, all are root-owned `0755`, and the relay service is active. This audit did not rerun sandbox
escape/negative-enforcement tests or verify helper selection for unrelated Codex launchers.
The vulnerable system package does not establish a bypass of the verified managed helper.

## Conditional matches and important coverage gaps

| Component | Advisory comparison and next evidence |
| --- | --- |
| Glance | Live binary-version marker **0.8.6** falls in the [high memory-exhaustion advisory](https://github.com/glanceapp/glance/security/advisories/GHSA-r225-jhr6-68cc), fixed in **0.8.7**. Its live config has no authentication block, so the reviewed login-handler prerequisite is absent. Schedule a compatible upgrade; do not enable vulnerable authentication as a hardening step. |
| Tailscale | Both routers and VMs 118/127 report daemon/client **1.104.7**, online, with Tailscale SSH disabled and no local operator user configured. This exceeds the **1.104.4** fixes for [TS-2026-014 through 017](https://tailscale.com/security-bulletins). Serve reports no direct Unix backend; finance's socket sits behind its local relay. The **TS-2026-018** Kubernetes API proxy is absent from the documented estate. These specific matches are cleared for checked deployments; live tailnet ACL policy/failover/negative tests remain outstanding. |
| UniFi gateway/controller | Passive device metrics report UDM-family firmware **6.0.17.36539**, U7 Pro **8.7.11.19419**, and US Mini **2.1.6.762**. Network/Protect application versions and authoritative OS/console policy were not retrieved. [Vendor bulletin 067](https://community.ui.com/releases/r/security/067) is product/version-specific; these device metrics do not clear all installed applications. Its full JavaScript page and later bulletins were not retrievable. No controller credential or insecure helper session was used. |
| Home Assistant and Cloudflare | Core version alone cannot clear HAOS, Supervisor, HACS/custom integrations, companion apps, NGINX, Mosquitto, Zigbee2MQTT or Cloudflared. No fresh add-on/image inventory or Cloudflare Access, tunnel-route, HA account/MFA or external IPv4/IPv6 assessment was obtained. |
| Codex / Telegram | The [runtime research](../../apps/codex-messaging/runtime-revision-research.md#remaining-dependency-findings-are-update-risks) retains normal-runtime dependency follow-ups, including [Hickory DNS allocation amplification](https://rustsec.org/advisories/RUSTSEC-2026-0491.html), fixed in **0.26.2**, with path-specific exposure. Live root ownership/modes and all three managed runtime hashes match; V08 distinguishes the vulnerable system helper. Sandbox enforcement and unrelated launcher selection were not retested. |
| PVE, PBS and other native applications | All 21 apt-target manifests were collected and distribution-matched, but generic Debian matching does not establish Proxmox kernel/QEMU backport status or native .NET/Go/Bedrock binary clearance. PVE is **9.2.26**, all host kernels **7.0.14-28-pve**, PBS **3.4.9-2**, Jellyfin runtime **12.4.0**, qBittorrent package **5.1.0-2**, Grafana runtime **13.3.1**. Cold guests were not booted; root-MFA enrollment was not revalidated. |

## Selected matches excluded by recorded versions

These comparisons exclude particular advisories only, not all vulnerabilities or image dependencies:

- Jellyfin **12.4.0** is beyond the **12.0** fix for the
  [critical virtual-folder traversal](https://github.com/jellyfin/jellyfin/security/advisories/GHSA-6828-c7cx-hvqm)
  and [high SVG SSRF/resource exhaustion](https://github.com/jellyfin/jellyfin/security/advisories/GHSA-cf3c-8m59-2vhx).
- Vaultwarden **1.37.4** meets the patch for
  [revoked-member vault access](https://github.com/dani-garcia/vaultwarden/security/advisories/GHSA-69q9-v8p6-xvx3)
  and the [administrative 2FA-remembrance gap](https://github.com/dani-garcia/vaultwarden/security/advisories/GHSA-7jg8-8m5x-6j9r).
- Seerr **3.5.0** exceeds the **3.4.0** fix for
  [avatar-cache traversal/RCE](https://github.com/seerr-team/seerr/security/advisories/GHSA-mc6w-69r3-62h8)
  and meets the **3.5.0** fix for [notification-credential disclosure](https://github.com/seerr-team/seerr/security/advisories/GHSA-8j73-j6rc-q8xh).
- Sonarr **4.0.20.3014** exceeds the stable **4.0.16.2944** fix for
  [authentication bypass](https://github.com/Sonarr/Sonarr/security/advisories/GHSA-h5qx-5hjf-7c9r).
  Its [separate traversal advisory](https://github.com/Sonarr/Sonarr/security/advisories/GHSA-h393-v5hm-6h8f)
  also specifies Windows as the affected platform; this deployment is Linux.
- Grafana **13.3.1** exceeds the listed fix floors for
  [folder-move privilege escalation](https://grafana.com/security/security-advisories/cve-2026-111000/)
  and [alerting-contact credential disclosure](https://grafana.com/security/security-advisories/cve-2026-100105/).

## Checks performed and next steps

| Check | Result |
| --- | --- |
| Insights committed lockfile, fresh npm audit | **0 affected package entries**, 71 total dependencies reported. The October Handlebars correction remains present. Insights remains disabled per PLAN. |
| Finance committed lockfile, fresh npm audit | **5 affected package entries**, 76 total dependencies reported; V01 above. No installation, extraction or finance publication ran. |
| Homelab full tracked-tree privacy check | **Passed**, including required Gitleaks. Ignored inputs were excluded; no history-wide or private-repository clearance is claimed. |
| Security-provisioning regression fixtures | **10/10 passed**: secret-output suppression, strict SSH trust, firewall failure and TLS/hosts behavior. These are local fixtures rather than live control revalidation. |
| Codex Telegram relay regressions | **40/40 passed** with permitted local loopback sockets and synthetic HTTP/native peers. No production Telegram/account operation or real model turn ran. |
| Live coverage | **3 hosts + 14 LXCs + 4 Linux VMs**, all reached. Distribution-specific source-package scans completed for all three OS releases; six public image digests scanned successfully. |
| qBittorrent passive controls | Torrent, nftables and WireGuard units active; torrent service requires nftables; loaded input/forward/output policies are **drop**. No tunnel-loss, firewall-removal or egress interruption test ran. |
| Monitoring and login boundaries | **18 targets up** from the anonymous Prometheus query; Alertmanager has zero active alerts; Grafana user API requires authentication. No login/password challenge or brute-force test ran. |

### Image scan evidence and interpretation

The following are **raw scanner match records before applicability review**, including duplicate
library artifacts and cross-platform or conditional advisories. They are not counts of exploitable
critical incidents. Full JSON results are retained in the temporary scanner directory recorded
in `/tmp/estate-grype-path`; sanitized host/guest and runtime evidence remains in
`/tmp/estate-audit-live-evidence.json`, `/tmp/estate-controls-evidence.json`, and
`/tmp/estate-image-runtime-evidence.json`. These temporary files are not the durable findings record.

| Running image | Critical labels | High labels | Immutable digest scanned |
| --- | ---: | ---: | --- |
| Prowlarr | 16 | 53 | `lscr.io/linuxserver/prowlarr@sha256:f9151e5bc1025c6d0a630d503210cdcb6bb55a7cc098562609d96a408d838902` |
| ByParr | 123 | 293 | `ghcr.io/thephaseless/byparr@sha256:874f719518f617d03a60e03411fc5d090647e1a877041e81f8dc965927c7deb6` |
| Gluetun | 6 | 55 | `qmcgaw/gluetun@sha256:fa19cc76b2af13d57a8d3dc3066f2ada061b1c761b8aecf989b3877c0486e027` |
| Seerr | 18 | 167 | `ghcr.io/seerr-team/seerr@sha256:27602401178d54f1964442287b9f23f67a3fa2252645ee8065839ea1c3f69e45` |
| Vaultwarden | 29 | 199 | `vaultwarden/server@sha256:efb3cde962015fcc036b2ea625242248611943b27212ebf4392841fb30fad055` |
| Actual | 9 | 86 | `actualbudget/actual-server@sha256:24645e971da6bb1a1f953d6859e307a0b29be1e8b4130a35b3220c209b5b860c` |

Distribution/source-package matching also needs runtime interpretation:

- Old Ubuntu kernel packages remain installed, but all four running Ubuntu VMs use
  **6.8.0-149-generic**. Matches against retained **6.8.0-147** packages are not evidence that those
  old kernels are running. No kernel or rollback artifact was removed.
- CT 121 retains older Debian-12-named ICU, Perl, LDAP and apt libraries after its Debian 13
  migration, alongside current replacements. Current apt and Perl executables are updated. These
  residual packages need dependency/loaded-library review before deliberate cleanup; their source
  package matches must not be attributed to all three updated PVE hosts.
- Several Debian matches have postponed/no-DSA dispositions. For example,
  [CVE-2026-60002](https://security-tracker.debian.org/tracker/CVE-2026-60002) is an SSH **client**
  re-exchange issue, not a demonstrated remote sshd RCE; Debian calls it minor.
- The portal's nginx package matches three critical conditional advisories, but its live parsed
  configuration has no alias/rewrite/request-filename combination, regex map, enabled SSI or AIO.
  The reviewed [alias/rewrite](https://security-tracker.debian.org/tracker/CVE-2026-15176),
  [regex-map](https://security-tracker.debian.org/tracker/CVE-2026-93479), and
  [SSI/AIO](https://security-tracker.debian.org/tracker/CVE-2026-97205) trigger configurations are
  absent. This does not clear HA's separate NGINX add-on, which was not inspected.

Prioritize the DNS update, ByParr browser/CA rebuild, available host c-ares update and reviewed
application-image refreshes. Correct V01's worker dependencies in the finance repository before
the next extraction, and retain V03 as the existing operator decision. HA/UniFi application
inventories, authoritative tailnet policy, full image-match applicability, other native sandbox
callers and external admission remain follow-ups. External exposure, negative ACL/VLAN tests,
VPN loss and restore drills retain the prerequisites in the October audit. No finding was
remediated by this assessment.
