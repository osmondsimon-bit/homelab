# ADR-003: No direct internet exposure — use Cloudflare Tunnel or VPN

**Date:** 2026-06-12  
**Status:** Draft

## Context

Some services (e.g. Home Assistant) need to be reachable remotely. Opening ports directly on the
router exposes the home network to internet-facing attack surface.

## Decision

No services will have ports forwarded directly from the internet. Remote access will use one of:
- **Cloudflare Tunnel** — for HTTP(S) services where a public URL is acceptable.
- **WireGuard VPN** — for full network access or non-HTTP protocols.

The specific choice per service is deferred until that service is deployed.

## Consequences

- Cloudflare Tunnel requires a Cloudflare account and a domain; adds a dependency on Cloudflare.
- WireGuard requires a VPN server VM and client config on remote devices.
- Either option is significantly safer than open port forwarding.
- This decision should be revisited if self-hosted tunnelling (e.g. Tailscale, Netbird) becomes
  preferable.
