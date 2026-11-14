Purpose: record the proposed security and cost boundaries for phone-driven homelab operations.

# ADR-028: Private Telegram access to Codex operations

**Date:** 2026-11-14

**Status:** Draft

## Context

Simon wants to investigate faults and request reviewed reboot/maintenance tasks from a phone using
the existing Codex subscription on the management VM. Public ingress, exposed infrastructure detail,
incremental API billing and unrestricted remote shells are outside the agreed scope. The
[research](../docs/codex-messaging-research.md) compares messaging alternatives; the
[implementation plan](../docs/codex-messaging-plan.md) owns the approved scope and acceptance gates.

## Decision

Prepare Telegram outbound long polling with one verified private user/chat initially. Separate
transport, restricted subscription-backed Codex worker, typed operations broker and eventual bounded
publisher identities. Give the model only registered diagnostics and plan preparation; a human's
single-use approval authorizes a concrete change. Preserve durable job identities across failures
and reconcile instead of replaying uncertain effects. Forbid management-VM and hosting-node reboots.

Pin the local app-server runtime and immutable configuration. Disable native tools and environment
access, require empty skills catalogs, reject API/provider overrides and fail closed on unknown or
exhausted quota/credit state. Verify account-side zero-spend controls before real model use.
Do not grant infrastructure/publication credentials until actual service and account isolation passes.
Use aliases and bounded summaries in Telegram; diagnostic context may reach OpenAI under Simon's
existing workflow. Bot messages are cloud conversations, not an end-to-end encrypted control channel.

The first source milestone installs only disabled, keyless services on the existing VM. It cannot
enable operations through configuration or Telegram. Deployment, device login, bot enrollment,
remote keys and a first operation have separate gates. Use the existing encrypted management-VM
backup model; prove isolated state recovery before live commissioning.

## Consequences

No inbound listener or new guest is required. Phone control depends on the management VM and the
selected messaging/OpenAI services. Transport filtering reduces accidental disclosure but does not
make arbitrary input safe. Dedicated identities, recovery evidence and pinned-runtime upgrades add
maintenance work. Unsupported repairs go to desktop review. The full operational service, publisher,
host/VM reboot support and measured backup recovery remain incomplete; this draft is not evidence
that deployment or credential enrollment has been approved.
