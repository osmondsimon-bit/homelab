# ADR-011: DNS engine — Technitium, in a DNS-only role

**Date:** 2026-06-15  
**Status:** Accepted

## Context

Phase 2 calls for a network-wide resolver with ad/tracker blocking (scope refined to
the home VLAN — see the DNS-by-VLAN-role consequence)
(see `homelab/PLAN.md`). Two decisions are bundled here:

1. **Which engine** — Technitium DNS vs Pi-hole vs AdGuard Home.
2. **Which role** — DNS only, or DNS *and* DHCP.

Today UniFi runs DHCP for the network and hands out a public/UniFi resolver. Whatever
we deploy has to slot in without a disruptive cutover, and must be reversible if it
misbehaves — DNS is load-bearing for the whole house.

## Decision

**Use Technitium DNS Server, in a DNS-only role.** UniFi keeps DHCP; it simply hands
out the Technitium LXC as the network's DNS resolver.

### Engine: Technitium

| Engine | Why / why not |
|--------|---------------|
| **Technitium** ✓ | Full authoritative + recursive/forwarding resolver, not just a blocker. Per-network/per-client blocking, DNS-over-HTTPS/TLS upstreams, conditional forwarding, a proper API, and built-in DHCP if ever wanted. Single self-contained service. |
| Pi-hole | Great blocker, but DNS is `dnsmasq` underneath — thinner as a real resolver; config split across `dnsmasq`/`lighttpd`/FTL. |
| AdGuard Home | Close second; clean UI and DoH/DoT. Technitium edges it on resolver depth (zones, conditional forwarding) and a richer API, and keeps a clean DHCP upgrade path on one engine. |

Technitium also matches the direction in `docs/tech-radar.md` (already listed adopted
for Phase 2).

### Role: DNS only (UniFi keeps DHCP)

- **Blast radius.** If Technitium fails, recovery is flipping a *single* UniFi DHCP
  field (the handed-out DNS server) back to a fallback resolver. No DHCP outage, no
  lease confusion.
- **No overlap.** One DHCP authority (UniFi), one DNS authority (Technitium). Clean
  ownership; no split-brain leases.
- **Reversible cutover.** The handover is one DHCP setting plus a lease renewal, not a
  service migration. See the cutover runbook in `docs/operations/runbooks.md`.

Technitium *can* run DHCP, and the engine choice deliberately keeps that door open —
but taking DHCP off UniFi is a separate, higher-risk decision that we are **not** making
now. If we revisit it, it gets its own ADR.

### Placement

Unprivileged LXC, CTID **111**, provisioned by `ansible/playbooks/provision-technitium.yml`.

> **Placement update (2026-06-16):** the Intel NUC (**oneill**) arrived during Phase 2, so
> Technitium was deployed **directly on oneill** rather than apophis-then-migrate — the
> planned Phase 4 migration is moot. The original plan (apophis now → NUC in Phase 4) is
> kept below for context. DNS-only kept this trivial: it was a placement choice at deploy
> time, not a data migration.

Original intent: deploy on apophis now and migrate to the NUC in Phase 4 (like Tailscale,
CT 110) to free apophis for Plex.

## Consequences

- **DNS-by-VLAN-role (update 2026-06-16, learned the hard way).** Technitium serves the
  **home VLAN only** (the resolver's own subnet). **IoT + guest VLANs use the gateway (Auto)
  for DNS**, not Technitium, because: (1) they're isolated and can't reach a main-LAN resolver
  at `.6` — queries never arrive (confirmed by zero such clients in Technitium's logs), and
  (2) cloud appliances (Sensibo, Roborock…) hard-fail on blocklist NXDOMAINs. The original
  "resolver for all VLANs" framing was wrong for isolated/appliance segments; pointing them at
  Technitium silently broke their devices. Camera/management have no internet (no resolver).
  If guest ad-blocking is ever wanted, it needs a firewall exception (guest → `.6:53`) **plus**
  the guest subnet in Technitium's blocking-bypass — not worth it for now.
- **Single resolver = single point of failure for name resolution.** Mitigated three
  ways: (1) the LXC is lightweight and `onboot`; (2) UniFi can hand out a *secondary*
  DNS (e.g. `1.1.1.1`) so clients still resolve if Technitium is down — at the cost of
  bypassing blocking for those queries; (3) Phase 4 migration to the NUC + the cluster
  opens the door to a second Technitium instance later. The secondary-resolver trade-off
  (resilience vs. guaranteed blocking) is called out in the cutover runbook; default is
  **no public secondary** so blocking is never silently bypassed.
- Technitium needs a static LAN IP, reserved/excluded in UniFi (same discipline as the
  Tailscale CT). Clients only get the benefit once UniFi advertises it as their DNS.
- Blocklists, upstream forwarders (DoH/DoT), the blocking type, and the admin password
  are all applied by the playbook via the Technitium API (declaratively, from
  `technitium_*` group_vars) — no manual console setup. The config tasks run on every
  invocation and read the settings back to fail loudly if anything didn't apply, so the
  deployment is fully reproducible. Only the UniFi DHCP cutover remains a manual step.
- Local-only secrets posture holds: the admin password is prompted at runtime and set
  via the API (`no_log`), never committed (ADR-006/007).
- Keeping DHCP on UniFi means no per-client DNS identity by hostname unless we later add
  conditional forwarding or move DHCP to Technitium — accepted for now.
