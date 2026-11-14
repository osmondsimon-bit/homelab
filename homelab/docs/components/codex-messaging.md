Purpose: operate and commission the private Telegram-to-Codex service without granting premature infrastructure authority.

# Codex messaging

**State (2026-11-14): source only; no accounts, service, token, login or remote keys deployed.**
**Security hold:** the [expanded assessment](../../apps/codex-messaging/security-review.md) found
unresolved advisories in the pinned runtime. Gateway, worker and device-login commands now return
`runtime_security_review_required` before reading credentials. A reviewed replacement/build-path
assessment and repeated isolation tests must clear this gate before the sequence below can proceed.
The [implementation plan](../codex-messaging-plan.md) owns scope, permissions and acceptance gates.
[ADR-028](../../decisions/028-codex-messaging.md) records the proposed architecture;
[research](../codex-messaging-research.md) compares transports. Telegram long polling needs outbound
HTTPS, with no public listener, inbound forwarding or new VM. Bot chats are cloud conversations;
use logical aliases and curated summaries. Filtering is a guardrail, not a guarantee that arbitrary
text is anonymous. Never send credentials, raw logs, addresses or files through chat.

## Prepared installation

The [playbook](../../ansible/playbooks/provision-codex-messaging.yml) targets the existing `mgmt`
group. After separate deployment approval, the operator supplies verified numeric private-chat and
user IDs plus a local pinned runtime distribution. Public examples deliberately cannot enable it.
Do not discover enrollment by accepting whichever sender arrives first. Verify the intended account
locally and bind both IDs before staging configuration. Never paste a bot token into this repository,
a command line, a model conversation or Telegram.

The playbook creates locked `codex-telegram`, `codex-worker` and `codex-ops` identities, root-owned
code under `/opt/codex-messaging`, protected settings under `/etc/codex-messaging`, and separate
state under `/var/lib/codex-messaging`. Worker HOME and `.codex` have root-owned sticky group-write
directories: the worker can maintain its auth cache but cannot replace root-owned configuration.
The root manifest pins runtime, bwrap and configuration digests. Existing unmarked paths/accounts
are refused; a partially failed installation needs local review before adoption.

`codex-telegram` can invoke only the fixed no-argument `codex-worker` wrapper through sudo. This
requires `NoNewPrivileges=false` on the coordinator; its capability bounding set contains only
SETUID/SETGID, and the sudo rule grants no root command. This boundary needs commissioning proof.
The broker accepts only that coordinator's OS peer plus the configured user/chat identities. Its
registry is empty and cannot be enabled from Telegram or JSON. No SSH or publication identity is
installed, and no target dispatcher is deployed.

The three service units and metrics timer share a component slice. All remain stopped and
disabled after installation. No current exporter, firewall or monitoring rules are changed. The
metrics writer exports only fixed numeric fields to the existing node-exporter textfile directory;
missing/stale health becomes unhealthy. Alert integration is an operational-enrollment gate.

The proposed component slice caps the combined services and worker descendants at one CPU,
1 GiB RAM, no swap and 128 tasks, with narrower role limits. The broker admits 16 connections and
the outbox keeps at most 128 undelivered replies; a full queue pauses new work and approvals while
preserving `/stop`. The gateway's main SQLite file is limited to 64 MiB. WAL/checkpoint and worker
cache sizes still require an aggregate disk allowance/high-water stop and monitoring before start;
these settings do not constitute a filesystem quota or prove that the management VM has headroom.
The worker launcher applies no-new-privileges after sudo changes identity. All limits require
measurement and failure-path testing under the actual unit. See the
[infrastructure review](../../apps/codex-messaging/infrastructure-review.md).

## Commissioning sequence after installation authorization

This sequence is on hold until the runtime security gate above is cleared. Also verify current
target vendor package status for sudo, Python and its linked libraries, systemd, OpenSSH and the
running kernel. A source audit or mocked-model test cannot attest those installed packages.

1. Confirm Tailscale access, the intended management VM and fresh protected recovery state. Inspect
   the exact source revision, rendered units, sudo policy and binary hashes. Install with the
   explicitly enabled keyless variables from a locally protected, ignored extra-vars file.
2. Run the keyless preflight on the installed binary as the dedicated worker, with no real auth,
   bot token, target key or publisher key present. Repeat credential-sentinel and native-tool/skills
   catalog probes in the actual service containment. A failed check blocks enrollment.
3. Verify account billing controls locally: existing included subscription, zero credit balance and
   automatic top-ups disabled. The client requires subscription authentication and confirmed
   zero-credit entitlement, and rejects exhausted or unknown allowances. Shared account balances may change after a precheck;
   do not claim that a quota precheck alone guarantees no credit spending. If the account cannot
   enforce the agreed cost constraint, stop before model use.
4. Only after those checks, the operator completes a new device login directly as `codex-worker`
   using `sudo -u codex-worker /usr/bin/python3 -I /opt/codex-messaging/entry.py worker-login`.
   Do not copy Simon's interactive `.codex` cache. Recheck the effective feature table, empty skills
   catalogs and real credential protection. Model smoke tests use fake diagnostics, with no
   infrastructure or publication keys present. Auth, quota, tool or protocol ambiguity stops work.
5. The operator creates the bot through BotFather, revokes any exposed token, and writes its token
   locally to `/var/lib/codex-messaging/telegram/bot-token`, owned by `codex-telegram`, mode `0600`.
   Keep command/history/log capture off that secret. The playbook never reads or overwrites it.
6. Start the broker, then gateway and metrics timer in an attended keyless window. Prove foreign,
   group, stale and duplicate input handling; private replies; pause/stop; restart; rate limiting;
   and credential-free metrics. `/resume` must keep changes disabled. Stop again on any failed gate.
7. Operational enrollment is a **later source and deployment change**: prove actual management VM
   and hosting-node exclusions, enrolled read-only probes, target identity and pinned host keys,
   fixed dispatcher/sudo boundaries, package/LXC vendor contracts, safe Git publication, alerts and
   restore behavior. Host/VM reboot and unsupported diagnostics remain unavailable. Only then
   consider a separately approved non-critical service operation. Do not install an unrestricted key.

## Controls and recovery

`/status`, `/pause`, `/resume`, `/stop` and `/new` are handled locally without model usage. A new
conversation cannot abandon an active approval. Pause prevents changes but allows reads. Stop
prevents subsequent steps; an already-running apt process must finish safely. One approval applies
to one immutable plan and expires after ten minutes. Uncertain dispatch is reviewed under the
original job ID and is never replayed. Desktop change work requires pausing the phone operator.

Worker threads expire after 30 days when inactive. Intake IDs older than 90 days are removed while
preserving the delivery cursor. Cleanup runs serially while idle and holds if jobs are unresolved;
it cannot delete active work. Unsent outbox messages and uncertain work remain for local review.
Operation-journal retention and publisher integration remain blocked before operational enrollment;
no deployed operational data exists in this milestone.

The proposed durable state is covered by the existing encrypted management-VM PBS image under
[ADR-012](../../decisions/012-backups.md), with the current gaps and restore evidence owned by the
[backup runbook](../operations/runbooks.md#restore-drills-a-backup-you-havent-restored-is-a-hypothesis).
Use RPO ≤24 hours / RTO ≤1 day as commissioning targets, not measured guarantees. Before declaring
the service live, record a fresh backup and isolated restore test for token/auth caches, gateway and
broker SQLite/WAL state, settings and any later target journals. Verify coherent state with services
quiesced and SQLite integrity checks. Never start a second live poller/dispatcher using restored keys.
Disable network/units before booting the clone. Restore starts paused, invalidates approvals and
reconciles original local/remote job IDs; missing or rolled-back evidence requires manual review.
Tokens and access keys remain credentials in encrypted backups and need a revocation/re-enrollment
procedure. PBS's existing off-site/key-custody limits remain unchanged and are not resolved here.

For rollback, stop and disable gateway, broker and metrics timer; remove only this component's
textfile metrics and sudo grant; revoke the bot token/device login and any later dedicated keys
through their owners. Retain the private state for review under its retention policy. Do not remove
accounts or data as an automatic rollback, and never undo/replay a completed package operation.

For outages, inspect unit state and safe error codes locally. Do not paste journal/database contents
back into chat. Poll/auth failure or stale heartbeat requires local intervention; management-VM
outage also removes phone access. Existing Tailscale/desktop recovery remains necessary.
