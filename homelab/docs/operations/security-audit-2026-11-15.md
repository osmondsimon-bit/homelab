# Estate vulnerability triage — 2026-11-15

Purpose: record current advisory matches, unresolved security risks, and the evidence needed to
confirm live exposure. [PLAN.md](../../PLAN.md) owns current infrastructure state; the
[October audit](security-audit-2026-10-11.md) owns its original findings and remediation evidence.

## Scope and evidence

This assessment reviewed the tracked homelab tree at `45918fa`, the separate finance-dashboard
repository at `cf88a05`, existing maintenance/security records, and current
maintainer advisories. Both repositories were initially clean. Fresh npm advisory queries used
only committed manifests/lockfiles in temporary directories, without installation or lifecycle
scripts. No finance data, private inventory, credentials, private physical-design data, or
credential-bearing recovery repository was read.

**This is repository/advisory triage, not a fresh live estate scan.** Tailscale access was not
confirmed for this session; this execution environment has no local Tailscale client. The operator
was asked to confirm access, and no remote SSH or private service probes were attempted while
that answer remained pending. Installed versions below are dated documentary evidence, not new
runtime measurements. No exploit, load test, authentication guessing, provisioning, update,
restart, firewall change, or recovery operation ran against production.

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
unauthenticated RCE in the serving dashboard. The deployed worker image/SBOM was not inspected.

Correct dependencies in the finance repository, verify Actual API/server compatibility and worker
regressions, and rebuild the worker deliberately before the next extraction. An npm-suggested
Actual API upgrade is not sufficient while an explicit vulnerable ZIP override remains.
Do not use `npm audit fix --force` or perform a real finance extraction as a security test.

### V02 / P1 — Both documented DNS versions predate a network DoS fix

**Likely version match, requiring live confirmation.** PLAN records Technitium **15.6** on CTs
111 and 117, last verified October 9. The
[maintainer changelog](https://github.com/TechnitiumSoftware/DnsServer/blob/master/CHANGELOG.md#version-1562)
records an October 17 fix in **15.6.2** for resource exhaustion caused by streams of empty UDP
packets. It also fixes zone authorization boundaries for a user holding zone-write privileges.
No vendor severity score is assigned here.

A reachable attacker could disrupt name resolution if the recorded releases remain installed.
Running the same vulnerable release on both resolvers weakens redundancy against the same input.
Internet reachability was not demonstrated. November's apt maintenance does not prove this native
application was upgraded: the provisioning task installs Technitium separately and skips installation
when `dns.service` is already enabled.

Confirm each running DNS version and reachable transports, then arrange a reviewed upgrade to at
least 15.6.2, one resolver at a time, preserving a working alternate and checking resolution after
each change. Do not send the resource-exhaustion input to production.

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

**Previously observed runtime exposure; current reference policy confirmed.** October S08 records
disabled PVE host firewalls, broadly listening management/exporter services, and anonymous
Prometheus/Alertmanager reads on the management LAN. Those runtime observations were not repeated.
The current [Tailscale reference](../../ansible/files/tailscale-acl.hujson) still grants operators
`*:*`; subsequent port-443 rules do not narrow that grant. Live console policy remains unverified.

The accepted Minecraft offline-auth exception means any source admitted to its game port can
claim a player name; it is not a new bypass. Preserve its disabled operator privileges and verify
the restricted family grant before relying on it. The broader Home-to-IoT/camera rules and
negative VLAN/ACL tests remain open in PLAN and the October audit. Design scoped access with
tested management, cluster, monitoring and recovery paths before changing rules.

## Conditional matches and important coverage gaps

| Component | Advisory comparison and next evidence |
| --- | --- |
| Glance | Recorded **0.8.6** falls in the [high memory-exhaustion advisory](https://github.com/glanceapp/glance/security/advisories/GHSA-r225-jhr6-68cc), fixed in **0.8.7**. It requires authentication to be enabled. The tracked template has no authentication configuration, so the necessary deployment condition is not established. Verify actual config/version and schedule a compatible upgrade; do not enable vulnerable authentication as a hardening step. |
| Tailscale | Versions and Serve backend/operator permissions were not freshly collected. [TS-2026-014 through 017](https://tailscale.com/security-bulletins) fix privileged Unix-socket forwarding/backend access and SSH/Serve issues in **1.104.4**. Finance uses a Unix-socket backend, making the backend-write/local-operator prerequisite particularly relevant. The November 13 update record is encouraging but omits exact versions. Confirm running daemon versions and configuration; this is not a confirmed unpatched deployment. The newer **TS-2026-018** concerns a Kubernetes API proxy, which is absent from the documented estate; it does not make every subnet router vulnerable. |
| UniFi gateway/controller | Current UniFi OS, Network, Protect and device firmware versions were unavailable. [Vendor bulletin 067](https://community.ui.com/releases/r/security/067) includes critical authenticated command/privilege issues across specified products. Determine exact model, installed applications and versions before matching. Its indexed advisory text was readable, but the full JavaScript bulletin page and later bulletin pages were not retrievable; this remains incomplete coverage, not a finding that the gateway is vulnerable. |
| Home Assistant and Cloudflare | Core version alone cannot clear HAOS, Supervisor, HACS/custom integrations, companion apps, NGINX, Mosquitto, Zigbee2MQTT or Cloudflared. No fresh add-on/image inventory or Cloudflare Access, tunnel-route, HA account/MFA or external IPv4/IPv6 assessment was obtained. |
| Codex / Telegram | The [runtime research](../../apps/codex-messaging/runtime-revision-research.md#remaining-dependency-findings-are-update-risks) already records unresolved normal-runtime dependency matches. [Hickory DNS allocation amplification](https://rustsec.org/advisories/RUSTSEC-2026-0491.html), fixed in **0.26.2**, remains an upstream follow-up with path-specific exposure. The documented patched helper **0.13.1** exceeds the **0.12.0** fix for [CVE-2026-87766](https://github.com/containers/bubblewrap/security/advisories/GHSA-pxhw-h44j-8pfx). This applies to the verified selected relay helper; it does not clear other Codex launchers or vulnerable bundled fallbacks. Neither runtime integrity nor sandbox commissioning was repeated here. |
| PVE, PBS, Linux packages and remaining images/binaries | November 13 signed-package maintenance is historical evidence, not a fresh CVE/SBOM scan. No image layers, firmware inventory, current package manifests or vendor-backport matching were collected for all guests. Radarr, Prowlarr, qBittorrent, Gluetun, ByParr, PBS, Samba, exporters, nginx and Minecraft are not comprehensively cleared. Cold guests were not booted. |

## Selected matches excluded by recorded versions

These comparisons exclude particular advisories only, not all vulnerabilities in a product:

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

First complete V01's worker dependency correction in its own repository and confirm V02's live
resolver versions. In parallel, retain V03 as the existing operator decision. After access is
confirmed, collect sanitized running package/application versions and image digests across the
three hosts and running guests, plus UniFi/HA appliance inventories; compare exact versions and
vendor backports. Record unknowns rather than treating missing versions or zero pending apt
updates as security clearance. External exposure, negative ACL/VLAN tests, VPN loss and restore
drills retain the prerequisites in the October audit. No finding was remediated by this triage.
