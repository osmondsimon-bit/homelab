# Security audit and test record — 2026-10-11

Purpose: record the security audit, reproducible checks, observed controls, prioritised findings,
and remaining validation. Current infrastructure facts remain in [PLAN.md](../../PLAN.md).

## Outcome and scope

**Baseline findings below describe the initial audit; remediation status is recorded at the end.** The safe audit covered the public repository at `6dc6ed5`, all three
Proxmox hosts, all 14 running LXCs, four running Linux VMs, monitoring, backup freshness, and
read-only UniFi configuration. Home Assistant was covered through its monitoring integration,
existing provisioning/recovery documentation, and VM state; its internal appliance configuration
and Cloudflare account were not exhaustively audited. One independent reviewer examined public
configuration and application code; the coordinator verified the material findings.

No infrastructure settings, passwords, packages, firewall rules, backup data, or service states
were changed. Clean dependency installation and malformed-input reproduction ran only in temporary
local fixtures. The credential-bearing recovery repository and private physical-design repository
were not accessed. Private addresses, tokens, factor IDs, and cookies are excluded from this record.
The operator explicitly approved the external public-IP comparison described below.

This is a comprehensive read-only baseline, **not a completed penetration test or proof of absence
of vulnerabilities**. The remaining active tests and coverage limits are listed below.

## Test results

| Check | Result | Evidence and interpretation |
| --- | --- | --- |
| Repository regression entry points | **22 passed, 3 failed / 25** | Every tracked `test-*` shell, Python and JavaScript entry point ran. Failures are listed below. |
| Insights application tests | **42 passed / 42** | Repeated successfully against a clean committed-lockfile installation in an isolated copy. Initial sandbox socket denial was resolved using approved local socket access. |
| Ansible playbook syntax | **33 passed / 33** | Used an isolated public-tree export and dummy local inventory; no deployment, secret prompts or ignored inventory loading. |
| Bash syntax | **36 passed / 36 files** | `bash -n` on tracked shell files. |
| Python syntax | **6 passed / 6 files** | AST parsing without running production utilities. |
| YAML, JSON and JavaScript parsing | **42 YAML, 12 JSON, 19 MJS files passed** | Safe YAML loading, JSON parsing and `node --check`; YAML parse success does not establish runtime correctness. |
| Public-tree privacy/secret scan | **Passed** | `git-precommit-scan.sh --full-tree --require-gitleaks`; ignored credential files were excluded. |
| Dependency advisory check | **Failed: one critical-rated package** | `npm audit --package-lock-only --ignore-scripts`; Handlebars has two critical and one moderate advisory. Application exposure is qualified under S01. |
| Live Prometheus rules | **Passed** | `promtool check rules` succeeded for both deployed rule files. |
| Host SSH and root MFA | **Passed** | Every PVE host disables password and keyboard-interactive SSH; each root API identity has two enrolled MFA/recovery entries. Enrollment was checked, not a full challenge/recovery exercise. |
| Linux guest automatic patching | **18 / 18 enrolled and timers active** | All 14 LXCs and VMs 100/118/125/127. Hosts intentionally follow the manual patching policy. |
| Host package/kernel baseline | **Current against cached package lists** | All three report PVE 9.2.21 and running kernel `7.0.14-23-pve`; no host packages appeared upgradable. Repository metadata was not refreshed. |
| ZFS health | **Passed on 3 / 3 hosts** | Pools online, no known data errors, zero reported read/write/checksum counters. No scrub or self-test initiated. |
| Tailscale router state | **Both online** | Both routers report `BackendState=Running` and `Self.Online=true`; failover and ACL deny tests were not performed. |
| Monitoring health | **Passed** | 17 / 17 scrape targets healthy; no pending/firing alerts at the observation. |
| LAN authentication probes | **Mixed** | Anonymous management-LAN requests: Prometheus query HTTP 200, Alertmanager alerts HTTP 200, Grafana user API HTTP 401. See S08. |
| Application ingress | **Loopback publishing confirmed** | Vaultwarden backend on TCP 8080 and Actual backend on TCP 5006 bind to loopback. Their containers drop all capabilities and set no-new-privileges. |
| qBittorrent live firewall | **Present and active** | Killswitch input/forward/output chains have drop policies; nftables, WireGuard and qBittorrent are active. Deployed service dependency defect remains S04. |
| qBittorrent current egress | **Passed** | Operator-approved `api.ipify.org` requests succeeded and the VPN guest's public address differed from the control node's. Only pass/fail was retained. This does not exercise tunnel failure. |
| Minecraft live firewall | **Passed passive check** | Input/forward drop policies and six rules present; nftables and game service active. Authentication exception remains documented in PLAN. |
| Backup freshness | **5 / 5 groups fresh** | PBS VMs 100/118/127 approximately 12 hours old, CT 129 approximately 10 hours, native HA approximately 9 hours; collector sample under one hour old. Landing/freshness does not prove restoration. |
| UniFi public admission | **No configured port forwarding found** | Zero port-forward rules; none of ten network objects marks UPnP LAN access enabled. This is configuration evidence, not an external WAN/IPv6 exposure test. |

The three repository failures are stale assertions, not demonstrated production service failures:

- `tests/test-actual-budget.sh:28` expects Actual 26.9.0; public defaults and the running server
  specify 26.10.0 after the recorded maintenance. The disabled companion still pins API 26.9.0;
  compatibility with the newer server needs its own integration check before enabling it.
- `tests/test-seerr-migration.sh:29` expects Seerr 3.4.1; public defaults and runtime specify 3.5.0.
- `tests/test-backup-local-config.sh:26` expects exact obsolete AGENTS wording; the current policy
  still defines the authoritative tree and a stronger prohibition on recovery-repository access.
  This test examines public files only; the production backup script was not executed.

The 22 passing entry points cover Insights contracts, capacity/recovery monitoring, backup
freshness, Git leak scanning, Glance filtering/dashboard contracts, HA memory/synthetic isolation,
host health, portal purchases, maintenance collectors/playbooks, media storage/version upgrades,
Minecraft, qBittorrent monitoring/migration, Renovate, secondary management, Vaultwarden
idempotence, and VM patching. Many are static contract checks or fixtures; they do not replace
live rebuild, restore, authentication, or network-boundary tests.

## Prioritised findings

Severity describes impact and exposure; priority describes what to address first. None of the
isolated application proofs was sent to a production application.

| ID / priority | Finding | Evidence, exposure and required correction |
| --- | --- | --- |
| **S01 / P1 before enabling Insights** | **Critical upstream dependency advisories; live exploitability unproven** | `apps/actual-insights/package-lock.json:319` locks Handlebars 4.7.9 through the Actual API/core dependency. Upstream patches are 4.7.10. Exploitation requires particular untrusted template/AST flows; those were not established in this companion. No Insights container is running on VM 127. Resolve the lockfile advisories and validate Actual API/server compatibility before deployment. |
| **S02 / P1** | **Medium: provisioning can disclose API tokens** | `ansible/playbooks/provision-monitoring.yml:35` mints the PVE monitoring token without `no_log`; `ansible/playbooks/tasks/technitium-instance.yml:133`, `:143`, `:151` embed the admin token in unsuppressed commands. First-login token capture at `:86` is also unsuppressed. Failed/verbose diagnostics can expose secrets. Apply secret-output suppression to every secret-producing/consuming task and review existing operator logs before deciding whether rotation is required. |
| **S03 / P1** | **Medium: Ansible disables target identity verification** | `ansible/ansible.cfg:6` sets `host_key_checking=False`. This weakens target authentication beyond suppressing a first-connect prompt. Use verified host keys and deliberate enrollment on rebuild. Audit SSH commands used strict host checking throughout. |
| **S04 / P1** | **Medium: VPN application startup does not require its killswitch** | `ansible/playbooks/provision-qbittorrent.yml:188` can mask nftables startup failure because its shell lacks failure propagation; `:322` orders after nftables but `:324` requires only WireGuard. Live `systemctl show qbittorrent --property=Requires` confirms nftables is absent. The firewall is active now, and interface binding adds protection; a traffic leak was not demonstrated. Require successful firewall installation/startup and loaded-rule verification, then test failure behavior in a maintenance window. |
| **S05 / P1** | **Medium: HA monitoring bearer token crosses plaintext HTTP** | `ansible/playbooks/provision-monitoring.yml:363` uses HTTP and `:365` supplies a long-lived bearer token. Live scrape configuration confirms HTTP. The token file is mode 0600, which protects storage but not transit. Establish an authenticated encrypted metrics path and confirm the token's account permissions; do not silently replace this with an unverified TLS bypass. |
| **S06 / P2** | **Medium: fresh Grafana install permits a blank provisioning password** | `ansible/playbooks/provision-monitoring.yml:55`, `:76`, `:626` treat blank as keeping existing credentials without a fresh-install gate. Live anonymous Grafana user access returns 401; default credentials were not tested. Require a strong password on initial installation while preserving legitimate rerun behavior. |
| **S07 / P2 before enabling Insights** | **Medium: unhandled request errors terminate the companion** | `apps/actual-insights/src/server.mjs:19` parses the URL before authorization; the async request callback at `:90` lacks an outer exception handler. In an isolated child process, request target `//%` exits with status 1 and `ERR_INVALID_URL`. GET storage/render errors share the uncaught path. Tailscale proxy acceptance of malformed targets was not tested. Catch errors around the entire handler and add behavioral regressions for malformed URLs and failed GET dependencies. |
| **S08 / P2, deliberate network design** | **Medium: broad LAN trust remains the main boundary** | PVE firewall reports disabled/running on all three hosts, with no cluster/host firewall files. Exporters and management services bind broadly; Prometheus and Alertmanager APIs accept anonymous management-LAN reads. All LXCs and mgmt-vm report `PasswordAuthentication yes`, although CT root password login is separately prohibited and usable non-root credentials were not tested. This increases lateral exposure; it does not prove internet exposure or a password bypass. Preserve required monitoring, cluster, deployment and recovery paths when designing scoped access/authentication. Guest nftables protections were verified separately. |
| **S09 / P2** | **Low: secrets are interpolated into privileged shell syntax** | PBS password task `ansible/playbooks/provision-pbs.yml:99`, Vaultwarden token hashing `ansible/playbooks/provision-vaultwarden.yml:171`, and Samba password task `ansible/playbooks/provision-ha-backup-share.yml:140` depend on shell-sensitive quoting. Legitimate quotes, dollar substitutions or metacharacters can corrupt provisioning or become shell code. Use structured arguments/stdin with secret logging suppression and metacharacter fixtures. |
| **S10 / P2** | **Low: UniFi session-cache creation is insufficiently protected** | `scripts/unifi-query.sh:29` uses a predictable shared-temporary cookie path; restrictive permissions follow the login write at `:66`. Local precreation/symlink and initial-permission risks remain. Use a protected per-user cache directory and restrictive permissions before creation. The helper also disables TLS certificate verification with `curl -k`; establish a trusted controller certificate/fingerprint. Its credential file is mode 0600. |
| **S11 / P2** | **Low: regression coverage drifts after maintenance** | Three stale assertions fail, and `.github/workflows/leak-scan.yml` exercises privacy/secret scanning rather than the full regression suite. Update the focused assertions to accepted contracts and add an appropriate deterministic regression gate. Do not mistake passing substring checks for runtime security evidence. |
| **S12 / P1, existing unresolved decision** | **High-impact credential-bearing Git backup model** | The existing PLAN security backlog and ADR-007 describe plaintext credential-bearing recovery material in private Git history. This audit did not access that repository or verify its contents. Privacy of Git access is not encryption. Resolve the already-recorded storage/encryption/history decision and operator-owned rotation requirements; a public-tree scan cannot close this finding. |

S01 references the maintainer's [AST type confusion advisory](https://github.com/handlebars-lang/handlebars.js/security/advisories/GHSA-8r5x-fm3f-whwj)
and [own-property check bypass advisory](https://github.com/handlebars-lang/handlebars.js/security/advisories/GHSA-p8wg-vrv2-v86f).
Both list 4.7.10 as patched. The former requires an untrusted object reaching compilation; the
latter requires attacker-controlled templates and permissive prototype-method access.

Selected upstream checks were also made for Vaultwarden and Jellyfin. The observed Vaultwarden
1.37.4 image exceeds the 1.37.0 fix for the maintainer's
[anonymous WebSocket exhaustion advisory](https://github.com/dani-garcia/vaultwarden/security/advisories/GHSA-96f7-78q5-j345).
Jellyfin's documented 10.11.11 baseline exceeds the 10.11.10 fix for
[authenticated client-log path traversal](https://github.com/jellyfin/jellyfin/security/advisories/GHSA-jg92-mrxq-vv75).
These selected comparisons are not an exhaustive CVE/SBOM inventory of every binary or container.

## Existing residual risks and operational observations

- The off-site backup gap, unverified off-box PBS key-copy assurance, and broad Home-to-IoT/camera
  policy decisions remain owned by PLAN and the runbooks. The live UniFi review found 158 policies,
  including two custom all-protocol network-to-network allows. Their exact source/destination
  correspondence and effective ordering were not proved by packet tests; do not infer a bypass
  from broad predefined zone rules alone.
- The Tailscale reference deliberately grants operators `*:*`; the explicit port-443 grants do not
  narrow that wildcard. The console remains authoritative. Positive reference tests cannot prove
  denied access for other identities, and live console policy was not retrieved.
- Minecraft's offline authentication exception remains intentional; its active guest firewall is
  the admission boundary. The PVE NIC firewall flag alone provides no assurance while the global
  PVE firewall is disabled.
- Cached guest package lists show the deferred Jellyfin migration and Ubuntu Open-iSCSI packages;
  other running guests show no pending packages. This does not establish a fresh security-origin
  vulnerability inventory or justify crossing the deferred Jellyfin major-version boundary.
- Failed units include OpenIPMI on hosts/VMs, unsupported monitoring boot units, and maintenance/
  login/networkd units on PBS and the HA share. These are availability/maintenance follow-ups;
  backup freshness and monitoring health passed despite them. Unit failure causes were not
  exhaustively diagnosed. The independent finance-dashboard container is unhealthy as previously
  recorded; its application source/data remain outside this repository's audit.
- The primary local dependency directory contains an older Actual API than package.json requests.
  Clean temporary `npm ci --ignore-scripts` and a second 42-test pass avoid relying on that stale
  installation. Tests mock the Actual service; real protocol/E2EE compatibility remains untested.
- Apophis now reports the same current kernel as the other hosts. The earlier deferred-reboot
  maintenance record remains historical; this audit does not establish who rebooted it or when.

## Remaining test set and prerequisites

| Test or review | Prerequisite / boundary |
| --- | --- |
| VPN loss and firewall-start failure | Confirmed maintenance window, recovery access, and operator-approved interruption; exercise drop behavior, IPv4/IPv6, DNS and existing flows. Current egress and passive rules do not prove this. |
| Tailscale route failover and ACL denial | Operator and restricted/non-operator identities, authoritative console policy, independent recovery route; verify allowed and denied destinations/ports. |
| VLAN isolation including synthetic HA | Source machines in each relevant VLAN, exact guest identity and gateway log correlation. Keep VM 201 stopped until its existing attended approval gates are satisfied. |
| Restore, reprovision and key recovery | Confirmed window, snapshots/isolated test networks, operator-held recovery keys; prove restorability and measured recovery time. Freshness is already checked. |
| WAN IPv4/IPv6 and Cloudflare HA exposure | Authorized external vantage point and controller/Cloudflare configuration access; verify tunnel authentication, HA accounts/MFA, TLS and absence of unintended external listeners. |
| Full software vulnerability inventory | Current signed package metadata and trusted image/SBOM scanner/advisory coverage for all deployed images, binaries, firmware and HA add-ons. No claim of exhaustive CVE clearance is made. |
| Terraform and ShellCheck validation | Tools are absent locally. Terraform is deferred under ADR-008; no plan/apply or state access was attempted. |
| Live default-password and auth challenge tests | Explicit targets/account consent and rate/lockout controls; do not substitute credential guessing for read-only configuration evidence. |

Reproduction entry points: from `/home/simon`, run each tracked `homelab/tests/test-*` file with its
declared Bash/Python/Node interpreter; run `node --test` from
`/home/simon/homelab/apps/actual-insights/` against a clean lockfile installation;
run the strict full-tree leak scanner; run playbook `--syntax-check` with isolated example/dummy
inventory. Never run provisioning playbooks, the production local-config backup script, or disruptive
runbook exercises merely to reproduce this report.

Address S02–S05 first in focused, reviewed changes; clear S01/S07 before enabling the companion;
resolve S12 with the operator. Network hardening and active failure tests require the separate
decisions and maintenance safeguards above. No finding is marked remediated by this audit.

## Remediation follow-up — 2026-10-11

The operator subsequently requested S01–S05 remediation and selected verified LAN-local TLS for HA.

| Finding | Current remediation evidence |
| --- | --- |
| S01 | **Dependency fix verified.** Handlebars 4.7.10 is pinned by override/lockfile with unchanged MIT licence. The benign compiler regression failed against 4.7.9 and passes against the clean patched install; all 43 app tests pass and npm reports zero advisories. Local dependencies were synchronized without lifecycle scripts. Insights remains disabled; actual-server compatibility and S07 are separate prerequisites. |
| S02 | **Provisioning prevention fixed.** PVE token minting and Technitium first-login/default-rejection/configuration tasks suppress output. A verbose local Ansible fixture verifies six secret-result paths without real credentials. No production tokens were minted or rotated; historical operator-log review remains an operator task. |
| S03 | **Strict trust enabled and access verified.** Ansible requires verified known-host entries and `StrictHostKeyChecking=yes`; read-only Ansible access still succeeds on all three Proxmox hosts. Rebuild/guest enrollment uses independently confirmed fingerprints. |
| S04 | **Live focused fix verified.** qBittorrent requires/binds to nftables and checks loaded default-drop policies before tunnel readiness. Firewall-start failure now propagates. The reviewed focused rollout used per-unit activity checks and systemd daemon-reload, with the torrent PID/start timestamp unchanged and all three services active. Failure behavior was exercised in local fixtures; a disruptive live negative test still needs its maintenance window. |
| S05 | **Live transport fix verified; backup follow-up pending.** The operator installed the HAOS proxy with a dedicated certificate and monitoring-source restriction. The independently confirmed public certificate was installed as explicit trust; authenticated HTTPS metrics return 200 from monitoring, anonymous monitoring returns 401, and another LAN source returns 403. Prometheus and its native credential-free TLS probe are healthy with certificate-expiry telemetry and alerts loaded. Both URLs use the certificate name through a monitoring-only LAN hosts alias; the original dashboard instance, metric filters, token and unrelated scrapes are preserved. Four loopback TLS tests verify fail-closed identity/trust/token-permission handling. Encrypted backup inclusion of the proxy addon and SSL/share files remains unverified; follow step 7 of the [operator runbook](runbooks.md#home-assistant-metrics--verified-lan-tls). |

Ten security-provisioning checks pass, including real verbose Ansible callbacks, firewall failure
fixtures, generated TLS scrape preservation and local alias preservation/conflict handling.
The two changed playbooks pass isolated syntax checking; the preceding all-35 check also passed.
The existing repository regressions remain 22/25 with the same three previously documented stale
assertions; the new checks introduce no additional failures. The independent security review found
and corrected aggregate `systemctl is-active` semantics before live rollout, then passed the gate.
The scoped TLS rollout restarted only the blackbox exporter and reloaded Prometheus; HA Core was
not restarted. A disruptive VPN loss test remains pending its maintenance window.
