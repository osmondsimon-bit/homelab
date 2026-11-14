Purpose: define the selected scope and remaining work for private Telegram access to a normal Codex session.

# Codex messaging implementation plan

**Status (2026-11-14): source implementation verified. No installation, pairing, service start or real model
use is authorized by this document.** [ADR-028](../decisions/028-codex-messaging.md) records the
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
| Code/runtime | Root-owned `/opt/codex-messaging`; official Codex 0.169.0 and patched static bubblewrap 0.13.1 in `runtime/bin`, ahead of ordinary PATH |
| Private relay data | `/var/lib/codex-telegram`; local token, pairing and SQLite delivery/conversation state |
| Configuration | `/etc/codex-telegram.json`; no committed token or account cache |
| Entry commands | `check`, `pair`, `serve`; exact invocation in the component runbook |

The [runtime research](../apps/codex-messaging/runtime-revision-research.md) owns dependency fixes,
artifact provenance and known limitations. Codex's patched system helper must actually be selected;
an old bundled helper is not an acceptable fallback. Native filesystem/network execution must work
under the intended host policy. The temporary helper's version/help/static ELF checks passed, but
namespace smoke tests were denied by the research runner; target native execution remains open.

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

## Source verification and remaining acceptance

**Source complete:** 38 offline tests pass, including the HTTP/stdio task, native approval and result
flow, owner checks, questions/cancellation, restart and replay protection. Playbook syntax and both
templates verify with synthetic configuration; the rendered systemd unit verifies.
[The current review](../apps/codex-messaging/relay-review.md) records security/infrastructure findings
and their fixes. Earlier broker tests are historical, and source checks do not clear installed-host acceptance.

1. After separate installation approval, verify artifact hashes, existing-user paths/permissions,
   selected patched bwrap, target OS/vendor patch status, native sandbox behavior and resource/disk
   headroom. Leave the single service stopped/disabled until setup is complete.
2. Confirm existing subscription/provider and account-side spend controls without introducing API
   credentials. The operator supplies the bot token locally, completes attended console/private-chat
   pairing, and reviews the resulting numeric owner identity. No enrollment occurs in source tests.
3. Prove a normal native turn and native approval/question/interrupt round trips in the installed
   context, then attend the first service start. Check that private output is not streamed and a
   failed account/transport/helper check stops visibly rather than changing providers or authority.
4. Record backup/restore and outage behavior for relay state plus existing Codex state. Use the
   existing encrypted management-VM backup model; prevent a restored clone from polling concurrently.
   No new backup job or recovery guarantee is implied by source preparation.

Installation, pairing, account/model smoke, and first attended operation are distinct from the
current source work. No completed phase or live service is declared here.
