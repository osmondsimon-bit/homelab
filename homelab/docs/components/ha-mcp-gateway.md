# Home Assistant MCP mediation gateway

**Status:** Design-only. No guest, address, host placement or deployment is approved.

The future gateway is an independent authorization boundary between an MCP client and Home
Assistant. It holds the dedicated HA credential and exposes a small semantic interface; it is not a
general Home Assistant proxy and never edits configuration.

## Ownership and interface

Public Git owns the generic systemd hardening, configuration template, fail-closed Ansible gates,
monitoring and recovery procedure. The private `home-automation` repository owns household entity
bindings, semantic mirrors, named intents and their tests. Secret values and measured/audit data do
not enter Git.

Allowed interface:

- freshness-aware semantic reads;
- explanations and bounded history; and
- later, explicitly approved named guarded intents.

Forbidden interface:

- raw entity IDs or arbitrary HA service calls;
- REST, template or configuration passthrough;
- protected or configuration actions through native MCP; and
- direct access to the private Git repository or deployment keys.

## Infrastructure contract

The service will run in an unprivileged LXC on a host separate from the PBS datastore. Inbound is
limited to registered LAN/Tailscale client networks **and** authenticated with a dedicated mutual-
TLS client CA. The gateway derives client identity from the verified certificate SAN and rejects
caller-supplied identity. Only the content-free `/healthz` endpoint is anonymous. The nftables
policy admits only the gateway TCP port from registered client CIDRs and permits the service UID to
initiate traffic only to the exact HA IP and TLS port; systemd IP restrictions add defence in
depth. HA must therefore provide a commissioned, CA-validated local HTTPS endpoint before staging.
The guest receives security-only unattended updates without automatic reboot; ordinary updates
and service version bumps remain deliberate.

The application artifact and private semantic manifest must both be schema-validated and SHA-256
pinned. Root-readable source files hold the dedicated revocable Tier 3 HA token and TLS private
key; systemd passes them to the unprivileged process as credentials. The human HA administrator password remains in
Vaultwarden and the HA backup key remains in the external operator keychain. Neither is supplied to
the gateway.

Audit data is state: retain 90 daily rotations and protect it with an encrypted PBS guest backup.
`GuestDown`, a Glance health tile and a blackbox `/healthz` probe provide availability signals;
backup freshness is auto-discovered by the existing PBS collector. A process-health alert is
maintenance-only because the house continues without MCP.

Availability monitoring does not satisfy the accepted abuse-detection requirement. Production is
hard-blocked by `ha_mcp_gateway_prohibited_attempt_monitoring_implemented` until HA-15 supplies and
tests a non-sensitive denied/prohibited-attempt metric or log collector, a repeated-attempt alert,
and stale/absent instrumentation detection. The committed default is `false`.

## Staged deployment

`ansible/playbooks/provision-ha-mcp-gateway.yml` is disabled by default and does not create a guest.
Infrastructure review first selects the creation mechanism current under ADR-008, placement, VMID,
address, resources and network rules.

- `disabled`: validation/reporting only.
- `staged`: installs the pinned artifact and configuration but leaves the service disabled; use it
  for restore, audit, no-control and kill-switch tests. Staged configuration is forcibly read-only,
  even if a caller requests control.
- `production`: enables the service only after every ADR-017 continuity gate and explicit operator
  approval is recorded. Approval is a protected, maximum-30-minute runtime artifact bound to the
  exact guest/address, control setting, executable, semantic manifest and trust-material digests;
  its canonical authority digest also binds host placement, client networks, both TLS paths and all
  rendered configuration/service/firewall templates. The target host independently recomputes it;
  an inventory Boolean cannot approve deployment. It restarts the process, verifies installed
  digests, tests exact-port egress and proves both anonymous denial and certificate-derived identity.

Both mutating modes render and validate controller-side inputs first, stop any existing gateway,
archive the complete prior deployment root-only, then replace files. A failed mutation restores the
archive across the entire acceptance transaction. Rollback removes the failed managed tree first,
restores and verifies exact prior systemd enablement, and restarts only services previously active.
Firewall convergence uses an explicit restart so obsolete CIDRs or HA destinations cannot remain
active.

Control remains independently disabled unless the private HA-15 manifest and a later mediated
control approval exist. A production read-only service is not permission to enable control.

## Recovery and kill switch

After restoring the PBS image, keep the service disabled. Revoke the restored HA credential in HA,
issue a new dedicated token, replace the root-readable runtime file, prove the old token fails, then
run semantic-read and no-control checks before enabling the service.

For an incident, run the installed local disable command or stop the guest/network path, revoke the
HA token, and prove existing clients and the old token fail. Preserve only redacted audit evidence.
Gateway failure or deliberate isolation must not change HA automation, native device controls, or
Home Assistant's household dashboard.

The full accepted boundary is ADR-027. Operational commissioning remains deferred to private HA-15.
