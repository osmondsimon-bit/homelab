# ADR-027: Home Assistant configuration lifecycle and mediated MCP boundary

**Date:** 2026-08-20
**Status:** Accepted (design; deployment deferred to private HA-15 commissioning)

## Context

The private home-automation project needs reviewable Home Assistant configuration and eventually
MCP access. Home Assistant also owns non-portable runtime state: integration/device registries,
Matter and Thread fabrics, credentials and UI configuration entries. Git cannot replace encrypted
HA backups for that state, while backups cannot provide a reviewable automation source.

Home Assistant's native MCP exposure list does not constrain the authority of its OAuth bearer
credential. Client-side confirmation is not a server-side authorization boundary, and the built-in
interface does not supply the durable, household-specific decision audit required for protected
actions. A future AI client must not receive a general HA bearer token.

## Decision

Use a hybrid authority model:

- The standalone private `home-automation` repository owns approved behaviour, tests, commissioned
  entity bindings, portable YAML and exact deployment manifests. It never stores credentials,
  pairing material, addresses or runtime databases.
- Encrypted HA native backups own UI integration entries, registries, Matter/Thread fabrics,
  credentials and runtime state. Daily partial backups include Core and every required add-on and
  dataset; material deployments take a named pre-change backup.
- This public repository owns only sanitised infrastructure: generic gateway provisioning,
  hardening, monitoring, backup/recovery and service documentation. Household intents, entity
  mappings and exposure manifests stay private under ADR-025.

Deployment is attended. A private manifest names exact source/destination digests; automation never
mirrors all of `/config`, reads `secrets.yaml`, edits `.storage`, or handles the HA database.
Repository tests and drift checks run before copy, then `ha core check`, then the narrowest supported
reload. A full restart requires separate approval. Config-check failure restores files before any
reload; post-reload behaviour failure uses an attended rollback. Emergency UI edits are recorded as
drift and reconciled before the next deployment.

Native MCP stays off during design. After private HA-15 commissioning it may expose read-only,
freshness-aware semantic mirrors with automatic exposure of new entities disabled. Native MCP never
exposes control, protected actions or configuration mutation.

Any later control uses a separate unprivileged LXC mediation gateway:

- The gateway holds a dedicated, revocable Tier 3 HA machine token in a root-readable runtime file;
  systemd passes it as a credential and the AI client never receives it.
- It is reachable only from registered LAN/Tailscale client networks over mutual TLS. Client
  identity comes from the verified certificate SAN, not request data; only a content-free health
  endpoint is anonymous. It has no direct internet ingress.
- A guest nftables rule limits inbound traffic to the gateway TCP port and limits the service UID's
  initiated egress to the exact HA IP and local HTTPS port. Systemd address restrictions provide a
  second layer. Repository/configuration authority is not available.
- Its small interface is freshness-aware semantic reads, explanations/history and named guarded
  intents. Raw entity, service, REST, template and configuration passthrough are forbidden.
- The first possible control pilot is lighting intents, ordinary reversible scenes and vacuum
  pause/dock. Covers, climate, modes and starts need later approval. Access, garage, water reopen,
  protection bypass and configuration remain prohibited initially.
- Structured audit retains request ID, client identity, semantic intent, redacted arguments,
  decision/reason, correlation ID and observed outcome for 90 days. Repeated prohibited attempts
  must alert before production; secrets and sensitive raw state are not logged. The current public
  playbook intentionally blocks production until HA-15 implements and validates that instrumentation.
- The kill switch stops the gateway path/service, revokes the HA credential and verifies the old
  credential and tools fail. Gateway loss affects MCP only.

Because the audit history is recovery data, classify the gateway as a small stateful LXC. Its
generic service is reproducible from Ansible, but its state receives an encrypted PBS image. Place
it on a host other than the PBS datastore host. After a restore, keep control disabled, revoke the
restored HA token, issue a new token, and complete a no-control recovery check before re-enabling.

The committed Ansible playbook is disabled by default and configures only an already-approved
guest. Guest creation uses the mechanism current under ADR-008 at implementation time: the interim
Ansible `pct` flow if migration has not happened, otherwise Terraform. The playbook's staged mode
installs a disabled, forcibly read-only service for recovery and kill-switch tests; production mode refuses to proceed
without infrastructure/security review, network registration, patching, monitoring, PBS backup
registration, backup freshness, restore drill and explicit operator approval. Deployment pins and
verifies the executable, private semantic manifest, server/client trust anchors, test-client
certificate and HA CA; production restarts the service and proves mutual-TLS identity plus negative
egress behaviour. Its attended approval is a short-lived runtime artifact bound to those exact
digests, rendered templates, host and guest placement, client networks, HA/gateway TLS paths, mode
and control setting. The selected host recomputes that canonical authority before mutation.
Mutation stops the gateway first and preserves a root-only prior-deployment archive for failure
rollback across the entire acceptance transaction; firewall rules are explicitly restarted.
A validated local HTTPS endpoint on HA is an HA-15 commissioning prerequisite.

HA-15 uses four distinct evidence environments: repository simulation; a fresh Synthetic HAOS VM
containing test-only helpers/templates; a disposable encrypted-backup recovery replica; and an
attended live hardware pilot. The synthetic VM never receives production backup state, credentials,
MQTT, a coordinator or a device-network route. The recovery VM is externally isolated before
restore, has no command authority and is destroyed after evidence; Home Assistant safe mode or
post-start disabling is not first-boot containment. The existing 2026-06-18 restore proves its
recorded backup/version, but a current deny-all restore must pass before command-producing private
configuration is deployed.

Credential placement follows ADR-018:

- human HA administrator password: Tier 1 Vaultwarden;
- HA backup encryption key: Tier 2 operator keychain outside the lab; and
- gateway HA token: Tier 3 scoped gitignored controller file, installed root-readable only.

## Consequences

- Git and HA backups have complementary, explicit authority rather than competing copies.
- The native MCP integration is useful for safe reads but is not misrepresented as authorization
  containment.
- Control requires another small service and therefore inherits ADR-012/015/017 monitoring,
  patching, backup, freshness, restore and documentation obligations.
- No gateway, MCP exposure, live HA change, guest identifier, address or placement is approved by
  this ADR. Those remain private HA-15 and infrastructure-review gates.
- No development or recovery HA guest is approved by this ADR. Host, storage, identifier, isolated
  network rules, monitoring and lifecycle remain an attended infrastructure-placement decision.
