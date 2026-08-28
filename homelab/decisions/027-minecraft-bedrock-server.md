# ADR-027: Private Minecraft Bedrock server on Carter

**Date:** 2026-08-28
**Status:** Accepted

## Context

The family wants a persistent Minecraft world for two children using iPads and Nintendo Switch 2,
with occasional desktop play by the operator. The service must work on the home LAN and may be
reached remotely through Tailscale, but must never accept public internet ingress. Ordinary outbound
internet access is required for Xbox authentication, downloads, and client-aligned updates.

Bedrock Dedicated Server is the first-party server matching the client mix. Switch supports Bedrock
LAN discovery, but the installed Switch-compatible client does not provide a dependable arbitrary
remote-server entry or Tailscale client. The operator accepted building without a separate pre-build
Switch proof; local Switch joining remains a post-deployment observation rather than a provisioning
gate. Unsupported DNS redirection and featured-server proxies are outside this decision.

## Decision

Run the pinned official Linux Bedrock Dedicated Server in unprivileged Ubuntu 24.04 LXC 129 on
Carter. Start at 2 vCPU, 4 GiB RAM, and a 32 GiB thin ZFS root disk. Carter has the best current CPU
and recovery-capacity balance; Minecraft is non-critical and must be stopped before recovery load if
the 3 GiB host-memory guardrail is threatened.

The native binary runs as a dedicated non-login user under a hardened systemd unit. Configuration
explicitly enables Xbox authentication, the game allow list, ordinary-member permissions, and LAN
visibility while disabling cheats. Only declared parent gamertags receive operator permission. BDS
releases are URL- and SHA-256-pinned and upgraded deliberately to remain compatible with clients.

Attach the LXC to the Home LAN with a pre-reserved MAC and static address. Its default-deny guest
firewall allows Bedrock UDP 19132 only from the Home subnet; the existing Tailscale subnet routers
SNAT authorised remote traffic into that same source boundary. A narrow tailnet grant gives child
identities only the Minecraft address and UDP port. Do not add a router port-forward, UPnP mapping,
Cloudflare route, public DNS record, Tailscale Funnel, or Tailscale node inside the guest.

The world is irreplaceable state. Protect it with a separate daily stop-mode PBS job to Oneill,
retaining seven daily and four weekly images. The brief overnight stop makes the image
application-consistent. Backup freshness is auto-discovered, but recovery is not considered proven
until an isolated restore drill succeeds. Do not replicate the guest or add it to Proxmox HA.

## Consequences

- The current hardware can host the server without a purchase, and failure of Minecraft cannot
  affect critical guest recovery if the shed-first rule is followed.
- iPad and Windows Bedrock clients can use the LAN address locally or through Tailscale remotely.
  Switch play is local-only and depends on LAN discovery in the actual installed client build.
- Xbox gamertags and child Tailscale identities remain private inventory/policy values rather than
  committed documentation.
- The server has no public attack surface, but authenticated play and maintenance retain ordinary
  outbound internet dependencies.
- Client auto-updates may force prompt attended BDS upgrades. Roll back by restoring the previous
  pinned release or the latest verified PBS image.
- The two local copies do not close ADR-012's site-disaster/off-site-backup gap.
