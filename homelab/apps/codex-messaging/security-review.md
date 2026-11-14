Purpose: record the bounded dependency and runtime security assessment for the source-only Codex messaging gateway, and distinguish evidence from outstanding deployment gates.

# Security assessment — 2026-11-14

## Verdict and scope

**Do not enroll a real ChatGPT account, Telegram token, or infrastructure key with the currently pinned Codex 0.146.0 runtime.** The pin has a normal TLS dependency matching a certificate-validation advisory, as well as affected vendored sandbox source. The latter is partly mitigated by disabling native execution; that does not address the TLS path. This is a dependency assessment, not a penetration test or permission to deploy. The existing source-only/keyless work can remain reviewable while the runtime decision is revised.

The assessment used public upstream source and advisory databases, public installed package metadata, and synthetic boundary-test evidence. It did not inspect authentication stores, private inventories, the private recovery repository, or hosts, and made no model requests. Application behavior and deployment gates remain authoritative in [the implementation plan](../../docs/codex-messaging-plan.md).

## Evidence and limits

The exact [0.146.0 Cargo.lock](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/Cargo.lock) has Git blob `38f79b89748ff5269b6ec4ecd49f12c9c318a4c4` and SHA-256 `828175f2781fe6c83e3396194f1b00d7fab6b2a27017ea0daa896456c4079d77`. On the assessment date, all **1,162 registry package/version entries** were submitted to the official [OSV batch API](https://google.github.io/osv.dev/post-v1-querybatch/) using ecosystem `crates.io`, then matched advisory records were retrieved from its vulnerability endpoint. **57 package/version entries matched 130 advisory identifiers.** These include duplicate GHSA/RustSec aliases and maintenance notices; they are neither 130 independent vulnerabilities nor 130 CVEs. No matched record was marked withdrawn at retrieval.

A workspace lockfile contains development, platform-specific and optional dependencies. It is **not an SBOM of the installed Linux binary**, and an affected version does not alone prove a reachable exploit. Conversely, an outbound-only service still parses untrusted TLS, HTTP and potentially DNS responses. Source dependency declarations establish likely normal TLS use below; full release build features and relevant call sites remain a gate. Database absence is not evidence of absence.

The installed npm platform package's bubblewrap executable hashes to `77360cb751ccedc5971391444ac86a8a33c15b04d6b4a6fe45f5d25496e62c4c`, matching the deployment pin. Its version string is only `bubblewrap built for Codex`; this does not identify its upstream release. The exact tag's [vendor manifest](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/vendor/bubblewrap/meson.build) identifies **0.11.2**, and [build.rs](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/bwrap/build.rs) compiles the vendored C files by default. Build-time source overrides exist, so source correspondence is strong evidence, not independently verified binary provenance. The [release workflow](https://github.com/openai/codex/blob/rust-v0.146.0/.github/workflows/rust-release.yml) builds and hashes the companion executable separately.

## Findings requiring action

### 1. TLS certificate validation — account-enrollment blocker

The pin selects **rustls-webpki 0.103.13**. [RUSTSEC-2026-0382 / CVE-2026-111943](https://rustsec.org/advisories/RUSTSEC-2026-0382.html) states that affected versions can accept certificate paths containing distrusted emSign intermediate public keys, whose private keys are now well known, **when configured trust anchors permit those paths**. Fixes are **0.103.16** or **0.104.0-alpha.8**; the [upstream fix](https://github.com/rustls/webpki/pull/546) rejects those intermediate keys.

This is more than an arbitrary workspace-lock hit: [codex-http-client normal dependencies](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/http-client/Cargo.toml) explicitly include rustls, native certificates and reqwest's `rustls-tls-native-roots` feature, and [custom_ca.rs](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/http-client/src/custom_ca.rs) constructs the native-root configuration. A credential-bearing HTTPS path is therefore plausible in the ordinary runtime. This review did not establish the effective trust anchors or demonstrate interception. Require a patched runtime or a reviewed equivalent mitigation and build-path proof **before real sign-in**, rather than relying on the absence of inbound listeners or the worker's command-network policy.

### 2. Vendored bubblewrap setup traversal — native-sandbox blocker

[CVE-2026-87766 / GHSA-pxhw-h44j-8pfx](https://github.com/containers/bubblewrap/security/advisories/GHSA-pxhw-h44j-8pfx) affects bubblewrap **before 0.12.0**. During sandbox setup, symlink traversal in attacker-controlled paths can cause host files to be created with the launching user's authority. This is not a demonstrated post-setup escape or automatic root compromise; reachability depends on setup arguments and attacker-controlled filesystem state. Upstream **0.12.0** fixes path resolution using `openat2` confinement and a fallback.

The pinned [utils.c](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/vendor/bubblewrap/utils.c) is byte-identical to [upstream v0.11.2 utils.c](https://github.com/containers/bubblewrap/blob/v0.11.2/utils.c), Git blob `7b7349ab824c8780597b2abb39f181d0e63702eb`, and lacks that fix. Keep native execution unavailable. Enabling it requires a patched, agreed runtime and repeated adversarial boundary tests; an executable hash only preserves the selected bytes.

The separate [CVE-2026-41163 / GHSA-xq78-7hw4-5jvp](https://github.com/containers/bubblewrap/security/advisories/GHSA-xq78-7hw4-5jvp) concerns setuid 0.11.x and was fixed in **0.11.2**. The examined executable has no setuid bit, and the Codex build does not define `ENABLE_SUPPORT_SETUID`; that advisory is not evidence of a current privilege-escalation path here.

### 3. Other network advisories — resolve features and call paths

These are confirmed version matches, with reachability qualified rather than assumed:

| Pinned component | Advisory and effect | Upstream fix / present relevance |
| --- | --- | --- |
| rustls 0.23.36 | [RUSTSEC-2026-0285](https://rustsec.org/advisories/RUSTSEC-2026-0285.html): TLS 1.3 messages accepted across encryption-level boundaries. | **0.23.45**. Transcript authentication remains; do not describe this as an arbitrary MITM authentication bypass. [Upstream fix](https://github.com/rustls/rustls/pull/3265). |
| rustls 0.23.36 | [RUSTSEC-2026-0349](https://rustsec.org/advisories/RUSTSEC-2026-0349.html): unauthenticated ServerHello can influence future key-share prediction. | **0.23.46**. Conditional loss of hybrid post-quantum exchange; no key compromise/authentication bypass. [Fix](https://github.com/rustls/rustls/pull/3355). |
| rustls 0.23.36 | [RUSTSEC-2026-0348](https://rustsec.org/advisories/RUSTSEC-2026-0348.html): pre-authentication Brotli certificate decompression can allocate 1 GiB. | **0.23.46**; requires the **non-default `brotli` feature**, not established for this installed binary. [Fix](https://github.com/rustls/rustls/pull/3297). |
| rustls 0.23.36 | [RUSTSEC-2026-0346](https://rustsec.org/advisories/RUSTSEC-2026-0346.html): session-value Debug can expose TLS secrets. | **0.23.46**; requires custom session-store Debug logging. Ordinary connection/cache Debug is unaffected. [Fix](https://github.com/rustls/rustls/pull/3299). |
| h2 0.4.13 | [RUSTSEC-2026-0258](https://rustsec.org/advisories/RUSTSEC-2026-0258.html): unbounded queued empty DATA frames when a stream is not drained. | **0.4.16**; conditional outbound response DoS, not proof that all requests are vulnerable. [Fix](https://github.com/hyperium/h2/pull/935). |
| hickory-proto 0.25.2 | [RUSTSEC-2026-0491 / CVE-2026-123570](https://rustsec.org/advisories/RUSTSEC-2026-0491.html): hostile DNS header record counts amplify allocations. | **0.26.2**. Determine whether the active DNS path uses Hickory; the network-proxy dependency graph alone does not establish this. [Fix](https://github.com/hickory-dns/hickory-dns/commit/280c0e5c4e3002d73ba0762835ef82272d1d33a6). |
| hickory-proto/resolver 0.25.2 | [RUSTSEC-2026-0118](https://rustsec.org/advisories/RUSTSEC-2026-0118.html), [0119](https://rustsec.org/advisories/RUSTSEC-2026-0119.html), [0514](https://rustsec.org/advisories/RUSTSEC-2026-0514.html), plus further DNSSEC-validation records. | NSEC3 loops and validation errors require DNSSEC features/configuration; encoding complexity has a different path. Migrate the applicable DNSSEC implementation to **hickory-net 0.26.2** / resolver **0.26.2**, rather than treating a prerelease range boundary as a complete fix. Zone-text-parser findings do not establish wire-DNS reachability. |
| rmcp 1.8.0 | [GHSA-33f5-2c5q-wgwj](https://github.com/modelcontextprotocol/rust-sdk/security/advisories/GHSA-33f5-2c5q-wgwj): OAuth metadata resource mismatch permits token theft; [GHSA-c9xm-49cp-xcr9](https://github.com/modelcontextprotocol/rust-sdk/security/advisories/GHSA-c9xm-49cp-xcr9): metadata URL SSRF. | **2.0.0**. Requires an enabled MCP OAuth connection. |
| rmcp 1.8.0 | [GHSA-9g45-5xwm-f3wc](https://github.com/modelcontextprotocol/rust-sdk/security/advisories/GHSA-9g45-5xwm-f3wc): custom authentication headers forwarded across origins on redirects. | **2.1.0**. Custom headers are affected; the stripped Authorization-header path is distinct. |
| rmcp 1.8.0 | [RUSTSEC-2026-0462](https://rustsec.org/advisories/RUSTSEC-2026-0462.html): unbounded Streamable HTTP client response buffering. | **3.9.0**. Disabled MCP connections mitigate this route. [Upstream fix](https://github.com/modelcontextprotocol/rust-sdk/commit/3e0156c1eaf1573a1b878e2a8998d2fa2d0b1439). |

The exact [rmcp-client manifest](https://github.com/openai/codex/blob/rust-v0.146.0/codex-rs/rmcp-client/Cargo.toml) enables auth and Streamable HTTP client/server features as normal dependencies. Current messaging policy must keep MCP/apps unconfigured and unavailable. A server-session leak advisory does not make the stdio app-server an exposed MCP HTTP server. Do not enable these facilities merely because the current bridge does not use them.

Additional material triage remains: [Tokio 1.52.3 I/O-safety violation](https://rustsec.org/advisories/RUSTSEC-2026-0386.html), fixed in **1.51.6/1.53.3**, needs matching `AsyncFd` ownership misuse; [libsqlite3-sys 0.37.0 content disclosure](https://rustsec.org/advisories/RUSTSEC-2026-0459.html) is fixed in **0.39.0**. OpenSSL, archive extraction, Git checkout/transport and other lock hits need build-feature and call-path classification before enrollment; their presence is not proof that disabled plugins, model Git operations or archive extraction are active.

## Existing first-party isolation limits

The source's [empty thread environments](codex_messaging/rpc.py), [worker policy](../../ansible/templates/codex-messaging/worker.toml.j2) and [runtime boundary fixture](tests/runtime_fixture.py) intentionally remove native execution/image/subagent tools and require empty skill catalogs. Earlier synthetic testing observed `/proc/self/environ` exposure despite a `/proc` read-deny policy while native execution was available. Filesystem denials therefore cannot be represented as a proven universal secret boundary. Empty skills catalogs are also a deployment invariant: no general skills-tool disable switch or symlink-safe registered-resource boundary has been established. Re-run the negative probes after every runtime/configuration change, including forged native calls, nonempty or spoofed skill authorities, traversal/URI/symlink inputs, and credential-file/environment access using synthetic data.

OpenAI's [GHSA-w5fx-fh39-j5rw](https://github.com/openai/codex/security/advisories/GHSA-w5fx-fh39-j5rw) affects CLI **0.2.0 through 0.38.0**, patched **0.39.0**. Version 0.146.0 is outside that published cwd/write-root bypass range. This observation does not clear newer native/process/skills boundaries.

## Operating-system dependencies — unresolved before-start gate

Cargo.lock does not assess the target VM's **sudo, Python interpreter/standard library and its linked OpenSSL/SQLite, systemd, OpenSSH, kernel or distribution security backports**. The Python gateway's stdlib-only design does not remove these dependencies. This assessment read no target package state. The local npm executable/mode observations above attest only to the research environment; they do not attest to ownership, modes, package patch levels or running kernel on the deployment VM.

The [gateway unit](../../ansible/templates/codex-messaging/codex-messaging-gateway.service.j2) deliberately uses `NoNewPrivileges=false` so the fixed sudo launcher can change to the worker identity. Consequently, sudo's privilege boundary is material even though the sudoers grant authorizes no root command. Ubuntu's [CVE-2025-32463 record](https://ubuntu.com/security/CVE-2025-32463) documents local root escalation through the chroot option; its [CVE-2025-32462 record](https://ubuntu.com/security/CVE-2025-32462) concerns host-matching authorization under specific sudoers configurations. Both were published **2025-06-30**, and Ubuntu **24.04 LTS** fixes both in **`1.9.15p5-3ubuntu5.24.04.1`**. The host-match condition is not established for this proposed rule, and the patched Ubuntu version need not have upstream version 1.9.17p1 because the distribution backports fixes. Those two fixes do not clear later sudo advisories.

**Before starting an enrolled service**, record the actual VM release and installed vendor package versions, compare their security status with current Ubuntu notices/advisories, and confirm any required service restarts or running-kernel update have taken effect. Cover sudo, Python and linked libraries, systemd, SSH and kernel, not just the Codex artifacts; require the two sudo fixes or a later vendor revision containing them. Ubuntu supplies [release-specific security/patch metadata](https://ubuntu.com/security/oval) for precisely this vendor-version assessment. This is an outstanding commissioning evidence requirement, not a recommendation to install another scanner or permission to inspect the target now.

## First-party findings corrected during this assessment

- Approval prompts previously omitted canonical service parameters, affected targets and exact
  package versions. The gateway now shows the complete scope, including separate reboot review;
  an oversized/private-looking plan pauses changes and provides no approval button.
- Concurrent model requests could replace an outstanding diagnostic/question/approval. A pending
  request now blocks another model tool from replacing its correlation state.
- Unbounded local broker threads and outage replies could exhaust management-VM resources.
  The broker admits sixteen handlers; replies are capped at 128; full backlog blocks model/change
  admission while keeping stop available; the main gateway database is limited to 64 MiB.
  Slice/role limits contain CPU, memory and tasks. These do not provide aggregate storage quotas.
- Installation could adopt unrelated groups/fixed files or retain identity drift. Preflight now
  rejects those collisions, links, shared UIDs/GIDs and unexpected memberships. The fixed worker
  launcher applies no-new-privileges after sudo switches identity. See the independent
  [infrastructure review](infrastructure-review.md) for remaining installed-state gates.

`RUNTIME_SECURITY_APPROVED=False` blocks all real gateway, worker and device-login entry points
before credential reads; no configuration/environment override exists. The dummy-only preflight
reports its separate runtime-security result as blocked. Regression checks exercise these entry
points, approval visibility, parallel tools, backlog/approval denial and socket exhaustion.

Final source verification: **86 tests**, including the actual pinned binary against a network-confined
local scripted model with dummy auth; eleven synthetic Ansible identity/path fixtures; rendered
systemd units/slice, sudo policy, shell launcher and synthetic playbook syntax. No host identity,
package patch status, actual service isolation, credentials or restore was inspected or exercised.
The absence of a new defect in this bounded source review is not a claim of zero vulnerabilities.

## Runtime candidate and release gate

The latest stable release reported by the [official GitHub releases API](https://api.github.com/repos/openai/codex/releases/latest) on this date was [0.169.0](https://github.com/openai/codex/releases/tag/rust-v0.169.0), published 2026-11-13. Its [lockfile](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/Cargo.lock) selects rustls **0.23.46**, webpki **0.103.16** and h2 **0.4.19**, addressing the headline version matches above. A fresh batch scan of its **1,296** registry entries still matched **35** package/version entries; it retains Hickory **0.25.2** alongside newer versions and Tokio **1.52.3**. Its [vendored bubblewrap manifest](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/vendor/bubblewrap/meson.build) still says **0.11.2**, with the same affected utils.c. It is a **candidate for an explicitly agreed runtime revision and full protocol/isolation revalidation**, not an approved or comprehensively remediated upgrade. No fully suitable replacement release was established in this bounded review. No pin was changed.

A follow-up source check confirms 0.169.0 still declares rustls/native-root HTTPS in [codex-http-client](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/http-client/Cargo.toml). Its [network-proxy manifest](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/network-proxy/Cargo.toml) declares the Rama network stack normally but one direct `rama-dns` dependency only on macOS. That distinction prevents clearing or asserting Linux Hickory reachability from the workspace lock alone; no definitive compiled Linux feature graph was obtained. No custom patched runtime was built or proposed.

Before enrollment: select the revised runtime or obtain a reviewed upstream backport/proven mitigation; establish the Linux release feature/SBOM and relevant dependency paths; resolve or explicitly evidence the nonreachability of remaining material advisories; repeat keyless mocked-model/native/skills and billing-fail-closed tests; then review the account-only gate separately from infrastructure-key enrollment. A dependency pin must be paired with recurring advisory checks and an owner for security updates. Re-scan before enrollment and each approved runtime change, and promptly when upstream publishes a security advisory; updates must repeat the protocol and isolation gates rather than silently replace the binary.

## Scan inventory for reproduction

The 57 matched package/version entries below are a triage inventory, **not a list of confirmed gateway exploits**. Repeat the documented OSV query against the pinned lock to obtain current advisory IDs and aliases; records can change after this dated assessment.

`actix-http@3.11.2`, `actix-web@4.12.1`, `atomic-polyfill@1.0.3`, `aws-smithy-json@0.61.9`, `basic-toml@0.1.10`, `bincode@1.3.3`, `block-buffer@0.12.0`, `cmov@0.5.3`, `crypto-bigint@0.5.5`, `ctutils@0.4.2`, `derivative@2.2.0`, `event-listener@5.4.1`, `faster-hex@0.10.0`, `fxhash@0.2.1`, `gix@0.81.0`, `gix-fs@0.19.2`, `gix-pack@0.68.0`, `gix-packetline@0.21.2`, `gix-sec@0.13.2`, `gix-transport@0.55.1`, `gix-validate@0.11.0`, `h2@0.4.13`, `hickory-proto@0.25.2`, `hickory-resolver@0.25.2`, `jsonwebtoken@9.3.1`, `libsqlite3-sys@0.37.0`, `lru@0.12.5`, `lru@0.16.3`, `memmap2@0.9.10`, `openssl@0.10.75`, `opentelemetry_sdk@0.31.0`, `paste@1.0.15`, `pin-utils@0.1.0`, `proc-macro-error2@2.0.1`, `quick-xml@0.39.4`, `quinn-proto@0.11.14`, `quinn-udp@0.5.14`, `rmcp@1.8.0`, `rustix@1.1.4`, `rustls@0.23.36`, `rustls-webpki@0.103.13`, `scc@2.4.0`, `serde_with@3.17.0`, `tar@0.4.45`, `tokio@1.52.3`, `unsafe-libyaml@0.2.11`, `webbrowser@1.0.6`, `webpki-root-certs@1.0.5`, `webpki-roots@1.0.5`, `yaml-rust@0.4.5`, `zbus_names@3.0.0`, `zip@2.4.2`, `zstd@0.13.3`, `zstd-safe@7.2.4`, `zstd-sys@2.0.16+zstd.1.5.7`, `zvariant@4.2.0`, `zvariant_derive@4.2.0`.
