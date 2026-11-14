Purpose: set up and operate the private Telegram relay to normal Codex after separate installation approval.

# Codex messaging

**State (2026-11-14): source preparation only. Nothing installed, paired or running is claimed.**
The [plan](../codex-messaging-plan.md) owns scope and remaining acceptance work;
[ADR-028](../../decisions/028-codex-messaging.md) records the selected same-user design.

The relay runs as existing `simon`, with HOME and authoritative workspace `/home/simon` and the
existing Codex subscription login/settings. It relays normal Codex tools, approvals and supported
questions over outbound Telegram long polling. Native Codex permissions and repository rules still
apply. One service, `codex-telegram.service`, uses root-owned code/runtime in `/opt/codex-messaging`,
configuration `/etc/codex-telegram.json`, and private state `/var/lib/codex-telegram`.

The [current source review](../../apps/codex-messaging/relay-review.md) covers security and
infrastructure; target installation and native execution remain unverified.

## Installation and commissioning

These are future operator steps, **after separate installation authorization**. No command below
was run against a real service/account during source preparation.

1. Verify the intended management VM, Tailscale/console recovery access, current OS vendor patches,
   backup state and resource/disk headroom. Review the exact source revision and rendered unit.
   The [playbook](../../ansible/playbooks/provision-codex-messaging.yml) stages the single relay as
   the existing user and leaves its service stopped/disabled. It creates no new identity or login.
2. Supply controller-local verified Codex 0.169.0 and patched static bubblewrap 0.13.1 binaries.
   Installation places both in `/opt/codex-messaging/runtime/bin`, root-owned and ahead of ordinary
   PATH. [Runtime research](../../apps/codex-messaging/runtime-revision-research.md) owns hashes,
   build provenance and dependency limitations. Verify the selected patched bwrap, not an older
   bundled/system fallback.
3. Run the local `check` as `simon`. It checks paths/configuration, pinned artifact hashes and
   private-state ownership; it **does not read actual auth state or make a model request**.
   Separately prove harmless native execution and configured sandbox restrictions on the actual
   host. The research runner denied namespace/UID-map setup, so its smoke result cannot clear this.
   A system service gets the user's HOME, SSH files and groups, but does not inherit an interactive
   shell's `SSH_AUTH_SOCK`. If existing keys require an agent, supply the established agent socket
   through a reviewed service environment/drop-in and verify it in this installed context.
4. Verify the user's existing ChatGPT login/subscription and account-side zero-credit/top-up
   settings in an attended setup step. If login is absent or expired, use normal Codex sign-in as
   `simon` after authorization. Do not copy another cache or create API credentials. Unknown,
   exhausted or paid-credit state must stop work rather than select a fallback provider.
5. Obtain the bot token through the operator's normal Telegram/BotFather workflow and write it
   locally to `/var/lib/codex-telegram/bot-token`, owned by `simon`, mode `0600`; keep its directory
   `0700`. Use a secure local editor/input method, not command arguments, Git, model chat or logs.
   The provisioning playbook does not fetch, copy or overwrite login/token secrets.
6. With the service stopped and no other poller running, run `pair` as `simon`. It prints a fresh
   nonce locally. Send `/pair <nonce>` from the intended **private** Telegram chat within ten
   minutes, then verify the recorded local owner. Pairing requires the nonce, not whichever sender
   arrives first. `enrollment.json` stores numeric `user_id`, `chat_id`, polling `offset` and
   `paired_at`; never enroll a group or infer authority from usernames.
7. In an attended window, test native approval/decline, supported questions, interruption, stale
   callbacks/messages, duplicate delivery, restart and account/transport failure. A normal turn may
   reach the model and requires separate live-use authorization. Only after these checks should
   the operator enable/start the service and review the first task.

Exact entry syntax (run as the existing user):

```bash
python3 /opt/codex-messaging/entry.py --config /etc/codex-telegram.json check
python3 /opt/codex-messaging/entry.py --config /etc/codex-telegram.json pair
python3 /opt/codex-messaging/entry.py --config /etc/codex-telegram.json serve
```

`serve` is normally systemd's job; running it manually while the unit is active would create a
second poller. The config contains only these absolute paths:

```json
{
  "user_home": "/home/simon",
  "workspace": "/home/simon",
  "state_dir": "/var/lib/codex-telegram",
  "codex_binary": "/opt/codex-messaging/runtime/bin/codex",
  "bwrap_binary": "/opt/codex-messaging/runtime/bin/bwrap"
}
```

Relay state also includes `relay.sqlite` and `relay.lock`. Do not edit enrollment or the delivery
cursor while running, and never commit these private files.

## Normal operation and privacy

Use one owner and one active turn initially. The relay preserves its own Codex thread across
messages; it does not promise to import an existing ChatGPT desktop conversation or app tools.
Coordinate phone and desktop work in the shared authoritative tree: preserve dirty/unrelated work,
follow AGENTS/runbooks and avoid concurrent change operators.

The phone shows Codex's native command/file/permission approval requests and supported questions.
Commands include their working directory; file approvals include the complete proposed patch.
Review the full displayed scope: a permission grant may cover the current turn. Approval responses
expire after ten minutes and must match the original request. An approval too large or unsuitable
for safe phone presentation is declined for local review, including any scope that would need
redaction. Prefer host aliases. Native
policy controls what asks for approval, rather than a separate relay operation catalog.

Send tasks as plain text. `/status` reports activity, `/pause` blocks new tasks, `/resume` permits
fresh tasks, `/stop` requests interruption and pauses, and `/new` starts a new conversation when
idle. After pause/recovery, send `/resume` in a later second than that pause/startup; an older queued
control cannot resume work. `/help` lists the controls. Question replies accept an option number or
plain text and expire after ten minutes.

Interrupting a turn is not rollback. After an outage, crash or missing completion, inspect actual
state before retrying commands. Do not automatically replay work or reuse old approval buttons.
Management-VM outage/reboot also removes phone access; use Tailscale/desktop/console recovery.

Telegram bot chats are cloud conversations, not end-to-end encrypted. Prefer aliases and concise
summaries; output redaction is **best effort** and raw tool streams are not forwarded. Anything
sent to the bot has already reached Telegram. Normal Codex can send necessary diagnostic context
to OpenAI. Do not send tokens, credentials, private addresses or raw logs through chat.

The relay and Codex share `simon`'s UID. Codex can therefore read relay token/state and other files
available to that user. Instructions not to do so are guidance, **not a kernel-enforced boundary**.
The recovery-repository prohibition still applies. If this accepted trust model changes, stop and
revise the design rather than claiming private-directory modes separate same-UID processes.

## Outage, recovery and rollback

Stop/disable `codex-telegram.service` before repairing relay files, changing pairing or restoring
state. Preserve SQLite with its coherent WAL state, enrollment and token as private data, and the
existing Codex HOME under the established encrypted management-VM backup model
([ADR-012](../../decisions/012-backups.md)). No new backup job or measured restore guarantee is
claimed. An isolated restore must keep polling/service networking disabled: never run two restored
instances with the same bot token. Invalidate pending approvals and review actual task outcomes
before resuming.

For rollback, stop and disable the single unit and revoke the bot token through its owner when
appropriate. Preserve private state for review; do not automatically delete the user's existing
Codex login, credentials or workspace, and do not undo or replay completed infrastructure changes.
For failures inspect safe local error categories and unit state; avoid pasting journal/database
contents into Telegram. A compromised token requires revocation/re-pairing, not a copied live state
on a second poller. Installed recovery and first-operation evidence remain pending.
