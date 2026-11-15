# Security remediation — 2026-11-15

Purpose: record the approved rollout, rollback safeguards, validation and final disposition of the
[live vulnerability findings](security-audit-2026-11-15.md). Current deployment facts belong in
[PLAN.md](../../PLAN.md).

## Completed scope

**Status: approved live rollout completed and verified on 2026-11-15.** The operator confirmed a
fresh private Actual portable ZIP, approved the concrete maintenance plan, and explicitly accepted
ByParr's remaining Firefox advisory. No host reboot, network-policy change, credential rotation or
recovery-repository access occurred. Application state and protected configuration were preserved.

| Target | Applied change | Expected interruption |
| --- | --- | --- |
| PVE hosts | `libcares2` 1.34.5-1+deb13u1 → 1.34.9-1~deb13u1, oneill → carter → apophis | No loaded c-ares consumers were found; no host reboot or unrelated package upgrade |
| DNS CT 117, then CT 111 | Technitium 15.6 → 15.6.2; validate the alternate before stopping either resolver | One resolver at a time; verify DNS/blocking before proceeding |
| VM 125 | Seerr 3.5.0 → 3.5.2; Prowlarr → 2.7.0.5723-ls168; ByParr browser/CA refresh | Brief request/indexer/solver restarts; preserve the existing Gluetun container and VPN namespace |
| VM 127 | Actual 26.10.0 → 26.11.0 | Brief Actual restart; preserve the independent finance report and Tailscale routes |
| VM 118 | Vaultwarden 1.37.4 → 1.37.5 security release | Brief vault-server restart; retain account/configuration and encrypted recovery paths |
| VM 100 | System bubblewrap 0.9.0 → reviewed local 0.13.1 package | No relay restart or sandbox-policy change; verify system-helper behavior afterward |

The deployed stable ByParr 3.1.1 image removes the old browser/CA findings but retains a Firefox
159.0 → 159.0.1 advisory. The maintainer `main` image and latest browser supplier build also contain Firefox 159.0.
No supported patched browser image was found. The operator explicitly chose the stable refresh and accepted this remaining high-severity
advisory. Keep it open until a supported image includes the fix; do not count the browser as fully
remediated.

Gluetun's current stable tag resolves to the already deployed digest. It is not an update and
will not be presented as remediation. Its conditional/vendor-low findings remain separately tracked.

## Artifact and readiness evidence

The exact public image candidates and before/after scan records are retained in
`/tmp/security-remediation-20261115/candidate-images.json` and `candidate-scan-summary.json`.
All five changed image candidates were scanned successfully using the same verified Grype binary
and current database as the audit. Raw critical labels drop Seerr **18→1**, Prowlarr **16→0**,
Actual **9→2**, stable ByParr **123→0**, and Vaultwarden **29→24**. Remaining labels require
applicability review; this is not a promise of zero advisories or exploits.

Technitium's official versioned portable archive is:

- URL: `https://download.technitium.com/dns/archive/15.6.2/DnsServerPortable.tar.gz`
- SHA-256: `51f2d4ebaf156a85035e820afde5e1d428f1920a37d7f0c65203fb1766917e08`
- Contents: `DnsServerApp/15.6.2` and `DnsServerCore/15.6.2.0`; no credential/config state shipped.
  Archive paths, member types and expanded size were checked before acceptance.

The local bubblewrap package uses the already reviewed unmodified static executable and included
upstream source. [The builder](../../scripts/build-bwrap-backport.py) rejects other binary/source
hashes, packages a root-owned non-setuid executable, and preserves the existing Noble namespace
sysctl file and command completions/manual. Package-manager installation preserves the separate
managed relay runtime and existing AppArmor policies. The local package is **0.13.1-0homelab1**,
not an Ubuntu vendor backport; future vendor/local security-update tracking remains necessary.

The installed package SHA-256 is
`3d818e6d4ffb1350f263b14697289a48f60c2406e2dfa55b03c26e1681df4004`.
Install with [the focused playbook](../../ansible/playbooks/provision-system-bwrap.yml), supplying
the reviewed controller-local package path/hash and explicit installation authorization. It does
not change sysctls, load profiles, alter Codex settings or restart the relay.

Preflight found healthy pools, two-vote cluster quorum, fresh scheduled encrypted PBS images
for VMs 118/127, valid existing Compose files and snapshot support for all affected guests. Neither
DNS CT has external bind mounts. Preflight free space was about 8.4 GiB on VM 125, 4.1 GiB on VM 118 and
1.5 GiB on VM 127; images were staged individually with a minimum-space guard. Do not prune Docker images or
remove previous rollback artifacts to make room without an exact separately approved deletion list.

## Rollout and recovery procedure

1. Refresh the safety checks. Retain the current package/images and create named
   `security-20261115` rollback checkpoints on each affected host/guest before its change.
   For stateful application snapshots, stop only that application long enough to obtain a
   consistent checkpoint; preserve unrelated services. Retain the operator's Actual ZIP privately.
2. Patch only c-ares on one host per deliberate step. Simulate the exact no-removal upgrade,
   refuse unrelated packages, suppress automatic service restarts and recheck loaded consumers.
   Verify the installed version and host health before proceeding to the next host.
3. Update CT 117 while CT 111 answers DNS. Stage/verify the archive, stop only `dns.service`,
   overlay application binaries/assets while preserving `/opt/technitium/dns/config`, and start
   the service. Confirm assembly version, service state, ordinary DNS resolution and blocklist
   behavior. Only then repeat for CT 111 with CT 117 as the working alternate.
4. Stage immutable accepted images without mounting application data. Keep old images. Replace
   only the selected image entries in protected existing Compose files, preserving permissions,
   configuration, secrets, data mounts and network definitions. Run Compose validation before
   targeted `up -d --no-deps`; do not reprovision guests or reset Tailscale Serve.
5. Verify Seerr/Prowlarr/ByParr readiness, loaded Node/browser/CA versions, unchanged Gluetun
   identity and namespace sharing. Check VPN health without logging public/private addresses.
   Verify Actual and Vaultwarden health and loopback-only bindings; keep the finance report route
   and container intact. No financial extraction, reconciliation, report publication or real-data
   inspection is authorized by this security rollout.
6. Install the reviewed system-helper package, compare installed bytes/version/ownership, and
   verify normal user namespace/sandbox operation with harmless fixtures. Recheck AppArmor/sysctl
   identity and the three managed relay hashes; do not disable protections to make a test pass.
7. Update only accepted image pins in local inventory, public defaults and affected docs after
   verified rollout. Recheck monitoring, DNS, backups, quorum and replication. Commit/sync the
   focused changes in each affected repository; do not invoke the credential-bearing backup script.

If an application fails, stop the rollout and retain protected diagnostics and its checkpoint.
Database rollback restores the old image **and its matching data/checkpoint**; never point an old
application at a migrated database. Obtain confirmation before a destructive checkpoint restore,
especially after a service could have accepted new writes. No automatic whole-VM rollback is implied.

## Validation and final disposition

Independent security review passed after adding remote package verification, complete dependency
notices and monthly local-package maintenance guidance. The operator approved the recorded rollout
and accepted the remaining Firefox risk before any production mutation.

| Finding | Verified disposition |
| --- | --- |
| V01 finance worker | Separate repository API/core 26.11.0 aligned with the upgraded server; Handlebars 4.7.10, csv-parse 7.0.3; obsolete adm-zip override and dependency removed. Fresh npm audit **0**, **82/82** fictional regressions, native SQLite 3.54.1 in-memory check passed. Worker build now explicitly uses integrity-pinned packaged native prebuilds with scripts disabled and a build-time smoke check. Independent security/adversarial review passed. Rebuild before its next separately approved extraction; old inactive worker images were retained. No real financial records, aggregates, credentials or report contents were accessed. |
| V02 DNS | CT 117 then CT 111 upgraded to **15.6.2**, each with a stopped-service snapshot. Config fingerprints matched across the code overlay. Both services active; ordinary DNS answered and the existing public advertising-domain probe returned NXDOMAIN. |
| V05 host c-ares | **1.34.9-1~deb13u1** installed on Oneill, Carter, Apophis in that order. Exact simulations/installations changed only libcares2. No loaded consumers before/after, healthy pools, quorum retained; no reboot. |
| V06 ByParr | **3.1.1**, Firefox **159.0**, certifi **2026.10.23** verified live; local `/health` and `/` returned 200. Old browser/CA versions replaced. **CVE-2026-120572 remains open with explicit operator risk acceptance**; fix floor Firefox 159.0.1. |
| V07 application runtimes | Live immutable digests match the scanned candidates: Seerr **3.5.2** (Node **22.23.5**), Prowlarr **2.7.0.5723-ls168**, Actual **26.11.0** (Node **24.22.1**), Vaultwarden **1.37.5** / Web Vault **2026.10.1**. Seerr status, Prowlarr ping, Actual root and Vaultwarden alive/root all return 200. Original Gluetun ID and both shared-network references are unchanged. Actual/Vaultwarden remain loopback-bound; Tailscale Serve hashes and unrelated container IDs are unchanged. Conditional image findings remain as described below. |
| V08 system helper | Package **0.13.1-0homelab1** installed through the focused Ansible playbook; exact root-owned non-setuid executable verified. Harmless normal-user fixtures prove outside writes fail, scratch writes succeed, no network routes and zero effective capabilities. Sysctls/AppArmor files and all managed relay binaries match their previous hashes; relay stays active. No paid/native Codex turn was needed or claimed. |
| V03 / V04 | Existing credential-recovery/history and internal-trust decisions remain open. This rollout did not rotate secrets, rewrite history, enable host firewalls or redesign authentication. |

The five changed running image digests match the candidates scanned before rollout. Remaining raw
scanner labels are not all exploitable: Actual glibc `%mc` issues require the specialized vulnerable
input path; some Vaultwarden matches describe curl features or MariaDB server behavior rather than
the shipped client library. Gluetun has no newer stable digest; its conditional Go/OpenSSL findings
remain. Neither old unused images nor rollback artifacts were deleted. A scan reduction is not a
claim that every runtime, advisory or attack path is clear. Actual's Node 24.22.1 also predates the
[November 11 Node security release](https://nodejs.org/en/blog/release/v24.22.3); review its HTTP/2,
TLS-server and other prerequisites separately from this supplier-image update.

Retained checkpoints: `security-20261115` for CTs 111/117 and VMs 100/118/125/127, plus each PVE
root dataset at `@security-20261115`. Restoring any stateful checkpoint still requires explicit
confirmation because it can discard writes accepted after the upgrade.

Post-stage free space is about **4.0 GiB** on VM 125, **3.7 GiB** on VM 118 and **983 MiB** on
VM 127. VM 127 remains tight; review the exact unused image list before any separately approved
cleanup. The finance-dashboard container's existing unhealthy Docker status was present before
this rollout; its identity, routes and networkless configuration were preserved. No report data
was read to investigate that unrelated status.

Final checks passed: **10/10** security-provisioning tests, the seven-pin Renovate parser,
Actual/Seerr/media deployment contracts, correct/incorrect artifact packaging fixtures, Ansible
syntax and whitespace checks. Both public source exports passed the secret scan. Finance passed
independent security/adversarial review, **82/82** fictional regressions, repository privacy checks
and the native in-memory fixture. No browser/UI or real-budget acceptance was claimed.

Final host checks report all pools healthy, cluster quorum on both nodes, all expected running
guests still running, and both replication jobs with zero failures. Prometheus and Alertmanager
ready, **18/18** scrapes up and **no pending or firing alerts** after the refreshed maintenance
metrics were scraped. Maintenance metrics were refreshed on each host after patching.
Vaultwarden and ByParr Docker health are both **healthy**. ByParr's initial starting status cleared
on its first normal 15-minute probe; direct local health had already returned HTTP 200.
