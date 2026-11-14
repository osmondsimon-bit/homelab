Purpose: record the security and infrastructure source review of the same-user Telegram relay, without authorizing installation or account enrollment.

# Relay review — 2026-11-14

**Latest state (2026-11-15): installed, enabled and privately paired.** The coordinator verified the installed corrected source/runtime and native enforcement; the owner confirmed `/status` and a fresh normal `pwd` result through Telegram. The dated sections below preserve the source review and commissioning findings at each stage. Real approval/question variants and isolated restore remain additional coverage, not claims of this harmless first-task acceptance.

**Source verdict: acceptable after the corrections below.** This covers the revised bridge in [ADR-028](../../decisions/028-codex-messaging.md), not the retired operations broker. The [plan](../../docs/codex-messaging-plan.md) owns scope and the [runbook](../../docs/components/codex-messaging.md#installation-and-commissioning) owns commissioning. No deployment, host measurement, credential access, pairing, bot call or real model turn was performed for this review.

The review independently examined the coordinator's relay, CLI, transport and documentation. The worker and installation configuration were implemented by this reviewer and also inspected by the coordinator; their checks here include self-review rather than a claim of wholly separate authorship.

## Trust and authority

- Telegram updates and callbacks require the enrolled numeric owner and private chat. Console pairing uses a fresh, short-lived unpredictable nonce, a private human sender and exclusive creation of the private enrollment file. Usernames and first contact confer no authority.
- The local official app-server is trusted protocol software. Model instructions and repository/tool content are untrusted inputs to ordinary Codex. Supported approval/question responses are bound to the original request and current thread/turn, immutable and consumed once. Unknown requests are rejected. Command/file approval sends `accept` or `decline`, never session approval; explicit permissions use the native **turn** scope.
- The relay and Codex deliberately share the existing user's UID, credentials, groups, workspace and normal tool permissions. A compromised native tool or same-user process can read/change relay secrets and state; directory modes and prompt guidance do not isolate them. Existing sudo/SSH authority is retained, not newly granted. Repository rules and runbooks still govern destructive work and prohibited recovery-repository access.
- Telegram cloud chats are not end-to-end encrypted. Phone redaction is best effort, not a confidentiality guarantee. Input has reached Telegram before the relay sees it; ordinary Codex may send necessary diagnostic context to OpenAI. Unlabelled or unfamiliar credentials can evade heuristic output checks. Do not send secrets through this interface.

## Findings and dispositions

| Finding | Disposition and source evidence |
| --- | --- |
| Redacted/truncated native approval could conceal the original target or change. | **Fixed.** [Approval rendering](codex_messaging/relay.py#L154) requires exact complete command and working directory, permission scope, or complete proposed file patch. Redaction or excessive length declines the request for local review. Approval output preserves literal paths and patch text; summary-only HOME shortening does not change approval scope. |
| File paths and a reason did not reveal the proposed edit. | **Fixed.** [Worker metadata](codex_messaging/normal_worker.py#L159) retains complete proposed diffs only when every diff is present and their aggregate is at most 6,000 characters. `diffAvailable` is false otherwise and no partial diff is passed. The relay displays the full safe patch or declines for local review; this does not change native approval policy for ordinary edits. |
| Native output bursts filled the relay queue before downstream filtering. | **Fixed.** Command output and unused agent deltas are discarded before enqueue. Selected item metadata and final agent messages remain; raw stdout/stderr streams do not reach Telegram. The external-peer regression emits 1,200 discarded deltas before the turn-start reply. |
| API-key authentication could trigger a quota request before rejection. | **Fixed.** [Turn admission](codex_messaging/normal_worker.py#L215) rejects a non-ChatGPT account before querying quota, then [subscription validation](codex_messaging/authentication.py#L14) requires a known included plan/allowance and zero-credit state before starting/resuming a thread. Fixed launch and thread provider choices prevent custom-provider fallback; ordinary tool credentials and SSH settings remain available. |
| Stale approvals/questions could survive stop, expiry, or restart. | **Fixed.** Worker responses bind original request/thread/turn, reject mutations and reuse, and interruption invalidates pending requests, including queued requests. Explicit native question cancellation sends the valid empty answer map. [Relay recovery](codex_messaging/relay.py#L48) pauses uncertain work and clears pending state; accepted update offsets are committed before dispatch, so accepted tasks are not automatically replayed. |
| Completion and request expiry could race, causing an unnecessary service failure. | **Fixed.** [The run loop](codex_messaging/cli.py#L144) processes a completed native event before ticking expiry; dismissal suppresses only the specific already-stale native response errors. Other worker failures still stop safely. |
| A buffered pre-recovery `/resume` could clear the new recovery pause. | **Fixed.** Recovery/pause records a resumption time and requires a strictly later Telegram timestamp, rejecting buffered controls from before recovery or the same second. |
| Installer defaults could override inventory and safe failures were discarded. | **Fixed.** Defaults resolve with `default(...)` in the first pre-task, preserving inventory overrides. App-server stderr is discarded; the CLI's constant safe failure notice goes to the unit journal. Raw native output is not journalled by the relay. |

Subscription checks do not reserve shared account quota or prove account-side top-up settings. Positive/unlimited/ambiguous credit state is rejected, but actual account behavior still requires attended verification. Notifications may be delivered twice after an ambiguous Telegram send; approval consumption prevents a repeated button from dispatching twice. No exactly-once infrastructure effects are claimed.

## Infrastructure assessment

The [playbook](../../ansible/playbooks/provision-codex-messaging.yml) configures an existing management VM and user. It creates no guest, account, group, sudo rule, SSH key or copied Codex login. It installs only public Python package source plus the entry point and two local, hash-verified runtime artifacts. Privileged installation paths reject links, hardlinks and unsafe ownership/modes; unexpected runtime helpers require explicit operator cleanup. Current/legacy services must already be stopped and disabled before replacement. The playbook reloads unit definitions but never starts, stops, restarts or enables a service.

Root owns application/runtime files and the five-path non-secret configuration. The existing user's primary group can read configuration; the user's state directory is `0700`, private files are `0600`, and the service umask is `0077`. Native tools keep normal user/group/sudo access; `ProtectHome`, `NoNewPrivileges`, separate identities and tool-disabling profiles are intentionally absent. Root-controlled installation is not a separate security boundary around the same-user workspace.

The [unit](../../ansible/templates/codex-messaging/codex-telegram.service.j2) requires nonempty token/enrollment files, uses the existing HOME/workspace, and puts the reviewed runtime directory first on PATH. Telegram uses bounded outbound HTTPS with certificate verification, proxy bypass and redirect refusal. The relay adds no TCP listener, port forwarding, tunnel or firewall change; native Codex retains its normal network authority. A system service does not automatically inherit an interactive shell's `SSH_AUTH_SOCK`; agent-dependent keys need explicit attended setup and a native SSH smoke check, without copying credentials.

Concurrency is one active phone turn and one local state lock. There are 128 queued outgoing messages, a 64 MiB SQLite main-database limit, bounded RPC lines and a 256-event queue. These limits are not an aggregate disk quota or a CPU/RAM budget. Native tools, model processes, existing Codex history/logs and SQLite WAL can consume additional resources. PLAN records **10 GB management-VM RAM**; ADR-000's original smaller sizing is historical. Current CPU/disk allocation, peak headroom and actual service usage were not measured. No VM resize or arbitrary tool resource ceiling is introduced by this source change.

A management-VM/hosting-node or connectivity outage also removes this interface. There is no independent management/reboot safety controller in the revised design. Tailscale/desktop/console recovery and the existing runbooks remain essential. `KillMode=control-group` and the 15-second stop timeout can terminate local descendants; remote effects may already have completed or continue. Interrupt/stop is neither rollback nor a durable package-maintenance transaction.

The existing encrypted management-VM backup decision in [ADR-012](../../decisions/012-backups.md) applies. Verify inclusion and coherent recovery of the private SQLite/WAL, token/enrollment, and existing Codex state; no new backup job or measured restore guarantee is claimed. A restored clone must not poll with the same token while the original is active. Rollback stops/disables the unit and preserves private state for review; it must not reset the workspace, replay operations, or remove the user's login.

## Evidence and remaining gates

Independent checks completed: **17 worker tests** against an external recording stdio peer; Ansible syntax checking with an explicit synthetic inventory/configuration; rendering of both templates; synthetic service-state, ownership/link, inventory-default and stale-helper assertions; focused diff whitespace checks. No playbook task, account lookup or service action was executed against a host. The coordinator reports **38 integrated tests passing**, including loopback Telegram and the external stdio peer. In this review environment full discovery stalled during asyncio executor shutdown after the isolated pairing test reported success, so an independent complete-suite pass is not claimed.

Before any operational use, separately authorize installation and complete:

1. Verify the exact installed Codex 0.169.0/static bubblewrap 0.13.1 hashes and selected helper, OS vendor patches, kernel/user-namespace support, harmless native execution and configured sandbox behavior. The research runner's namespace failures remain outstanding; binary version/help/hash checks alone do not clear them. Ordinary user configuration must not select an older helper or unintended provider.
2. Check live management-VM CPU/RAM/disk headroom and steady/peak usage, backup coverage and isolated restore behavior. Prevent concurrent phone/desktop change operators and duplicate restored pollers.
3. Verify existing ChatGPT sign-in, included quota and account-side credit/top-up controls without API credentials; perform attended console/private-chat pairing and review the numeric owner. No enrollment is authorized by this review.
4. Prove installed native command/file/permission approvals, supported questions/cancellation, actual SSH context, interruption, restart/uncertain outcome recovery and transport failure handling. Keep the unit stopped/disabled until these checks and the first attended start are separately approved.

## Commissioning addendum — exact-path AppArmor helper policy, 2026-11-15

The preceding sections record the earlier source-only milestone. The user subsequently authorized commissioning. The coordinator reports that installation completed through the user's local sudo, the relay remains **inactive and disabled** (installed, never started), installed hashes/root ownership checks passed, and the existing account's included allowance/zero-credit checks passed without a model turn. Those installation/account facts were not independently re-read here; this reviewer accessed no token, enrollment, auth cache or password.

**Bounded configuration verdict: acceptable for the separately authorized operator loading step; native commissioning is not yet passed.** The coordinator observed the expected patched `/opt/codex-messaging/runtime/bin/bwrap` through strace, but namespace setup failed with `RTM_NEWADDR: Operation not permitted`. The reported host setting is `kernel.apparmor_restrict_unprivileged_userns=1`. The existing vendor profile attaches to `/usr/bin/bwrap`, so that profile's attachment does not cover the separately installed helper.

This review read `/etc/apparmor.d/bwrap-userns-restrict` directly and compared it with the new [profile template](../../ansible/templates/codex-messaging/codex-telegram-bwrap.j2). After substituting only the attachment path and the two profile names, their operative rules match; optional vendor-local override includes are deliberately absent. The new names are `codex_telegram_bwrap` and `codex_telegram_unpriv_bwrap`, with the sole executable attachment `/opt/codex-messaging/runtime/bin/bwrap`.

The parent permits namespace setup and its required capabilities, then uses `px` to stack execution into the restricted child. The child keeps its inherited `pix` stacking behavior and `audit deny capability`. There is no unconfined/complain flag, parent inherit-exec fallback, child capability grant, global sysctl change, or replacement of the vendor `bwrap`/`unpriv_bwrap` profiles. This preserves the vendor hardening model for the new helper path; it is not a separate UID boundary or a guarantee against every user-namespace/kernel vulnerability. Ubuntu documents both [the purpose and limitations of selective namespace access](https://discourse.ubuntu.com/t/understanding-apparmor-user-namespace-restriction/58007); the [policy syntax reference](https://manpages.ubuntu.com/manpages/noble/man5/apparmor.d.5.html) describes profile attachments and execution transitions.

The playbook defaults `codex_telegram_install_apparmor_profile` to false, checks the reviewed Ubuntu 24.04 parser/ABI prerequisites, and retains root-owned regular-file/no-link/no-hardlink protection for the dedicated policy path. It validates the candidate with `--skip-kernel-load --skip-cache` before installation and, only when explicitly opted in, replaces the two named profiles from `/etc/apparmor.d/codex-telegram-bwrap`. It does not reload the complete AppArmor service or alter vendor policy. The explicit profile load now reports `changed_when: true`, correctly identifying the kernel-policy mutation. The installation guard accepts both `stopped` and `inactive` services only when disabled; running or enabled installations remain refused.

Independent checks completed for this addendum:

- Exact normalized rule comparison against the installed vendor profile passed.
- `/usr/sbin/apparmor_parser --skip-kernel-load --skip-cache` accepted the candidate; no profile was loaded by this reviewer and no parser cache was written.
- Ansible syntax checking passed with an explicit synthetic inventory/configuration; no playbook tasks or infrastructure operations ran.
- Four independent synthetic Ansible evaluations passed: `inactive/disabled` and `stopped/disabled` accepted; `running/disabled` and `inactive/enabled` rejected. The explicit profile-load change-reporting flag was also checked.

At this update the dedicated policy has not been loaded. After the operator loads only this reviewed policy, the planned native fixture must confirm the expected helper execution with strace, permitted workspace writes, denied outside-workspace writes and denied network access under the fixture's policy. Use the existing normal `CODEX_HOME` so helper-selection overrides are exercised. Verify the actual child's `codex_telegram_unpriv_bwrap` stack label and zero effective capabilities, rather than accepting helper setup alone as proof. Codex may perform nested setup after an execution transition; if the restricted child prevents that workflow, investigate the concrete sequence rather than adding child capabilities or weakening host-wide restrictions. Recheck the profile/helper selection after runtime updates. Until these checks pass, keep the relay inactive/disabled and do not declare native operation, pairing or the first model turn successful. Rollback affects only the new dedicated profile file/names and must not disable the vendor policy or the host restriction.

## Commissioning addendum — subscription inference routing, 2026-11-15

The coordinator reports that the operator loaded the reviewed AppArmor policy and the actual native fixture passed using the normal `CODEX_HOME`: strace selected the expected patched helper, the child retained the restricted profile and zero effective capabilities, workspace writes succeeded, outside writes failed read-only, and the fixture's network restriction held. The root-controlled policy hash matched and the global namespace restriction remained enabled. The operator privately supplied the token and paired the owner; the service was enabled/active with no restarts, and the user confirmed `/status` returned ready/idle. This reviewer did not read credentials, pairing identifiers or private caches and did not repeat those live operations.

The initial live `pwd` requests then failed during model connection/authentication, before any command ran. A real source bug was identified: the worker explicitly set `openai_base_url` to the Platform API URL even while requiring ChatGPT authentication. **The earlier source review checked provider/auth selection but missed the precedence of that explicit inference URL.** Subscription/account checks and a successful fake-peer turn were insufficient evidence of correct inference routing.

Independent inspection of the pinned official 0.169.0 source confirms the correction:

- [`core/src/config/mod.rs`](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/core/src/config/mod.rs#L4061) passes the nonempty `cfg.openai_base_url` into the built-in provider constructor.
- [`model-provider-info/src/lib.rs`](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/model-provider-info/src/lib.rs#L757) passes that value into `create_openai_provider`; `to_api_provider` uses an explicit provider `base_url` before its authentication-dependent default.
- The same source defines `CHATGPT_CODEX_BASE_URL` as `https://chatgpt.com/backend-api/codex` and selects it by default for ChatGPT authentication. The corrected worker argument is exactly this subscription inference endpoint. The separate `chatgpt_base_url=https://chatgpt.com/backend-api` remains the account/backend management base.

**Routing-fix verdict: correct in source.** The fixed ChatGPT login, built-in provider, early rejection of API-key accounts, per-turn included-allowance/zero-credit checks, and removal of inherited OpenAI API-routing credentials remain in place. The correction does not introduce an API key, provider fallback or permission change. An external-peer regression now checks the actual child argv for the subscription inference URL and rejects the previous Platform URL; all **17 worker tests passed independently** after the change.

At this review point the installed root-owned worker still contained the previous URL, while a corrected candidate live probe was pending. The routing correction must be installed through the authorized operator step only after that probe passes, then verified with a fresh harmless phone turn. The observed connection failures do not establish paid API usage, successful model operation or command execution. Do not declare the live inference/approval/question commissioning gates passed from the source regression alone.

## Commissioning addendum — complete ordinary Code Mode runtime, 2026-11-15

A second commissioning regression was diagnosed after subscription routing was corrected: inference completed but no native command ran. The available account models select `tool_mode=code_mode_only` with `shell_type=unified_exec`. The earlier two-binary installation omitted the official `codex-code-mode-host` companion required by that ordinary model mode. This was a runtime packaging omission, not a reason to disable tools or replace model metadata.

Independent tracing of official 0.169.0 source confirms that [model tool mode overrides feature defaults](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/core/src/tools/mod.rs#L65). `CodeModeOnly` does not fall back to direct shell tools when its host is absent. The [upstream missing-host regression](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/core/tests/suite/code_mode.rs#L401) explicitly verifies this behavior. Native shell access is normally nested under `functions.exec`, so a probe must allow that route rather than insist on a directly advertised `exec_command`.

The [installation-context resolver](https://github.com/openai/codex/blob/rust-v0.169.0/codex-rs/install-context/src/lib.rs#L175) prefers a packaged resource host, then a host beside the executable. The managed flat runtime now adds only `/opt/codex-messaging/runtime/bin/codex-code-mode-host`. Default local hosting uses gRPC over stdio, requiring no new TCP listener or model/feature/permission override.

The coordinator verified the official 0.169.0 host archive against its published GitHub release digest, then extracted a regular 70,023,704-byte executable:

| Artifact | SHA-256 |
| --- | --- |
| Official host archive | `cbed6a8d25e8268792b757767fbc76d4c62e84bcf8ee4a63f97547f0de3aaceb` |
| Extracted host executable | `e9f2ef68671b2b6ac68902d19e8dafda3f5928e678ecf3f30c74b203a2c403ed` |

Independent source spot-review confirms that `cli.check_runtime` derives the sibling host path and applies the same root-owned parent/file, write-mode, executable-mode and hash checks before pairing/serving. The five-key configuration is unchanged. Ansible requires the third absolute controller-local artifact, pins the exact executable hash, guards its destination and copies it root-owned `0755`; the runtime whitelist admits this specific companion without permitting older bundled bwrap or arbitrary helpers. Ansible syntax checking passed independently. Ordinary model metadata, tools, environments, permissions and approval policy are unchanged.

**Candidate result reported by the coordinator: GREEN.** The complete staged runtime performed one actual harmless native command, completed its model turn and returned the exact verification summary, with zero automatic approvals. The patched installed bwrap remained selected on PATH. This demonstrates the corrected candidate's inference-to-native path; it does not by itself prove every native approval/question interaction.

At this review point production still held the older root-owned worker. The bounded production update copies only the corrected CLI/worker modules and pinned official companion, verifies integrity and restarts the relay without modifying token/enrollment/state. No source blocker was found for that authorized operator update. Confirm a fresh harmless phone turn after installation; do not substitute the staged candidate result for that production check. The coordinator additionally reports 38 offline tests and Ansible syntax checks passing. This reviewer did not read credentials, make another model call, install files or restart the service.

## Production acceptance — 2026-11-15

The operator applied the bounded update. The coordinator verified that installed CLI/worker bytes
match the tested source, all three runtime hashes and root ownership checks pass, pairing remains
present, and the service is enabled/active with zero automatic restarts. The owner then confirmed
that a fresh Telegram request to run `pwd` returned the home alias. This closes the earlier
production-versus-candidate gap for normal command execution. No credential or pairing identifier
was printed or committed, no Platform API key/fallback was introduced, and no global namespace
restriction or vendor profile was lowered. This final acceptance is coordinator/operator evidence;
the independent source reviewer did not repeat the live account, token or model operations.
