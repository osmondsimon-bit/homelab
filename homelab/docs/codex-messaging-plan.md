Purpose: define the selected scope and remaining work for private Telegram access to a normal Codex session.

# Codex messaging implementation plan

**Status (2026-11-15): running, enabled and privately paired.** Runtime integrity, existing
subscription admission and native sandbox checks pass. A real normal command turn succeeded,
and the owner confirmed `/status` and a fresh `pwd` result through Telegram.
[ADR-028](../decisions/028-codex-messaging.md) records the
accepted design; [the component runbook](components/codex-messaging.md) owns operator procedures.

## Selected outcome

Simon can converse with normal Codex from one verified private Telegram chat, including commands,
file work, native approvals and supported follow-up questions. Codex uses the existing management
user's HOME, subscription login, permissions, tools and authoritative `/home/simon` workspace.
[AGENTS.md](../../AGENTS.md), ADRs and relevant runbooks continue to govern work, destructive-action
confirmation, preserving existing changes, and documentation/commit/sync after verified tasks.

The user explicitly rejected the earlier restricted operations platform. Its separate worker/broker
identities, named-operation registry, custom SSH dispatchers, source publisher, native-tool removal
and helper-free runtime are retired. Existing source reports describe that earlier design and are
not acceptance evidence for this relay.

## Runtime and flow

Private owner → Telegram Bot API long polling → Python/SQLite relay → local Codex app-server stdio.
Approvals, questions and concise results return through the same relay. This adds no inbound
listener, forwarding rule, tunnel, new VM or hosted relay.

| Item | Selected implementation |
| --- | --- |
| Service/user | One `codex-telegram.service`, running as existing `simon` |
| HOME/workspace | `/home/simon`; existing Codex login/settings and authoritative repository |
| Code/runtime | Root-owned `/opt/codex-messaging`; official Codex 0.169.0 with matching code-mode host and patched static bubblewrap 0.13.1 in `runtime/bin`, ahead of ordinary PATH |
| Private relay data | `/var/lib/codex-telegram`; local token, pairing and SQLite delivery/conversation state |
| Configuration | `/etc/codex-telegram.json`; no committed token or account cache |
| Entry commands | `check`, `pair`, `serve`; exact invocation in the component runbook |

The [runtime research](../apps/codex-messaging/runtime-revision-research.md) owns dependency fixes,
artifact provenance and known limitations. Codex's patched system helper must actually be selected;
an old bundled helper is not an acceptable fallback. Native filesystem/network execution must work
under the intended host policy. The temporary helper's version/help/static ELF checks passed, but
namespace smoke tests were denied by the research runner; installed native checks now pass.
The installed host also needs an AppArmor attachment for the custom helper path. The optional
`codex_telegram_install_apparmor_profile` installs a distinct exact-path parent/child policy,
preserving child capability denial. Its installed hash and actual child label/capabilities are
verified. No global namespace setting or vendor profile is changed. The matching official
`codex-code-mode-host` is required alongside the main executable; Code Mode models cannot use
native tools if it is missing. Preflight and provisioning now require its pinned hash too.

## Authentication, authority and privacy

Use only the existing ChatGPT subscription. Force ChatGPT login and the built-in OpenAI provider,
reject inherited Platform/API routing and provider fallback, and verify account type plus known
included allowance and zero-credit state before turns. Unknown/exhausted usage or positive/unlimited
credit entitlement requires local review. Verify account-side zero balance and disabled top-ups;
a pre-turn check cannot reserve a shared account's allowance. No API-key or credit fallback is allowed.
No login cache is copied and no new worker identity is created.

Native Codex policy determines when an approval is requested. The relay presents each supported
request's command/files/permissions and reason, and binds an expiring reply to its original
thread/turn/request. It does not replace native approval with a runbook catalog or claim every normal
command requires a new phone button. Unsafe, unrepresentable or unsupported requests need local
review. A permission approval may explicitly apply to the current turn; it must not be shown as a
narrower command-only grant.

Pairing uses a short-lived console nonce and the intended private Telegram chat, with local owner
verification before persistence. Store numeric user/chat IDs; reject groups, foreign senders,
callbacks for other turns and stale/replayed approval replies. Start with one owner and one active
turn. Additional users require a separate authorization decision.

Telegram bot messages are cloud chats, not end-to-end encrypted. Prefer aliases and short summaries;
phone redaction is best effort and cannot make arbitrary prompts/logs private. The relay does not
forward raw tool-output streams. Necessary diagnostic context can reach OpenAI through normal
Codex. The existing private-recovery-repository prohibition still applies.

This is a **same-user** session: Codex can access files/credentials available to `simon`, including
relay token/state. Prompt guidance tells it not to inspect relay secrets, but that is not OS
isolation. Normal Codex sandbox/approval policy remains useful without creating a separate security
principal. This accepted tradeoff must remain explicit in setup and recovery documentation.

## Conversation and failure behavior

Persist the relay's thread ID, delivery cursor and pending-request correlation. This supports the
relay conversation; it does not import the current ChatGPT desktop conversation or all connected
app tools. Only one phone/desktop operator should change the shared workspace at a time; inspect
and preserve unrelated work rather than stashing/resetting it automatically.

Reject old messages after the accepted age window and expire approvals after ten minutes. Stop is
an interrupt request, not rollback: commands or remote changes may already have happened. Following
crash, lost completion or restart, invalidate pending approvals and require actual-state review;
do not replay a command because a reply was lost. A checkpoint/thread resume is conversation
continuity, not an exactly-once infrastructure transaction. Management-VM or internet outage removes
phone access; Tailscale/desktop recovery remains necessary.

## Verification and operating follow-through

**Source complete:** 38 offline tests pass, including the HTTP/stdio task, native approval and result
flow, owner checks, questions/cancellation, restart and replay protection. Playbook syntax and both
templates verify with synthetic configuration; the rendered systemd unit verifies.
[The current review](../apps/codex-messaging/relay-review.md) records security/infrastructure findings
and their fixes. Earlier broker tests are historical.

The [installed acceptance record](components/codex-messaging.md#installed-acceptance-record--2026-11-15)
owns the live evidence: root-controlled artifacts/source, actual helper/child enforcement,
subscription admission, paired-owner status reply, normal native command turn and phone result.
The initial inference URL and missing runtime companion were corrected before declaring normal
task execution operational. Existing normal tools/model settings and approval policy remain intact.

Continue exercising native approval/question variants, interruption, transport loss and long-running
remote jobs against safe fixtures. Existing source coverage is not a claim that every live variant
was exercised. Keep ordinary OS/runtime patch review and headroom monitoring, and use the encrypted
management-VM backup model. Prevent a restored clone from polling concurrently; an isolated restore
has not been measured for this new service. This records a working service, not completion of a
broader infrastructure phase.
