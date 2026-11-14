Purpose: define the implementation scope and acceptance gates for a private Telegram interface to Codex homelab operations.

# Codex messaging implementation plan

**Status:** Security hold following the expanded review on 2026-11-14. Source is prepared and tested,
but the current runtime is not cleared for real use. Gateway, worker and device-login entry points
fail closed pending a reviewed runtime revision. No deployment or enrollment has occurred.

**Date:** 2026-11-13. **Evidence:** [primary-source research](codex-messaging-research.md).

## Source milestone — 2026-11-14

[Application source](../apps/codex-messaging/README.md), the disabled keyless
[installation playbook](../ansible/playbooks/provision-codex-messaging.yml) and
[component procedures](components/codex-messaging.md) are prepared. All 86 behavioral tests pass,
including the actual pinned runtime with dummy credentials and a local scripted model. No paid
model calls, live account, real inventory, target or bot was used. Synthetic Ansible/unit/sudo
validation and independent security/continuity review cover this source milestone only.

Review findings about stale approvals/turn completion, asynchronous diagnostic delivery, broker
group access and safe installation reruns were corrected. Rendered systemd units and sudo policy
validate; the playbook syntax-check used synthetic inventory only. The rendered worker configuration
passes effective-feature checks and strict app-server initialization against the pinned binary
without a model turn. The initial review covered the keyless source commit. The expanded review
below adds a runtime security hold; installed-state restore remains an unproved live-service gate.

The installed entry hard-codes an empty registry and disabled changes. It cannot enroll keys or
turn operational through configuration. The remote journal, SSH dispatcher, service restart,
guarded apt and application-LXC reboot modules have fake-machine tests; they are not deployed.
LXC reboot uses the reviewed graceful no-kill path under the PVE config lock; `pct reboot` is not
permitted because its timeout path can force-stop. Exact installed vendor contracts need review
before enrollment. Host/direct-VM reboot, DNS probes, standalone-node management ownership proof,
immutable reference export, bounded publisher and operational-journal retention remain unavailable.
This milestone does not satisfy the full operational acceptance list below.

The worker rejects API accounts and unknown/exhausted allowances, plus positive/unlimited/unknown
credit entitlements. Account-side zero-credit and disabled automatic top-up controls must be
verified before real model use; a pre-turn quota check cannot guarantee shared account state stays
unchanged during a turn. [OpenAI credit behavior](https://help.openai.com/en/articles/12642688-using-credits-for-flexible-usage-in-chatgpt-personal-plans).

## Expanded security and infrastructure assessment — 2026-11-14

The [dependency/security assessment](../apps/codex-messaging/security-review.md) scanned 1,162
registry entries in the exact pinned Cargo.lock. It found 57 matching package/version entries,
including aliases and maintenance notices, not 57 proven exploitable vulnerabilities. A normal TLS
dependency matches a certificate-validation advisory; the pinned vendored bubblewrap source also
matches a sandbox-setup traversal advisory. Disabled native tools reduce the latter route, but do
not patch TLS. The lockfile is not the installed Linux SBOM, and remaining feature/call-path triage
is required. The latest release inspected is a migration candidate, not a cleared replacement.

`RUNTIME_SECURITY_APPROVED=False` now blocks gateway/worker/login before any account or token is
read. There is no configuration/environment override. The dummy-only preflight remains usable and
reports the separate runtime-security gate as blocked. Do not waive it or silently change the pin.
Select a reviewed replacement or upstream backport, establish relevant Linux build paths, resolve
material advisories and repeat protocol/isolation/billing checks before any real sign-in. Verify
target OS vendor-security status separately; Cargo advisory scanning does not assess sudo, Python,
OpenSSL/SQLite, systemd, OpenSSH or the running kernel.

The [infrastructure review](../apps/codex-messaging/infrastructure-review.md) found namespace/adoption
and resource-exhaustion risks. Source fixes reject conflicting paths/accounts/groups, shared UID/GID
aliases, group/identity drift and component-directory links before privileged writes. A component
slice caps aggregate CPU, RAM and tasks, with narrower service limits; the worker child sets
no-new-privileges after the fixed sudo transition. Broker connections and undelivered replies are
bounded, and gateway SQLite has a main-file size ceiling. These are containment limits, not measured
capacity or an aggregate disk quota. Disk/WAL/cache/journal high-water protection, target package
status, actual service containment and isolated restore remain start/enrollment gates.

Further first-party fixes make approvals show the canonical service, all affected targets, exact
package changes and separate reboot requirement. A plan too large or private-looking for chat has
no approval button and pauses changes. Parallel model requests cannot replace an outstanding
approval/question/diagnostic. New regressions cover these boundaries and blocked account entry.
Verification includes all 86 tests (actual pinned runtime, dummy/local model only), eleven synthetic
Ansible identity/path fixtures, rendered units/slice, sudo/shell validation and playbook syntax using
synthetic inventory. No live account, host package/status, deployment or recovery claim follows from
these checks. Nothing in the expanded review authorizes deployment or credentials.

## Outcome and agreed boundaries

Simon can send “Reboot x”, “Run maintenance tasks on y” or “Find out why z isn't working” from a
private Telegram chat. Codex investigates, proposes a concrete change, obtains one approval for its
scope, and reports verified results or a clear handoff. Accepted requests are not completed tasks.

- Telegram Bot API long polling, outbound only. No new public listener, tunnel or hosted relay.
- One enrolled user/private chat initially. Keep user identity separate from permission grants so
  adding another user later does not automatically grant administrator authority.
- Logical target names and concise results in Telegram. No raw diagnostic streams, addresses,
  credentials, files or private design documents. Necessary diagnostic context may reach OpenAI's
  model service. An address the operator types into Telegram has already reached Telegram.
- Existing ChatGPT/Codex subscription only. No Platform API usage, billing fallback, credit
  purchases or automatic paid escalation. Stop on unavailable authentication or exhausted usage.
- Separate bot-owned conversations are acceptable. Desktop conversation/app transfer is optional,
  not promised or required.
- Diagnosis through permitted tools is automatic. Changes require one approval of target, impact
  and plan. Materially changed scope needs fresh approval. Unfamiliar repairs go to a desktop session.
- Include services, guests and guarded Proxmox operations. Block reboots of the management VM and
  its actual hosting node, including aliases and indirect operations. Unknown ownership means stop.
- Routine OS/package maintenance only. Network changes, physical home controls, application/image
  upgrades, firmware, storage/backup changes, force resets, quorum changes and resource
  creation/deletion are excluded. Gateway self-modification and management-VM maintenance remain
  desktop work.
- One change operator at a time. Pause bot changes during desktop maintenance; read-only checks
  remain available. Preserve existing work; never automatically stash, reset or overwrite it.
- Management-VM/internet downtime may make the bot unavailable. Independent operator recovery stays
  necessary.

Current host/guest facts remain owned by [PLAN.md](../PLAN.md) and the
[operations runbook](operations/runbooks.md), not a second prose inventory in this packet.

## Selected architecture

Use **Python 3.12 standard-library code**, Telegram HTTPS APIs, SQLite and **Codex CLI 0.146.0
app-server over stdio**, with a narrow version-matched RPC adapter. Generate experimental-inclusive
schemas from that binary during implementation. Pin and verify the worker binary/version/digest;
do not modify Simon's interactive installation. Codex is Apache-2.0. No extra pip/npm library or
third-party bridge is selected.

The direct adapter avoids coupling to an SDK-packaged runtime and makes separate service identities
explicit. Existing bridge projects have not demonstrated all required privacy, operation-approval
and recovery properties. Version upgrades and new dependencies require review, not silent fallback.

Flow: private Telegram chat → coordinator ↔ local Codex worker; typed tool requests return through
the coordinator → local operations broker → restricted SSH target dispatcher → verified result.

| Principal | Owns | Enforced boundary |
| --- | --- | --- |
| codex-telegram | Bot token, inbox, conversation/approval routing | No SSH key or worker credential-file access; only fixed worker launch and broker socket access. |
| codex-worker | Dedicated ChatGPT login context and bot threads | No Telegram token, operations key/socket, general sudo or access to Simon's home/private inventory. |
| codex-ops | Dedicated automation key, private target registry, operation journal | Bounded typed requests from the coordinator's OS identity only; no model-supplied shell, script, path, URL or arbitrary arguments. |
| codex-publish | Write access to the bounded public-record surface and a public-homelab-only publication key | Separate from Simon and the operations identity; constrained public-tree/Git view, no private home or infrastructure credentials. |

Install root-owned code. Supervise coordinator and broker as separate systemd services. Launch the
worker through an exact root-owned sudo wrapper as codex-worker, with a clean environment and fixed
configuration. The wrapper cannot launch another program or accept caller-selected configuration.
Provide an immutable, revision-labelled export of reviewed public tracked reference documents,
excluding .git, ignored files and nested repositories. It is a reference view, never a deployment
tree. Live diagnostics come through the broker.

Use only the necessary account/thread/turn RPC methods and typed dynamic-tool responses. Never
relay arbitrary RPC from chat/model text: app-server also exposes methods with wider authority than
ordinary sandboxed turns. Support correlated user questions and interruption; unsupported forms or
permission requests stop safely rather than receiving blanket approval.

### Feasibility gate before infrastructure authority

Exact-release dynamic-tool/event compatibility and protection of the worker's own authentication
have **not been proved** by research. Read-only mode and a separate UID alone are insufficient:
app-server needs its credential, while model tools must not retrieve it.

First prove with the pinned runtime that every enabled model-controlled shell/native file/tool
route cannot read authentication, /proc/process environment, secrets, private trees or broker
credentials, or reach private services directly. Disable unnecessary native tools, inherited
plugins/MCP servers/hooks and provider overrides. If enforcement cannot be established, stop and
revise the design before installing keys or enabling operations. Do not upgrade silently, weaken
the sandbox, share Simon's full identity or switch billing methods to get past this gate.

Implementation evidence on 2026-11-14 found that an enabled native shell could read its synthetic
process environment despite a /proc deny rule. Credential-file and network denials alone therefore
did not pass the gate. The selected worker now has empty environment access, native features off,
and no skill/capability roots. Against the actual pinned runtime and a local mock model, injected
shell/image/agent calls are rejected, both skill catalogs are empty, forged skill reads fail, and
typed dynamic-tool callbacks work. The first deployment stage is strictly keyless/paused with an
empty operation registry; it cannot be enabled through /resume. Real-account feature/catalog
validation and installed service confinement remain commissioning checks before any operational
credential is introduced.

## Operation catalogue and execution boundary

| Operation | Reviewed implementation |
| --- | --- |
| Investigate | Compose registered host/guest/service, resource, package/reboot, bounded unit-log, DNS and health probes. Parameters are validated identifiers, not arbitrary shell, file paths or endpoints. |
| Restart service | Registered unit and target; preview dependency/impact, restart once, verify service and application health. |
| Graceful guest reboot | Revalidate current identity/ownership and exclusions, check recovery prerequisites, request graceful reboot, verify new boot identity and required services. No reset/stop fallback. |
| Graceful PVE reboot | One node only. Check management ownership, quorum, replication, backups, resolver failover and independent access according to the existing runbook. Show affected guests; verify recovery before another change. Never change quorum. |
| Routine OS maintenance | Reviewed apt recipes derived from the existing runbook: refresh/simulate, preview package/service impact and reboot requirement, revalidate, execute, verify. Unexpected removals, changed transactions, prompts or unsupported targets require a new plan/handoff. No automatic autoremove or appended reboot. |

Implement trusted dispatchers with a dedicated, independently revocable SSH key, verified host
keys, forced-command protocol, source restriction and no forwarding/PTY. The worker/coordinator
cannot read the key. Never accept unknown or changed host keys automatically.

Run LXC operations through their registered PVE dispatcher. Enrol a Linux VM's own dispatcher for
in-guest operations; do not assume guest-agent exec or SSH exists. Appliances get only explicitly
supported lifecycle/health operations. Never execute code from a model-writable repository with
operational authority. Runbook/dispatcher changes require review and deployment.

Broker preparation stores an immutable normalized plan: resolved target, runbook version, validated
parameters, preconditions, expected impact and verification. The coordinator renders that object,
not an arbitrary model-authored approval prompt. Dispatch revalidates current state and plan hash.
Package-service restarts must be included in impact analysis, not just the eventual reboot flag.

## Subscription-only authentication and privacy

Operator completes a fresh login in the dedicated service context; do not copy existing credential
caches or collect credentials through Telegram. Require forced_login_method = "chatgpt", the
approved built-in provider/endpoint and ChatGPT identity from account/read before dispatch.
Use an allowlisted launching environment; reject API keys, access-token/provider/endpoint overrides
and unapproved configuration. Stop on auth/quota failure. Test rejection paths without paid calls.
[Official authentication controls](https://developers.openai.com/codex/auth/).

The official SDK's supplied environment merges with the inherited environment; that alone would not
remove API credentials. This adapter must construct a clean process environment.
[Matching SDK launcher](https://github.com/openai/codex/blob/rust-v0.146.0/sdk/python/src/openai_codex/client.py).

Enrol sender/private-chat IDs through a local operator command. Verify both on messages, callbacks
and follow-up answers before contacting Codex. Reject groups and attachments initially.

Render concise Telegram progress, questions, approvals and outcomes. Replace known private
identifiers, detect address/MAC/token patterns and block unsafe output rather than dumping raw
exceptions/tool results. Unrenderable detail produces “details available locally”. This is not a
claim of perfect general-purpose redaction; raw outputs never stream directly to Telegram.

Keep configuration under /etc/codex-messaging/, per-principal state under
/var/lib/codex-messaging/, and sockets/locks under /run/codex-messaging/. Protect credentials,
SQLite/WAL files, conversations and logs with appropriate owner-only access. Live completed-task
transcripts/tool output expire after 30 days; credential-free outcome metadata after 90 days.
Never purge active/uncertain jobs. Close task threads and clean expired inactive UUIDs through the
pinned app-server's supported thread deletion method. Live deletion does not erase retained backups.
Service logs contain operational metadata, not prompts, tokens or raw diagnostics.

## Conversation, approval and crash behaviour

Commands: /new, /status, /pause, /resume and /stop. Persist chat/task/thread routing and active
turn/question IDs; do not select a desktop session implicitly.

- Persist each bot/update ID before advancing the polling offset. Duplicate delivery must not
  create another task.
- Use opaque random single-use approval callbacks bound to user, chat, task, immutable plan digest
  and pending request. Expire approvals after ten minutes; restart invalidates pending approvals.
- Messages older than ten minutes cannot start a change without fresh confirmation. Messages during
  work are explicitly routed as answers, follow-ups or proposed later tasks, never concurrent changes.
- Broker and target dispatcher durably record a job ID before execution. Duplicate IDs return
  existing state; reuse with different parameters is rejected.
- Run long remote work as supervised jobs that survive SSH disconnection. Reconnect by querying the
  original job ID, never submitting a replacement under a new ID.
- Reconcile journal, boot identity and actual health after uncertainty. Pause changes and require
  review of ambiguous work. Delivery offsets/RPC IDs do not establish end-to-end exactly-once effects.
- /pause prevents new changes and lets an active package step reach a safe boundary. /stop interrupts
  the model and prevents further steps; it does not kill dpkg mid-transaction or undo completed work.
- A successful reboot command acknowledgement is insufficient: new boot identity and health checks
  are required. Failed recovery is reported without automatic reset/quorum workarounds.

Use a cooperative change lock and documented desktop pause procedure. It cannot stop an
uncooperative manual operator; recheck live preconditions before dispatch and consequential steps.

## Authoritative tree and operation records

/home/simon remains the sole working/deployment tree. Worker reference exports cannot replace it.
Initial scope is infrastructure operations, not editing private design or unrelated repositories.

A narrow trusted repository-record helper runs as codex-publish, not Simon's unrestricted identity.
Its execution context exposes only reviewed public tracked files, selected Git metadata and the
explicit record/current-state write surface in the authoritative tree. OS permissions and service
confinement must deny private directories and all infrastructure/operator credentials. Give it a
separate write-enabled deploy key scoped to the public homelab repository; registering that key is
part of separately authorised enrolment. It accepts
only structured results and a bounded sanitised record/current-state update, checks expected HEAD
and base blobs, validates allowed paths and private-data exclusions, then stages explicit files for
a focused commit and push. Never accept arbitrary Git commands, paths, hooks or executable snippets
from the worker. Use controlled Git configuration and plumbing that bypass repository hooks,
filters and unapproved external commands; no operational credential or inherited agent socket may
reach this process. The confined view aliases the authoritative files, not a new deployment checkout.
If that boundary cannot be proved, publication remains a visible desktop handoff rather than
granting the helper broader access.

Preserve dirty/staged desktop work, branch choice and unrelated files. Unexpected PLAN layout,
ambiguous factual updates, private content or conflicting work leaves awaiting_documentation;
a failed push leaves awaiting_sync. Infrastructure completion and publication completion are
separate states: a publication failure cannot rerun maintenance or be silently called complete.
Read-only work with no affected source facts does not create empty commits.

## Bounded source scope

Implementation may create files only within these directories and edit the named existing files.
All paths here are relative to the Git root; every new file starts with its purpose.

- homelab/apps/codex-messaging/**: stdlib adapter, broker, dispatcher, repository helper, fixed
  launch/cleanup wrappers, protocol fixtures, tests and README. No third-party application dependency.
- homelab/ansible/playbooks/provision-codex-messaging.yml and
  homelab/ansible/templates/codex-messaging/**: deployment, accounts, pinned runtime, systemd,
  sudo/SSH boundaries, configuration templates, health and retention.
- Exactly one homelab/decisions/NNN-codex-messaging.md using the next unused numeric prefix and
  existing ADR template.
- homelab/docs/components/codex-messaging.md, this plan, and affected sections of
  homelab/docs/operations/runbooks.md, homelab/docs/tech-radar.md, homelab/PLAN.md,
  homelab/ansible/README.md, homelab/ansible/inventory/group_vars/all.yml.example and index.md.
- homelab/ansible/files/monitoring/alert-rules.yml: only service-health/stale-operation rules.
- Runtime records only as homelab/docs/operations/codex-maintenance-YYYY-MM-DD-JOBID.md, plus bounded
  updates to affected existing facts in homelab/PLAN.md. Validate date/job ID; do not accept a path.

No new Terraform resource/guest, network topology, unrelated repo, private design tree, interactive
agent config, existing key or credential-bearing recovery repository is in scope. Executors do not
read real inventory/credentials or deploy. Coordinator/operator handle approved configuration and
enrolment separately under existing project rules.

## Acceptance tests and commands

Use unittest, temporary SQLite/workspaces, fake Telegram HTTP, fake app-server stdio, fake clocks
and a recording broker/SSH adapter. For keyless native-tool isolation, exercise the actual pinned
binary against a local mock model HTTP service that emits fixture tool calls, with dummy credentials
and the selected filesystem policy. This is a separate test harness, not a provider override exposed
by the production launcher. No request leaves the harness for OpenAI/another paid service. Injection
points must not become runtime authentication bypasses.

Red/green behaviour tests cover:

1. Foreign senders/chats/groups and mismatched callbacks cannot reach Codex or dispatch anything.
2. Wrong/missing auth, API env/config/provider overrides and usage exhaustion stop without billing
   fallback or credit purchases.
3. Every enabled worker tool is denied credentials, /proc/environment, excluded trees, broker/key
   access, direct private services and arbitrary privileged execution.
4. A valid immutable plan executes once; expired/replayed/changed approvals and unsupported targets
   dispatch nothing. Live management-VM/hosting-node exclusions cannot be bypassed.
5. Duplicate delivery, crashes before/after dispatch, remote disconnection, lost replies and restored
   state reconcile without replaying side effects.
6. Pause/cancel and new messages respect safe package boundaries, single-change execution and expiry.
7. Telegram fixtures containing private addresses/tokens/logs/files are blocked or safely rendered.
8. Dirty index/tree, changed HEAD/base blobs, ambiguous PLAN, private data and push failures preserve
   work and leave visible publication states.
9. Fake maintenance/reboot scenarios cover preflight, approval, action, verified recovery and failure.

During implementation, from /home/simon:

    python3 -m unittest discover -s homelab/apps/codex-messaging/tests -v
    python3 -m compileall -q homelab/apps/codex-messaging
    codex app-server generate-json-schema --experimental --out /tmp/codex-messaging-schema
    git diff --check

Also validate rendered units with systemd-analyze verify, candidate sudo policy with visudo -cf,
and the playbook with ansible-playbook --syntax-check using synthetic credential-free configuration.
Do not use real inventory for executor tests. Schema/fake tests need no model calls. A later local
subscription-backed smoke test validates the actual account, tools and event flow.

## Delivery and escalation gates

1. Review this packet; implement protocol/identity/isolation tests first, without infrastructure
   credentials. Failed pinned-runtime isolation or protocol gates stop the work.
2. Implement and test the broker, registry, remote journal, approval binding, exclusions, safe
   publication and crash paths against fake targets.
3. Prepare Ansible plus service/operation/revocation docs. Include poll/auth failure, stale/uncertain
   job and service-health visibility, retention, rollback and backup decision. Do not mark live yet.
4. Independently review SSH/sudo/socket/filesystem/Git boundaries; run the project's security gate
   before configuration commits and continuity gate for the new state/backup decision.
5. Present tested source, rendered credential-free configuration, exact enrolment/impact and rollback
   for deployment authorisation. Source preparation does not authorise key installation, account
   creation, sign-in, Telegram enrolment or infrastructure changes.
6. After authorisation, confirm access and deploy keyless/paused services first. Before introducing
   a real account credential, prove native-tool/process/filesystem isolation against credential
   sentinels in the actual pinned runtime. Operator then creates the bot and completes direct
   ChatGPT sign-in. Run a subscription-backed model/tool smoke test against fake diagnostics with
   no infrastructure/publication credentials present; recheck real credential protection and
   absence of billing fallback. Only after those gates pass, enrol the restricted target key and
   publication key and enable registered diagnostics. Verify monitoring, then separately approve
   one non-critical target operation. Host reboot validation requires an attended window and
   independent recovery access; self/hosting-node reboot stays forbidden.
7. Prove protected-state recovery, update actual live status, complete the focused commit and sync.

State follows the management VM's existing protected backup model, with an explicit recorded
decision and continuity review; no new backup service is created. Restore drills use an isolated
scratch context, never a second live poller/dispatcher with the same bot/key. Restored service starts
paused, invalidates approvals and reconciles local/remote journals before changing anything.

Rollback stops/disables the gateway, revokes its dedicated key, retains audit state and restores
only its previous service configuration. It cannot undo completed package transactions. Existing
backup retention/off-site limits remain owned by their authoritative runbook.

Escalate for failed auth/protocol/isolation gates, unverifiable identity/ownership/recovery,
new privileges/dependencies, unfamiliar repairs, changed runbook semantics, unsafe publication,
ambiguous side effects or requested scope expansion. Do not weaken boundaries or substitute another
runtime/transport/model/billing method without a revised agreed design.

Authority: [AGENTS.md](../../AGENTS.md), [ADR-025](../decisions/025-repository-boundaries.md),
[ADR-018](../decisions/018-secrets-management.md) and the [shared workflow](agents/shared-workflow.md).
