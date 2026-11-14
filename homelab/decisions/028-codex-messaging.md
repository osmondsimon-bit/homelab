Purpose: record the accepted architecture for private Telegram access to normal Codex on the management VM.

# ADR-028: Private Telegram access to normal Codex

**Date:** 2026-11-14

**Status:** Accepted for source preparation; deployment pending

## Context

Simon wants normal Codex from a phone, including investigation, file changes, native tools,
approvals and questions, using the existing ChatGPT subscription and management workspace.
Telegram long polling fits a private, single-owner interface without public ingress. The user
explicitly rejected an earlier restricted operations-broker design.

## Decision

Use one Python standard-library Telegram relay and one local Codex app-server over stdio, running
as the existing `simon` user with HOME/workspace `/home/simon`. Retain normal Codex tools, settings,
permissions and repository rules. Relay native approvals and supported user-input questions;
correlate responses with the active thread/turn/request. Persist this relay's conversation and
invalidate stale approvals on failure. Do not replay uncertain commands.

Install root-owned code and pinned runtime under `/opt/codex-messaging`; prepend
`runtime/bin` containing official Codex 0.169.0 and patched static bubblewrap 0.13.1 to ordinary PATH.
Use `/etc/codex-telegram.json`, private `/var/lib/codex-telegram` state and one
`codex-telegram.service`. Leave the service disabled until separately approved installation,
console/private-chat nonce pairing and native host smoke testing are complete.

Use the existing ChatGPT login and subscription only. Force the intended provider/login path,
reject API-key/provider/credit fallback, and check usage plus account-side spend settings. No copied
login or new service identity is required. The [plan](../docs/codex-messaging-plan.md) owns acceptance
work and [runtime research](../apps/codex-messaging/runtime-revision-research.md) owns artifact and
advisory evidence.

One owner/private chat is verified by attended console nonce pairing. Telegram cloud chats are
not end-to-end encrypted. Prefer aliases and concise results, omit raw tool streams and apply
best-effort redaction. Normal Codex can send necessary diagnostics to OpenAI. Same-UID processes
can read relay token/state; instructions against doing so are guidance, not kernel separation.

## Consequences

No public listener or new guest is needed. Existing desktop credentials and permissions determine
Codex's authority, and normal project rules still require confirmations and preservation of work.
Phone and desktop changes share one working tree and need operator coordination. Thread persistence
does not guarantee transfer of an existing ChatGPT app conversation, rollback or exactly-once effects.
Outage or reboot of the management VM also removes this interface.

The retired broker, separate worker identity, custom operation/SSH registry, bounded source
publisher and native-tool restrictions are not part of this decision. Historical reviews do not
clear the revised relay. A patched helper was built in temporary storage; native namespace tests
were blocked by the research runner, so installed-host proof and all deployment/enrollment steps
remain pending. This ADR does not declare a live service.
