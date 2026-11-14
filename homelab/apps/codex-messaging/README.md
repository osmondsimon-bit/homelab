Purpose: describe the private Telegram relay to a normal local Codex session and its source verification.

# Codex messaging

**Status (2026-11-14): source implementation verified; not installed, paired or running.**
[The plan](../../docs/codex-messaging-plan.md) owns the selected scope and acceptance work;
[the component runbook](../../docs/components/codex-messaging.md) owns setup and operation.

A Python 3.12 standard-library relay receives one paired owner's private Telegram messages through
outbound long polling and connects them to Codex app-server over local stdio. Codex runs as the
existing `simon` user in `/home/simon`, using that user's existing HOME, login, workspace, normal
tools and repository rules. Native command/file/permission approvals and supported questions return
to the phone. Approvals show the exact command/directory, full proposed patch or requested permissions;
scope that needs redaction or cannot fit safely is declined for local review. The relay keeps its
own Codex thread; transfer of an existing ChatGPT desktop chat is
not promised.

The prepared runtime is official Codex **0.169.0** plus patched static **bubblewrap 0.13.1**,
root-owned under `/opt/codex-messaging/runtime/bin` and prepended to the ordinary PATH. The
[runtime research](runtime-revision-research.md) records provenance and the outstanding native host
smoke test: this research runner denied namespace setup. Dependencies still need ordinary update
review; the dated Cargo advisory matches do not establish that every dependency is secure.

One `codex-telegram.service` runs the relay. Private state belongs in `/var/lib/codex-telegram` and
configuration in `/etc/codex-telegram.json`. Installation leaves the service disabled. Console nonce
pairing verifies the owner before serving; possession of a Telegram username or being the first
sender is insufficient. No token belongs in Git or a command-line argument.

Only the existing ChatGPT subscription is allowed: account/provider and usage/credit checks reject
Platform authentication, provider fallback and ambiguous/exhausted allowance. Check account-side
credit/top-up settings before live use. No new API key, paid fallback or copied login is required.

Telegram bot chats are cloud conversations, not end-to-end encrypted. Phone output uses concise
summaries and best-effort redaction; raw tool streams are not forwarded. The model can receive
necessary diagnostic context through normal Codex operation. **Same-UID processes can read the
relay's token/state**: instructions against doing so are guidance, not kernel separation.

Source checks from the repository root:

```bash
python3 -m unittest discover -s homelab/apps/codex-messaging/tests -v
python3 -m compileall -q homelab/apps/codex-messaging
git diff --check
```

Synthetic tests do not prove target namespace support, actual account cost controls, pairing or
recovery. No deployment, account enrollment, bot call or real model request is claimed by this
source milestone. The earlier [security](security-review.md) and [infrastructure](infrastructure-review.md)
reports are historical assessments of the retired broker design.

The [current source review](relay-review.md) covers the revised relay's security and infrastructure.
The 38-test offline suite includes an end-to-end HTTP/stdio fixture for a task, native approval and result;
it uses no real bot, credentials or model.
