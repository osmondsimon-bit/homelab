# ADR-003: Remote access — Cloudflare Tunnel for HA, Tailscale for admin

**Date:** 2026-06-12  
**Updated:** 2026-06-14  
**Status:** Accepted

## Context

Some services need to be reachable remotely. Opening ports directly on the router exposes the home
network to internet-facing attack surface. Two tunnelling options are in use or planned:

- **Cloudflare Tunnel (cloudflared)** — already deployed as the Home Assistant add-on. Proxies
  HA's HTTP interface through Cloudflare's network with no inbound ports required.
- **Tailscale** — planned for Phase 2. Full mesh VPN giving access to all homelab services and
  subnets without exposing anything to the public internet.

## Decision

No services will have ports forwarded directly from the internet. Remote access uses a hybrid approach:

| Access type | Tool | Rationale |
|-------------|------|-----------|
| Home Assistant (HTTP/S) | cloudflared add-on | Already working; nice domain URL; Cloudflare handles TLS |
| Proxmox UI | Tailscale only | Admin interface must never be public-facing, even via tunnel |
| SSH to any VM | Tailscale only | Non-HTTP; full network access |
| Future HTTP services (Vaultwarden, Grafana) | TBD — see consequences | Depends on RAM headroom |

**Rule:** Proxmox and SSH access go via Tailscale exclusively. Never routed through Cloudflare.

WireGuard (previously listed as the VPN option) is superseded by Tailscale — simpler to manage,
no server VM required, and handles subnet routing natively.

## Consequences

- cloudflared add-on is scoped to HA only. Fronting other HTTP services requires a standalone
  cloudflared LXC (~128 MB RAM) — deferred until Phase 3 when those services are deployed.
  Alternatively, Tailscale alone is sufficient for private access to those services.
- Tailscale LXC (~256 MB RAM) planned in Phase 2. All admin and non-HTTP access blocked until
  this is deployed.
- Two remote access paths in operation long-term (cloudflared for HA, Tailscale for everything
  else) — acceptable complexity given they serve distinct use cases.
- Cloudflare is a dependency for HA remote access. If Cloudflare has an outage, HA is
  unreachable remotely (local access unaffected).
