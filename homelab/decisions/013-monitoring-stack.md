# ADR-013: Monitoring stack — Prometheus + Grafana + Alertmanager on oneill

**Date:** 2026-06-16  
**Status:** Accepted (infra-designer-reviewed 2026-06-16)

## Context

Phase 3 prioritises observability. We want metrics, dashboards, and — importantly —
**alerting**, so an outage (e.g. Technitium DNS down) is caught in minutes rather than via a
"the internet's broken" complaint (continuity-reviewer flagged this for the single-instance
DNS). Scope of what to watch: the Proxmox nodes (apophis, oneill), UniFi, Home Assistant, and
key services (Technitium, PBS). This is the first genuinely stateful service on oneill — its
backup prerequisite (ADR-012, PBS) now exists.

## Decision (proposed)

**Prometheus + Grafana + Alertmanager**, in a single unprivileged LXC on **oneill**.

- **Stack:** Prometheus (scrape + TSDB), Grafana (dashboards), Alertmanager (routing). Pull-based,
  the homelab standard, matches the PLAN. **Native packages** from official repos (consistent with
  our LXC + Ansible pattern — no Docker layer).
- **Placement:** unprivileged LXC, CTID **114**, IP **`YOUR_MONITORING_IP`** (`.9`; reserve in UniFi), on oneill.
  ~**3 GB RAM / 2 cores**, rootfs ~8 GB, plus a **quota'd ZFS dataset for the TSDB** bind-mounted
  exactly like PBS (proven — plain `mp0`, no uid-mapping override needed). Core counts across
  oneill's CTs are intentionally oversubscribed (soft caps; these services are bursty, not sustained).
- **Data sources / exporters:**
  - `node_exporter` on **apophis + oneill** (host metrics).
  - `prometheus-pve-exporter` (Proxmox API — guests, storage, node health).
  - **UniFi Poller** (`unpoller`) for UniFi network/client metrics.
  - **Home Assistant** native Prometheus integration (`/api/prometheus`, long-lived token).
  - Technitium + PBS metrics — added later.
- **Scrape interval 30 s** (plenty for a homelab; ~halves TSDB size vs 15 s). **Retention ~30 days**,
  dataset quota ~**16–20 G** (revisit against actual growth). History is non-critical.
- **Dashboards + alert rules as code** — provisioned via Ansible files so a rebuild restores them;
  only the TSDB *history* is lost (acceptable; **not** backed up to PBS — recovery model honest).
  Prometheus uses **static `scrape_configs`** (not file_sd — no dynamic discovery needed at ~6
  targets). Grafana dashboard provider set **`allowUiUpdates: true`** so panels can be tweaked
  live — with the discipline that edits are exported back to the repo, else they're lost on the
  next Ansible run.
- **Alerting:** Alertmanager → **ntfy** (free, simple HTTP push to phone) for service-level alerts;
  `mail-to-root` as fallback.
- **Dead-man's-switch** (a monitor *on* oneill can't report oneill being down): a small **cron check
  on apophis** curls oneill's Prometheus `/-/healthy` every few minutes and, on failure, pushes its
  **own** ntfy alert — so "oneill / Technitium down" is still caught. (Optional later: an external
  heartbeat ping *from* oneill to catch a total-site/uplink failure — deferred to avoid a SaaS
  dependency for now.)
- **Access:** Grafana on the LAN (`:3000`); remote via **Tailscale only** (ADR-003, never public).
- **Secrets** (Grafana admin pw, HA token, UniFi read-only creds, PVE audit token) via
  `vars_prompt` / `ansible-vault` — never committed (ADR-006). Exporters use **least-privilege,
  read-only** credentials (UniFi read-only user; PVE token with `PVEAuditor`).

## Consequences

- First stateful service on oneill: the TSDB sits on its single SSD — metrics history is lost if
  oneill dies, but Grafana dashboards + Prometheus/alert config rebuild from code (recovery model).
- RAM: ~3 GB on oneill (16 GB, ~11 GB free) — fits alongside Technitium/PBS/share; watch when
  Homepage lands.
- New read-only creds to create: a UniFi local read-only user, a PVE API token (`PVEAuditor`), an
  HA long-lived token.
- New LXC → **infra-designer gate** (this review) + **/security-review** before marking done.
- Provisioned by a new `provision-monitoring.yml` playbook (+ a small role/play to drop
  `node_exporter` on the nodes).

## Build in two steps (per infra-designer)

1. **Core / scraping:** LXC + TSDB dataset + Prometheus + `node_exporter` (apophis + oneill) +
   pve-exporter + a basic Grafana dashboard. Confirm disk growth vs the estimate over a few days.
2. **Alerting + extra sources:** Alertmanager + ntfy + alert rules + the apophis dead-man's-switch,
   then the UniFi + HA exporters. Splitting avoids debugging alert-routing and exporter auth at once.

Provisioned by `provision-monitoring.yml` (+ `node_exporter` on the nodes). Run `/security-review`
before marking the Phase 3 monitoring item done.
