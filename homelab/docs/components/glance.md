# Glance dashboard (CT 115)

The homelab **front-door**: a responsive two-page operator dashboard for degradation, service
launching, resource pressure, placement, backup/maintenance state, and version currency. It is an
at-a-glance **summary**, *not* the deep time-series/debugging surface (that's Grafana) and *not* the
wall-tablet home UI (that's Home Assistant). Admin launchpad across all three Proxmox nodes
(ADR-014).

| | |
|---|---|
| Host / VMID | **oneill** (KAMRUI Essenx E2) / CT 115 (unprivileged LXC, Debian 12) |
| IP / port | `YOUR_GLANCE_IP` / `8080` (HTTP) — LAN + Tailscale only, **no auth** |
| Engine | [Glance](https://github.com/glanceapp/glance) — single static Go binary, pinned (`glance_version`) |
| State | None — config is rendered from Ansible; nothing to back up |
| Data source | Prometheus (CT 114) via `custom-api` widgets — host/guest CPU·RAM·disk, maintenance intent, alerts, versions |
| Layout | **Overview:** core telemetry + host-grouped service launcher + wide capacity comparison + currency/maintenance/backups · **Infrastructure:** visual host and resource-ranked guest utilisation + fleet baseline |

## How it's managed

Provisioned by `homelab/ansible/playbooks/provision-glance.yml`:

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-glance.yml --limit oneill
```

The playbook creates the LXC, downloads the **pinned** Glance release (`glance_version`,
extracted from the `glance-linux-amd64.tar.gz` asset — a `.version` marker makes bumps
idempotent), **renders `/etc/glance/glance.yml` from the committed Jinja template
`ansible/templates/glance/glance.yml.j2`**, installs a hardened systemd unit (`DynamicUser`,
`ProtectSystem=strict`), installs the committed `operator.css` stylesheet, and starts it. The render
is **staged + validated** (`glance … config:print` on a `.new` file) and only **promoted** into place
if it parses — a bad render can't break the live dashboard. The template uses **custom Jinja
delimiters** (`<< >>` / `<% %>`) so Glance's own
Go-template `{{ }}` pass through untouched; real LAN values come from gitignored `group_vars`
(`glance_prometheus_url`, `glance_hosts`, `monitoring_ip`, `ha_ip`, `technitium_ip`, `pbs_ip`,
`gateway`) and committed files use `YOUR_*` placeholders (ADR-006).

> **Invariant:** change the **template** (`glance.yml.j2`) and/or the `glance_*` vars, then re-run
> the playbook — **not** the live `/etc/glance/glance.yml` (it's overwritten on the next run and
> won't survive a reprovision).
>
> **Scope:** keep this an operator *summary*. Deep time-series, network throughput, alert debugging,
> and capacity planning belong in **Grafana**. **Maintenance State** owns package-managed currency.
> **Version Currency** compares declared reproducible pins with upstream GitHub release tags for
> Glance, Vaultwarden, Jellyseerr, and Actual; uncollected runtime versions are explicitly described
> as such. Container version proposals still arrive through Renovate and are deployed manually.
> The top `Core telemetry` status deliberately covers Prometheus-backed signals only; native Glance
> service checks remain visible in the Service Directory and are not implied by that headline.
>
> **Capacity semantics:** local ZFS is shown once per node; the overlapping Proxmox `local` directory
> backend is excluded; the shared PBS datastore is deduplicated across cluster clients; and the
> replaceable media SSD appears only when its host filesystem metric exists. Bars show used + free
> capacity in a wide comparison grid and use 70% warning / 85% critical thresholds. Infrastructure
> workloads remain resource-ranked and collapse after five entries per host.
>
> **Pinned, deliberately:** Glance is pre-1.0 and renames config keys between minor releases.
> Bump `glance_version`, re-run, eyeball the page — don't track `latest`.

## Why Glance, not Homepage

Glance is a native single binary (fits the lab's no-Docker pattern); Homepage is Docker-first
and its non-Docker path is a fragile Node source build. The Docker decision is deferred to
the media phase (Phase 6 — Gluetun forces it on apophis). Full rationale + the three-surfaces analysis: ADR-014.

## Continuity

Stateless relative to Ansible (config in git) → recovery is a reprovision, RTO ~10 min. No
LXC-level backup needed (nothing to lose). No auth by design — exposure is limited to a
read-only links/status page on a LAN/Tailscale-only network (ADR-003).
