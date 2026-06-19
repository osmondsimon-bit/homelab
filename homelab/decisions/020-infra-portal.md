# ADR-020: Homelab Infra Portal (CT 116)

**Date:** 2026-06-19  
**Status:** Accepted

## Context

`physical_infra/` (ADR-019) created a machine-readable design surface for the house
— rooms, port schedule, lighting, network topology, rack layout. The data is YAML/JSON,
which is precise but not scannable for design reviews, pre-move decisions, or as-built
verification. A visualisation layer is needed so upcoming decisions (ISP demarc,
Garage AP, IoT device placement) can be reviewed against the actual data rather than
prose notes.

The lab already has Glance (live status launchpad) and Grafana (metrics). A third
surface is warranted because the use case is fundamentally different: **static design
data** (floor plan ports, rack layout, lighting schedule) viewed as diagrams and
tables, not time-series panels or service links. This is the operator's planning
and as-built record, not a live dashboard.

## Decision

**Deploy a homelab infra portal as a static site on CT 116 (nginx, oneill).**

- **Generator runs on the mgmt-vm:** a Python script reads `physical_infra/` YAML/JSON,
  generates HTML tables + D2 diagram sources, calls `d2` to render SVGs, and outputs
  a single-page static site. A systemd timer triggers daily (and on demand via
  `systemctl start infra-portal-generate`).
- **CT 116 is a pure nginx file server:** the mgmt-vm rsyncs generated output to the
  CT's webroot via a dedicated unprivileged `portal-deploy` SSH user with access
  restricted to the webroot only. The CT runs no app logic.
- **D2** (diagram-as-code, Go binary) renders network topology, rack layout diagrams
  as embedded SVGs. Version is pinned in group_vars; same discipline as Glance.
- **Access:** LAN + Tailscale only. No Cloudflare Tunnel, no public exposure. Same
  posture as Grafana/Glance. Unauthenticated is acceptable within this strict boundary
  because the content is private-property data (floor plans, port schedule) but not
  security-sensitive (no credentials).

**Portal sections (Phase 1):**
1. Overview — summary stats, PoE budget, VLAN breakdown
2. Port Schedule — table colour-coded by VLAN, TBD rows highlighted
3. Network Topology — D2 SVG: switch, servers, APs, cameras, uplink
4. Rack Layout — D2 SVG: 12U wall-mount unit-by-unit
5. Lighting Schedule — per-room fixture count summary
6. TBD / Gaps — auto-detected null fields across all YAML/JSON files

**Portal growth path (future phases, no new ADR required while scope stays static-site):**
- As-built tracker (planned vs confirmed columns, populated after move-in)
- IoT device inventory per room as devices are onboarded
- HA area/device scaffold preview from `rooms.json`
- ADR index and phase tracker (if scope justifies, revisit Glance-vs-portal boundary)

**Glance vs portal boundary:** Glance = live status launchpad (metrics, service links,
alert summary). Portal = static design-data visualisation (physical layer, planning
decisions, as-built record). These do not overlap. Glance links to the portal via a
`glance_services` tile.

## Consequences

- CT 116 on oneill: reproducible-from-playbook, no PBS image needed. The source data
  (`physical_infra/`) is covered by the mgmt-vm PBS daily image (ADR-012) — that is
  where the real durability lies.
- Restore drill: destroy CT 116, re-run `provision-infra-portal.yml`, trigger the
  generation timer, confirm site returns. Record RTO in the runbook restore-drills table.
- Adding a port, updating rack layout, or recording an as-built change = edit the YAML
  file + trigger regeneration. The portal is a read-only view; all edits go to source.
- The `portal-deploy` rsync user is the only SSH surface added by this CT. Restrict
  the authorized_keys entry to the webroot and no shell features. Run `/security-review`
  on the rsync path before first deploy.
- CT 116 must be included in the Terraform import set at cluster scale (ADR-008,
  Phase 4) — same requirement as all other oneill LXCs.
- D2 version is pinned (`d2_version` group_var). Upgrade is a one-line group_vars
  change + playbook re-run, same as Glance.
