Purpose: describe the source-only Telegram commissioning package and its verification boundaries.

# Codex messaging

**Status: keyless source prepared; not deployed or operational.** The authoritative design and
remaining gates are in [the implementation plan](../../docs/codex-messaging-plan.md), with operator
procedures in [the component runbook](../../docs/components/codex-messaging.md).

Python 3.12 standard-library code provides outbound Telegram long polling, private user/chat
authorization, durable intake/outbox, a local Codex app-server client and a separately owned
operations broker. Every operational change requires a canonical plan and a single-use approval.
Requests never become shell commands. Lost dispatch replies reconcile the original job ID.

The installed entry supports **keyless mode only**: an empty target registry, paused changes,
no SSH identity, no publisher and no configuration switch to grant operational authority.
The playbook leaves all services disabled and stopped. It does not create a bot, install a token,
sign into OpenAI, copy interactive auth or enroll any remote key. Account creation and installation
are themselves gated by deployment authorization.

Source modules for the eventual remote broker, forced-command dispatcher, constrained apt
transaction and graceful application-LXC reboot are exercised against fake machines. They are not
enrolled by this package. Host reboot, direct VM reboot, DNS diagnostics, standalone-node management
ownership proof and the bounded Git publisher are unavailable. Their failures must remain visible;
they cannot trigger a generic shell fallback.

The worker requires the pinned Codex CLI `0.146.0`, a root-protected configuration, no inherited
provider overrides, ChatGPT subscription authentication and known allowance/zero-credit state.
Typed tools use `environments: []`. Native tools are disabled and skill catalogs must remain empty.
The mock-model fixture proves selected protocol/tool properties; it does not prove live-account or
systemd confinement. A filesystem-only profile failed to hide synthetic `/proc` process data and
must not be substituted for the selected tool restrictions.

From the repository root:

```bash
python3 -m unittest discover -s homelab/apps/codex-messaging/tests -v
python3 -m compileall -q homelab/apps/codex-messaging
git diff --check
```

The ordinary suite skips the real-runtime fixture unless explicitly selected. Socket tests need
permission to bind temporary Unix sockets and a loopback HTTP fixture. Run the full keyless gate
against the locally installed pinned binary:

```bash
CODEX_MESSAGING_TEST_BINARY=YOUR_PINNED_CODEX_BINARY \
  python3 -m unittest discover -s homelab/apps/codex-messaging/tests -v
python3 -I homelab/apps/codex-messaging/entry.py preflight \
  --binary YOUR_PINNED_CODEX_BINARY
```

The native fixture copies that binary and its adjacent `codex-resources/bwrap` into temporary
storage, uses dummy authentication and a local scripted model, and confines network access with
Landlock and seccomp. It requires Linux x86-64 and Landlock ABI 4. It performs no real model call
and installs nothing. Its provider override exists only in the fixture, never production settings.

No application package dependency was added. The separately installed Codex runtime is Apache-2.0
([upstream license](https://github.com/openai/codex/blob/rust-v0.146.0/LICENSE)); its bundled bwrap
uses LGPL-2.1-or-later ([upstream license](https://github.com/containers/bubblewrap/blob/main/COPYING)).
Retain upstream notices with the operator-supplied runtime distribution; this repository does not
redistribute the runtime binaries.
