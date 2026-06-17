# Glance dashboard (CT 115)

The homelab **front-door**: a single page of service tiles with up/down status and
click-through links. It is *not* a metrics tool (that's Grafana) and *not* the wall-tablet
home UI (that's Home Assistant) — it's the admin launchpad across the ~9 service UIs spread
over apophis + oneill (ADR-014).

| | |
|---|---|
| Host / VMID | **oneill** (NUC) / CT 115 (unprivileged LXC, Debian 12) |
| IP / port | `YOUR_GLANCE_IP` / `8080` (HTTP) — LAN + Tailscale only, **no auth** |
| Engine | [Glance](https://github.com/glanceapp/glance) — single static Go binary, pinned (`glance_version`) |
| State | None — config is rendered from Ansible; nothing to back up |
| Tiles | `monitor` widget: Grafana, Prometheus, Alertmanager, Proxmox ×2, PBS, UniFi, Home Assistant, Technitium |

## How it's managed

Provisioned by `homelab/ansible/playbooks/provision-glance.yml`:

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-glance.yml --limit oneill
```

The playbook creates the LXC, downloads the **pinned** Glance release (`glance_version`,
extracted from the `glance-linux-amd64.tar.gz` asset — a `.version` marker makes bumps
idempotent), renders `/etc/glance/glance.yml` from the `glance_services` list in
`group_vars/all.yml`, installs a hardened systemd unit (`DynamicUser`, `ProtectSystem=strict`),
validates the config (`glance ... config:print`), and starts it. The tiles' real URLs live only
in gitignored `group_vars`; committed files use `YOUR_*` placeholders (ADR-006).

> **Invariant:** add/change a tile in `glance_services` + re-run the playbook, **not** by hand —
> the config is overwritten on the next run and won't survive a reprovision.
>
> **Pinned, deliberately:** Glance is pre-1.0 and renames config keys between minor releases.
> Bump `glance_version`, re-run, eyeball the page — don't track `latest`.

## Why Glance, not Homepage

Glance is a native single binary (fits the lab's no-Docker pattern); Homepage is Docker-first
and its non-Docker path is a fragile Node source build. The Docker decision is deferred to
Phase 5 (Gluetun forces it on apophis). Full rationale + the three-surfaces analysis: ADR-014.

## Continuity

Stateless relative to Ansible (config in git) → recovery is a reprovision, RTO ~10 min. No
LXC-level backup needed (nothing to lose). No auth by design — exposure is limited to a
read-only links/status page on a LAN/Tailscale-only network (ADR-003).
