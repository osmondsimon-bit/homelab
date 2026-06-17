# ADR-014: Homelab front-door dashboard — Glance on oneill

**Date:** 2026-06-17
**Status:** Accepted (infra-designer-reviewed 2026-06-17)

## Context

Phase 3's last service is a dashboard. PLAN named **Homepage (gethomepage.dev)**, but on closer
look the lab actually has **three distinct dashboard surfaces**, and conflating them was the trap:

1. **Wall tablet** (household control — lights/scenes/climate, glance at home state) → a **Home
   Assistant Lovelace** dashboard in kiosk mode. This is HA's job, not a startpage's, and it slots
   into the **Phase 6 HA-expansion** work (HACS, Mushroom/bubble-card, kiosk-mode, Fully Kiosk). Out
   of scope here.
2. **Deep graphs / history** → **Grafana** (already live, CT 114).
3. **Ops/admin front-door** ("is everything up, and where do I click to open it?") across ~8 web UIs
   on two nodes (Proxmox ×2, PBS, Grafana, Prometheus, UniFi, Home Assistant, Technitium console).
   This is the gap — and the only thing a startpage should own.

Homepage and Grafana are **not** redundant (graphs vs. launchpad), and Homepage **cannot** control
or "push into" Home Assistant — its HA widget only *pulls* a few stats to display read-only. Once the
wall tablet is correctly assigned to HA, the front-door is an **admin-only launchpad**, which lowers
the need for Homepage's turnkey service widgets.

## Decision (proposed)

Run **Glance** (`github.com/glanceapp/glance`) as the front-door, **not** Homepage.

- **Why Glance over Homepage:** Glance is a **single static Go binary + one `glance.yml`** — exactly
  the lab's native pattern (Technitium, Tailscale, Prometheus, Alertmanager, unpoller are all native
  binaries/packages, no Docker). Homepage is **Docker-first**; its only non-Docker path is a fragile
  `pnpm`/Next.js **source build** (Node drift, rebuild per upgrade, no packaged artifact) — *worse*
  for Ansible reproducibility than a container. Introducing Docker/containerd on oneill (the
  "simple services" node) for a convenience dashboard isn't worth it. **The Docker decision is
  deferred to Phase 5**, where the media stack's **Gluetun** (container-only by design) forces it
  anyway — confined to apophis.
- **What it does:** a `monitor` widget listing every service with a **status indicator + click-through
  link**, so the front-door also *links to Grafana* for graphs (no embedding — keeps Grafana full-fat
  and avoids enabling `allow_embedding`/anonymous auth). Panel-embeds can be added later if wanted.
- **Placement:** unprivileged LXC, CTID **115**, IP **`YOUR_GLANCE_IP`** (static-services band; reserve
  in UniFi *before* provisioning — the first IP chosen was withdrawn after it collided with a desktop's
  DHCP-preferred lease), on
  oneill. ~**512 MB / 1 core**, rootfs ~4 GB. Tiny footprint (Go binary, tens of MB). `features
  nesting=1` to match the oneill-CT pattern and avoid systemd-sandbox `226/NAMESPACE`.
- **Stateless:** no TSDB, no DB — config is the only state, and it's **rendered from Ansible** (the
  service list lives in gitignored `group_vars`; committed files use `YOUR_*` placeholders, ADR-006).
  A rebuild restores it fully from code; nothing to back up.
- **Binary:** fetched from a **pinned** GitHub release (`glance_version` in group_vars, currently
  `v0.8.5`) at provision time and extracted from the `glance-linux-amd64.tar.gz` asset. Pinned rather
  than `latest` because Glance is pre-1.0 and has renamed config keys between minor releases — a
  `latest` fetch would risk a config-incompatible binary on reprovision (infra-designer flagged this).
  Bumping = edit the var + re-run.
- **Access / security:** Glance has **no built-in auth** — same posture as Grafana/Prometheus:
  **LAN + Tailscale only, never public** (ADR-003). It serves only links/status, no secrets. Runs as
  a hardened systemd unit (`DynamicUser`, `NoNewPrivileges`, `ProtectSystem=strict`).

## Consequences

- Deviates from the tool named in PLAN (Homepage → Glance); PLAN updated. The trade-off is no
  first-party Proxmox/PBS/UniFi/HA tiles — for an admin launchpad, `monitor` status + links suffice;
  richer per-service numbers can be added later via Glance `custom-api` widgets.
- Keeps oneill **Docker-free**; the container-runtime precedent is taken deliberately in Phase 5 for
  Gluetun, on apophis, not snuck in here.
- New LXC → **infra-designer gate** (this review) + **/security-review** before marking Phase 3 done.
- The **wall tablet** (HA Lovelace kiosk) is recorded as Phase 6 HA-expansion work — not built here.
- Provisioned by a new `provision-glance.yml` playbook.
