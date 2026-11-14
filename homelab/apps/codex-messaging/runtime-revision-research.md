Purpose: identify ordinary dependency remediation for a normal Codex session reached through Telegram, without deploying or enrolling accounts.

# Native runtime revision research — 2026-11-14

## Current recommendation and result

Use the official **Codex 0.169.0 Linux x86_64 musl release** with a **patched, compatible system bubblewrap**, preferably current upstream **0.13.1** or an independently verified vendor backport. Upstream **0.12.0** is the minimum release fixing the identified setup traversal. Normal Codex execution environments and tools remain part of the intended product. The earlier helper-free/environment-free proposal is **retired**, and its negative tests do not establish that a normal native session works.

**The isolated upstream build succeeded.** No pre-existing compiler/build tools were available, so verified build-only inputs were extracted under `/var/tmp`; no root/system package installation occurred. Upstream source was unchanged, and mandatory libcap was retained. No runtime pin or application file changed, no credential/inventory/host access occurred, and no model request was made.

| Built artifact | Result |
| --- | --- |
| Path | `/var/tmp/bubblewrap-isolated-build-vh_uqj_r/build/bwrap` |
| Executable SHA-256 | `711ac2c00998eede367c2b3827efa36ba4436dfce19ab9d3b6d56ff5a5996fa1` |
| Version/size/mode | `bubblewrap 0.13.1`; 2,305,192 bytes; `0755`, non-setuid |
| ABI | ELF64 x86_64, ET_EXEC; **no PT_INTERP or PT_DYNAMIC**, statically linked for musl |
| Codex capabilities | `--as-pid-1`, `--perms`, `--argv0`, `--ro-bind-fd` present in successful `--help` output |
| Native smoke | **Not passed in this runner**: network namespace test hit `RTM_NEWADDR: Operation not permitted`; filesystem-only test hit `setting up uid map: Permission denied`. These are commissioning limitations, not reasons to weaken the sandbox. |

`artifact.json`, exact setup/build commands, `native.ini`, clean build environment, source/tool metadata, configure/compile logs and synthetic smoke results are retained beside the artifact. Native Codex integration and the actual VM's user-namespace/kernel policy remain unverified; version/help/ELF success alone is not an end-to-end sandbox result.

## Concrete fixes and Ubuntu caveat

The [official Codex releases API](https://api.github.com/repos/openai/codex/releases/latest) still identifies stable **0.169.0**, published **2026-11-13 08:37:05 UTC**; the checked newer prerelease was **0.171.0-alpha.5**, published **2026-11-14 01:20:37 UTC**. The stable [lock](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/Cargo.lock), SHA-256 `56e04c89b25a6efa1fa6f1cf02934e92451933c8ebda57a5153207ba9ea9fb9e`, advances rustls to **0.23.46**, rustls-webpki to **0.103.16**, h2 to **0.4.19**, OpenSSL crate to **0.10.82**, and libsqlite3-sys to **0.39.1**. These resolve the earlier identified TLS/certificate-validation, h2 and SQLite version matches. Normal HTTPS uses [codex-http-client](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/http-client/Cargo.toml); [musl builds enable vendored OpenSSL](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/core/Cargo.toml), selecting openssl-src `300.6.1+3.6.3`. OS Python/OpenSSL/SQLite vendor patching is a separate installed-state check.

Both checked Codex tags still vendor bubblewrap **0.11.2**. [CVE-2026-87766](https://github.com/containers/bubblewrap/security/advisories/GHSA-pxhw-h44j-8pfx) affects versions before **0.12.0**: filesystem symlinks can redirect setup-time file creation to the host as the launching user. Upstream 0.12.0 fixes resolution and removes setuid support. The newer [0.13.1 release](https://github.com/containers/bubblewrap/releases/tag/v0.13.1), published **2026-10-14**, also fixes opening parent directories without read permission. Its tag is marked verified by GitHub; an independent local signature verification was not performed.

**Do not assume Ubuntu 24.04's latest bubblewrap is patched.** Ubuntu's [CVE record](https://ubuntu.com/security/CVE-2026-87766) currently marks Noble vulnerable. [USN-8779-1](https://ubuntu.com/security/notices/USN-8779-1) initially shipped a fix in `0.9.0-1ubuntu0.2`, but [USN-8779-2](https://ubuntu.com/security/notices/USN-8779-2), dated **2026-09-18**, says it reverted the fix because of symlink-resolution regressions. The [official Noble changelog](https://lists.ubuntu.com/archives/noble-changes/2026-September/059045.html) for `0.9.0-1ubuntu0.3` explicitly drops CVE-2026-87766. A future vendor backport must be checked against its current advisory/changelog rather than a numeric package floor inferred from the superseded notice.

## Helper source provenance and Codex compatibility

Only official source-release archives were downloaded to `/var/tmp/bubblewrap-native-source-u455s702/`, with their public GitHub release JSON. Computed archive hashes match the corresponding official API asset digest:

| Source | SHA-256 |
| --- | --- |
| [bubblewrap-0.12.0.tar.xz](https://github.com/containers/bubblewrap/releases/download/v0.12.0/bubblewrap-0.12.0.tar.xz) | `9760d007363e3abba7c747489910f9f82d9fca53ba3bd3282e396fa3c97a3314` |
| [bubblewrap-0.13.1.tar.xz](https://github.com/containers/bubblewrap/releases/download/v0.13.1/bubblewrap-0.13.1.tar.xz) | `0e85c8702248b8dd64144f594147553650cdd0e4c951690345faace79c217c4d` |

These are **source** hashes, not executable hashes. Upstream [0.12 release notes](https://github.com/containers/bubblewrap/releases/tag/v0.12.0) and [COPYING](https://github.com/containers/bubblewrap/blob/v0.12.0/COPYING) specify **LGPL-2.1-or-later**. Preserve source/license and build provenance when distributing the helper.

Codex's [system-helper selector](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/linux-sandbox/src/launcher.rs) prefers a usable system bwrap on PATH, requires `--as-pid-1` and `--perms`, and recognizes `--argv0`/`--ro-bind-fd` with compatibility paths. It invokes an executable using command-line arguments; this is not a shared-library ABI with Codex. The completed static musl artifact avoids a target dynamic-loader/libcap ABI dependency. It still needs compatible CPU/kernel/user-namespace support and testing on its actual host; that installed-state evidence is outstanding.

Codex may fall back to its old bundled helper if the expected system helper is missing or rejected. Consequently preflight must verify the expected patched **selected executable**, ownership/path, hash, version and capabilities; an unpatched bundled fallback is not an acceptable successful test. Ordinary native sandbox execution must then succeed with a harmless fixture, and representative read/write/network restrictions must behave as configured. Do not replace the bundled executable in place: its [build-time digest verification](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/linux-sandbox/src/bundled_bwrap.rs) intentionally rejects different bytes. Version/help and static ELF inspection passed; actual Codex helper selection/native execution remains unverified because this runner denied namespace setup.

## Isolated build provenance

The build used [official Zig 0.17.1](https://ziglang.org/download/) (`zig-x86_64-linux-0.17.1.tar.xz`, SHA-256 `3581863e3cbcfd0fce0efc682ce7e9e93da96668a977791d356a26d2a7e9b17a`). Its hash matched the official index, and both archive and trusted-comment minisign signatures verified against Zig's published key using the existing Ed25519 verifier. Hashed build-only [Meson 1.12.1](https://pypi.org/project/meson/1.12.1/) and [Ninja 1.13.2](https://pypi.org/project/ninja/1.13.2/) wheels were extracted without system/Python-environment installation.

Because upstream bubblewrap has **no libcap-disable option**, signed Alpine v3.23 x86_64 **libcap-dev/libcap-static 2.78-r0** supplied genuine musl headers/archive. The static archive SHA-256 is `59c683ce9288ba369c578e3939dad86ff2e2f063146cfaab141de8ded9cff7e3`. Temporary musl/pkgconf inputs served dependency discovery only. APK package signatures verified using official Alpine keys; the temporary verifier's detached RSA/SHA-256 signature was independently verified before use. These inputs remained under the build directory and did not alter a package database.

The standard Meson native file selects `zig cc -target x86_64-linux-musl`, `zig ar`, temporary pkgconf, and static linking. Build options: release, static/prefer_static; optional SELinux, man pages, completion generation and upstream test targets disabled. No compiler wrappers, source patches or capability substitutions were introduced. Upstream helper functional tests were not claimed: the separate synthetic smoke failures above preserve that limitation.

License metadata: bubblewrap **LGPL-2.1-or-later**; libcap **BSD-3-Clause OR GPL-2.0-only**; musl/Zig **MIT**; Meson/Ninja **Apache-2.0**; pkgconf **ISC**; temporary APK verifier **GPL-2.0-only**. Preserve corresponding source/license notices when packaging the static artifact. Build-tool provenance and hashes are recorded in the temporary manifest rather than adding product dependencies to the relay.

## Remaining dependency findings are update risks

The earlier official OSV registry scan covered **1,296** package/version entries and matched **35** entries; aliases and unmaintained notices are not independent CVEs. A Cargo.lock is not an installed binary SBOM. This table preserves dispositions without using disabled ordinary tools as remediation:

| Entries | Normal-runtime significance |
| --- | --- |
| hickory-proto/resolver 0.25.2 | Normal Rama proxy DNS path; [wire-allocation issue](https://rustsec.org/advisories/RUSTSEC-2026-0491.html) is fixed in 0.26.2. DNSSEC/text-parser advisories have additional prerequisites. Active proxy/DNS use matters; the newer test-only proto 0.26.3 does not fix this route. Track upstream; do not claim the normal runtime patched. |
| tokio 1.52.3 | [AsyncFd ownership issue](https://rustsec.org/advisories/RUSTSEC-2026-0386.html), fixed 1.51.6/1.53.3. Inspected native PTY/watch sites own File lifetimes; no incorrect-close/reuse exploit established. This remains a dependency update finding. |
| jsonwebtoken 9.3.1 | [Malformed optional-claim validation](https://github.com/Keats/jsonwebtoken/security/advisories/GHSA-h395-gr6q-cpjc), fixed 10.3.0. Inspected Agent Identity and WebSocket sites deserialize typed numeric expiry and require/check relevant claims; no matching bypass established. |
| opentelemetry_sdk 0.31.0 | [Baggage extraction DoS](https://github.com/open-telemetry/opentelemetry-rust/security/advisories/GHSA-w9wp-h8wv-79jx), fixed 0.32.1. Tagged Codex installs TraceContextPropagator; no BaggagePropagator call found. Telemetry presence alone does not prove this path. |
| quick-xml 0.39.4 | [CPU](https://rustsec.org/advisories/RUSTSEC-2026-0194.html)/[namespace allocation](https://rustsec.org/advisories/RUSTSEC-2026-0195.html) fixed 0.41.0. Exact lock edges put protocol parsing on **0.41.0**; old 0.39.4 belongs to TUI plist/theme loading and Wayland build input. |
| quinn-proto 0.11.18 | [Retry-token OOM](https://rustsec.org/advisories/RUSTSEC-2026-0524.html)/[stream limit](https://rustsec.org/advisories/RUSTSEC-2026-0523.html), fixed 0.11.19. Identified route is the separate TCP-tunnel command; no workspace reqwest HTTP3 enablement found. Reassess if that route is used. |
| quinn-udp 0.5.14/0.6.1; cmov 0.5.3; zstd-sys 2.0.16+zstd.1.5.7 | Advisory prerequisites respectively exclude [Linux](https://rustsec.org/advisories/RUSTSEC-2026-0538.html), require [aarch64](https://github.com/RustCrypto/utils/security/advisories/GHSA-3rjw-m598-pq24), or require [wasm32](https://rustsec.org/advisories/RUSTSEC-2026-0410.html); selected target is Linux x86_64. |
| gix 0.89.0; tar 0.4.45; zip 9.0.0 | [Reduced-trust/case-insensitive Git path protection](https://github.com/GitoxideLabs/gitoxide/security/advisories/GHSA-q54r-jf2p-rfr2), [PAX interpretation](https://github.com/composefs/tar-rs/security/advisories/GHSA-3pv8-6f4r-ffg2), [ZIP dual-reader differential](https://github.com/zip-rs/zip2/security/advisories/GHSA-m665-v7pm-7grj); fixes 0.90.0/0.4.46/9.0.5. Native Git/plugins/archive intake can make these material; prior constrained-profile exclusions no longer clear normal use. Do not describe every archive call as RCE. |
| zstd 0.13.3; zstd-safe 7.2.4 | [Borrowed-context reuse](https://rustsec.org/advisories/RUSTSEC-2026-0391.html) and [specialized unsafe APIs](https://rustsec.org/advisories/RUSTSEC-2026-0395.html) through [0406](https://rustsec.org/advisories/RUSTSEC-2026-0406.html). No matching Codex call pattern found; [legacy writer disclosure](https://rustsec.org/advisories/RUSTSEC-2026-0403.html) explicitly excludes the read Decoder/decode_all used for rollout reading. Residual transitive risk, not a clean bill. |
| aws-smithy-json 0.61.9 | [JSON recursion](https://github.com/smithy-lang/smithy-rs/security/advisories/GHSA-8ffr-xgwf-xj56), fixed 0.62.7; AWS/Bedrock provider path, not evidence about every ChatGPT HTTPS request. |
| block-buffer 0.12.0; crypto-bigint 0.5.5; event-listener 5.4.1; rustix 1.1.4; serde_with 3.17.0 | Conditional caught-panic/reuse, secret-dependent timing, non-Send tags, zero-length xattr buffers and KeyValueMap serialization issues. No matching Codex misuse established; full transitive/compiler proof unavailable. Track upstream updates rather than turning ordinary tools off. |
| scc 2.4.0; libz-sys 1.1.29 | scc parent serial_test is dev-only. libz-sys leak requires build cc ≥1.6.0; lock has 1.2.55 and direct curl is Windows-only. Not a normal installed Linux model-input exploit established here. |
| atomic-polyfill; basic-toml; bincode; derivative; fxhash; paste; pin-utils; unsafe-libyaml; zbus_names; zvariant; zvariant_derive | The remaining **11 entries** are unmaintained-package notices. Preserve upstream maintenance/update tracking; do not count these as 11 proven vulnerabilities. |

Git-pinned **rmcp 3.5.1** is outside that registry-only count. Its [HTTP client still buffers JSON bodies](https://github.com/modelcontextprotocol/rust-sdk/blob/98a54789b80110ad210495c4ad845c89e1980471/crates/rmcp/src/transport/common/reqwest/streamable_http_client.rs); the [3.9.0 fix](https://rustsec.org/advisories/RUSTSEC-2026-0462.html) remains relevant when configuring MCP servers. These conditional issues require ordinary runtime update/risk decisions as capabilities are actually used; they do not justify claiming all Codex 0.169.0 dependencies secure.

Next concrete result needed: verify this patched helper's selection by official Codex 0.169.0 and a normal native session on an environment permitting the required namespaces, using only synthetic data. The binary has not been installed or published; provisioning and actual sign-in remain separate actions. No deployment or enrollment occurred in this assessment.
