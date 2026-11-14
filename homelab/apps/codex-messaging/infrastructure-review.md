Purpose: record a source-based infrastructure review and the gates that prevent premature Codex messaging commissioning.

# Infrastructure review

Reviewed 2026-11-14 against `fb3120e` and the subsequent review fixes described below.
This review covers the deployment surface independently of its author. The reviewer previously
implemented the operations backend; this record is not an independent second audit of that backend.
No inventory, credentials, private recovery repository, host access, deployment, live capacity
measurement or network vulnerability scan was used. Local source inspection cannot establish the
installed host's security posture.

## Verdict

**CONCERNS: suitable architecture for a disabled, keyless source package; not approved for
installation, credential enrollment or operational use by this review.** Installation and each
commissioning stage still require the authorization and evidence in the
[implementation plan](../../docs/codex-messaging-plan.md#delivery-and-escalation-gates) and
[component runbook](../../docs/components/codex-messaging.md#commissioning-sequence-after-installation-authorization).

The first package creates no guest, network listener, operational SSH identity or publisher key.
The installed broker uses an empty registry, starts paused and hardcodes `allow_changes=False`
([cli.py](codex_messaging/cli.py#L125)); changing JSON or issuing `/resume` cannot enable it.
Host/VM reboot, standalone management-ownership proof and publication remain incomplete source
features, not commissioning evidence that an operator can supply to enable them.

The separate [dependency assessment](security-review.md) also blocks use of the pinned runtime
with real credentials. `RUNTIME_SECURITY_APPROVED=False` now prevents gateway, worker and login
startup in [cli.py](codex_messaging/cli.py#L237). Infrastructure limits or successful mock tests
cannot waive that source guard; a reviewed runtime decision and repeated tests are required.

## Findings and disposition

| ID | Severity / stage | Source finding | Required disposition |
| --- | --- | --- | --- |
| INF-01 | High before installation | The original playbook omitted reserved groups and fixed files, permitting unintended group access or overwriting unrelated files. The revised [preflight](../../ansible/playbooks/provision-codex-messaging.yml#L38) reserves launcher, units, configs, runtime namespace and metrics filename; rejects unmanaged groups, outsiders, links and directory drift; and checks globally unique positive role UIDs, unique reserved GIDs, private primary GIDs, fixed HOME/shell and supplementary memberships. | **Source fixed and re-reviewed.** Actual ownership/membership checks remain an installation prerequisite, not evidence obtained here. |
| INF-02 | High before starting services | The original units lacked explicit aggregate budgets and the broker created unbounded threads. | **Source fixed:** the [slice](../../ansible/templates/codex-messaging/codex-messaging.slice.j2#L5) caps CPU at one core, RAM at 1 GiB, swap at zero and tasks at 128, with narrower role/fd limits. [IPC admission](codex_messaging/ipc.py#L73) caps active handlers at 16. **Live acceptance open:** measure whether legitimate work fits without violating VM/host headroom. |
| INF-03 | Medium before starting services | Time-based idle retention does not bound caches, journals or an outage backlog. | **Partially fixed:** [gateway.py](codex_messaging/gateway.py#L15) caps outbox delivery at 128 replies and the main DB at 64 MiB; full backlog pauses new model/change admission and preserves local stop. WAL checkpoint/size settings are advisory, not an aggregate disk quota. **Open:** measured allowance, cache/journal/WAL high-water monitoring and safe pause/retention behavior before start. Preserve delivery cursor and uncertain job evidence. |

These are source risks, not claims that an account/group collision, memory shortage or disk
exhaustion currently exists. A marked rerun must not silently repair unrelated ownership or adopt
extra supplementary groups. Root ownership of a marker alone does not prove the entire tree safe.

## Capacity and concurrency

Current [PLAN](../../PLAN.md#L287) records VM 100 at **10 GB RAM**, superseding
[ADR-000](../../decisions/000-mgmt-vm.md)'s initial 4 GB allocation. Its 2-vCPU / 64-GB disk shape
is an initial baseline; current CPU allocation,
disk size/free space, swap and representative peaks are **unknown to this review**. Apophis is
documented with 32 GB and a required ≥3 GiB `MemAvailable` guardrail
([PLAN](../../PLAN.md#L39)). No new VM or resize is justified by source tests.

Admission is one chat and one active model turn; the RPC event queue is bounded at 256 and message
responses have byte/time bounds ([rpc.py](codex_messaging/rpc.py#L46),
[transport.py](codex_messaging/transport.py#L45)). Review fixes additionally bound broker connections
and pending replies and contain subprocess memory/tasks in one slice. Worker cache growth and total
disk use still require installed limits. All worker/sudo descendants must remain inside that slice.
Before start, measure idle, a representative
turn, the tool fixture, a poll outage and restart; record guest/host headroom, peak tasks, disk growth
and behavior at each limit. Resource exhaustion must pause/reject work and preserve journals.

## Network and privilege boundaries

- Outbound Telegram HTTPS long polling adds no public ingress or port forwarding, consistent with
  [ADR-003](../../decisions/003-remote-access.md). The transport fixes the production API host,
  disables inherited proxies/redirects and validates TLS. OpenAI authentication/model traffic and
  DNS remain outbound dependencies; loss of either must fail without billing/provider fallback.
- VM 100 is on the Home VLAN ([PLAN](../../PLAN.md#L84)); its existing placement follows
  [ADR-002](../../decisions/002-network-layout.md). It is not a new isolated network appliance.
  The gateway unit permits IPv4/IPv6 networking without an OS destination allowlist. Model-tool
  network denial and absence of native tools reduce exposure, but are not a host egress firewall.
  Actual service-context tests must prove the selected tools cannot reach private services or
  credentials. No generic network exception or provider override is justified by this review.
- `codex-telegram` owns intake/token state; `codex-worker` owns its fresh account cache;
  `codex-ops` owns the journal. Broker access requires both the expected Unix peer UID and enrolled
  user/chat IDs ([ipc.py](codex_messaging/ipc.py#L22)). The broker has no network and no capabilities.
  Other supplementary memberships would widen cross-service access and must be rejected.
- The gateway's exact no-argument sudo grant switches only to `codex-worker`, never root
  ([sudoers template](../../ansible/templates/codex-messaging/sudoers.j2#L1)). Its deliberate
  `NoNewPrivileges=false` exception and UID/capability transition must be tested under the installed
  unit. After sudo, the fixed launcher uses `setpriv --no-new-privs` before Python/worker execution.
  This source guard prevents the child from obtaining further executable-file privileges; it does
  not prove the actual service's mount/DAC isolation. The worker must not inherit gateway token,
  broker journal or interactive Simon credentials.
- Root-owned sticky worker directories protect the root-owned configuration while permitting its
  own cache. They rely on exclusive group membership. Final-file `O_NOFOLLOW`, ancestor ownership
  checks and runtime hashes fail closed ([cli.py](codex_messaging/cli.py#L53),
  [remote.py](codex_messaging/remote.py#L52)); installation must also refuse parent-path links/drift
  before writing. Source policy is not proof of the installed mount/DAC boundary.
- Metrics run as a fixed root oneshot with `CAP_DAC_READ_SEARCH`, private networking and numeric
  output. This remains a privileged cross-service bridge into the existing node-exporter textfile
  directory. Validate that directory's ownership, reserved filename, numeric-only output, stale
  heartbeat alert and inability to expose token/log/database contents before enabling its timer.

The root-owned `/run/codex-messaging` expectation is consistent with systemd's nested
`RuntimeDirectory=codex-messaging/broker`: only the innermost broker directory is assigned to the
service UID/group; the intermediate directory is not. This follows the
[official systemd.exec nested-directory example](https://www.freedesktop.org/software/systemd/man/255/systemd.exec.html#RuntimeDirectory=),
not a live ownership measurement. The metrics CLI requires root and atomically renames its own
root-created file, consistent with the reserved `.prom` file ownership check.

## Installation, rerun and rollback

The playbook is explicitly opt-in, checks Ubuntu/x86-64/Python prerequisites, installs root-owned
code and verifies pinned runtime/config digests. It stops an owned installation before replacement
and leaves units stopped/disabled. No Terraform change is required; this respects
[ADR-005](../../decisions/005-activate-ansible.md) and
[ADR-025](../../decisions/025-repository-boundaries.md).

Rerun is a maintenance stop, not a transactional release swap. A mid-copy failure can leave mixed
source; a first partial run deliberately lacks the ownership marker and needs local review. Record
the previous revision/config, retain the verified runtime distribution and notices, validate rendered
units/sudo policy and the complete ownership/membership inventory before start. Roll back by stopping
and disabling units and removing only this component's metrics/sudo grant; preserve private state
for review and revoke bot/account credentials through their owners. Do not remove shared paths,
accounts or groups automatically. Never treat service rollback as package-transaction rollback.

## Continuity and management failure domains

The service remains inside VM 100 on Apophis; losing that VM, its host or management connectivity
also loses phone control. Apophis's attended reboot/recovery work is still pending in
[PLAN](../../PLAN.md#L9). The management VM and its current hosting node must remain write/reboot
excluded. Unknown/stale ownership must fail closed, including aliases and migration. There is no
automatic HA claim: independent cold VM 128 is a manually activated recovery workstation, not a
second bot poller or a replica of this service's state.

The selected backup model is VM 100's encrypted daily PBS image on independent Oneill under
[ADR-012](../../decisions/012-backups.md). The existing VM restore drill predates this service.
The runbook correctly labels RPO ≤24h / RTO ≤1 day as **targets, not measured guarantees**. Before
live use, prove a fresh isolated restore of token/account state, settings and SQLite/WAL integrity,
with networking/units disabled before clone boot. Resume paused, invalidate approvals, reconcile
original job IDs and never run a restored second poller/dispatcher with live credentials. Include
revocation/re-enrollment and rolled-back-journal handling. Oneill/same-site and off-box key-custody
limitations remain the existing accepted/open project risks; this package does not resolve them.

Under [ADR-017](../../decisions/017-observability-continuity-by-default.md), VM monitoring alone is
insufficient: poll/auth/quota failure, stale heartbeat, bounded disk usage and uncertain operations
need service-specific visibility. Live alert integration and a service-state restore drill remain
commissioning prerequisites, alongside the source fixes above and the existing runtime/account
gates. No live-service completion or enrollment authorization follows from this review.

## Review verification

Source inspection and relative-link/whitespace checks passed. All 16 gateway tests passed,
including bounded outbox backpressure and stop behavior. The three local IPC tests could not bind
their temporary Unix sockets in this review sandbox (`EPERM`); they did not exercise the revised
handler behavior here. The coordinator must retain socket-capable suite evidence and synthetic
Ansible assertion/render validation before committing the fixes. No live systemd, sudo, account,
capacity or restore result is implied.
