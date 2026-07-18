# Monitoring (CT 114)

Observability + alerting for the lab: metrics, dashboards, and proactive alerts so an
outage is caught in minutes rather than via "the internet's broken" (ADR-013). Pull-based
Prometheus, native packages, no Docker.

| | |
|---|---|
| Host / VMID | **oneill** (KAMRUI Essenx E2) / CT 114 (unprivileged LXC, Debian 12, `features nesting=1`) |
| IP / ports | `YOUR_MONITORING_IP` — Grafana `:3000`, Prometheus `:9090`, Alertmanager `:9093` (LAN/Tailscale only, no public exposure) |
| TSDB | Prometheus data on a quota'd ZFS bind-mount (`rpool/data/monitoring-tsdb`), ~30-day retention. **Not backed up** — history is non-critical, rebuilds from code |
| Exporters | node (`:9100` on apophis+oneill), pve-exporter (`:9221`), unpoller/UniFi (`:9130`), Home Assistant `/api/prometheus`, blackbox (`:9115`) — TCP-connect probe of the SLZB-06 Zigbee coordinator (`zigbee_coordinator_target`) |
| Alerting | Prometheus rules → Alertmanager → `am-ntfy.py` bridge (`127.0.0.1:9095`) → **ntfy**; apophis dead-man's-switch covers "oneill down" |

## How it's managed

Provisioned by `homelab/ansible/playbooks/provision-monitoring.yml` — run **without** `--limit`
(play 1 mints read-only PVE tokens on both hosts; play 2 builds CT 114 on oneill):

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-monitoring.yml
```

Prometheus + Grafana + Alertmanager are installed from official repos. Alert rules come from
`ansible/files/monitoring/alert-rules.yml` (committed); the am-ntfy bridge from
`ansible/files/monitoring/am-ntfy.py`. Secrets (Grafana admin pw, HA token, UniFi read-only
creds, PVE audit token, ntfy topic) are `vars_prompt`/`group_vars`, never committed (ADR-006).
Login to Grafana as `admin`; the password is only set when you type a non-blank value at the
prompt (blank = keep current). Reset: `pct exec 114 -- grafana-cli admin reset-admin-password '…'`.

> **Invariant:** dashboards + alert rules are code. Grafana has `allowUiUpdates: true` for live
> tweaks, but **export edits back to the repo** or they're lost on the next Ansible run.

`GuestDown` deliberately excludes `qemu/128`: `mgmt-vm2` is a cold secondary whose healthy state is
powered off. The Glance workload resource queries omit it for the same reason. VM 128's existence,
`onboot=0`, protection flag and activation test are verified by its provisioning playbook/runbook,
not by an always-up alert.

## Operations

Health checks, the alert-pipeline test (`amtool alert add …`), exporter/target troubleshooting,
and the dead-man's-switch all live in
[docs/operations/runbooks.md](../operations/runbooks.md#monitoring--alerting-ct-114-on-oneill--adr-013).

## Continuity

Stateless relative to Ansible (config + rules + dashboards in git) → recovery is a reprovision;
only the TSDB *history* is lost (acceptable, ADR-013). The PVE-exporter→apophis token wiring and
the dead-man's-switch are re-applied by re-running the playbooks. Single instance = a *visibility*
SPOF, not a production one.
