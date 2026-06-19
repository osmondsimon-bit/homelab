# ADR-019: Physical infrastructure design surface (physical_infra/)

**Date:** 2026-06-19  
**Status:** Accepted

## Context

The homelab's logical infrastructure (VMs, LXCs, services, network config) is documented
and managed in `homelab/`. The *physical* layer — house structure, room layout, structured
cabling, lighting design, rack, and compute hardware — existed as a separate project built
with OpenCode/VS Code using specialised AI agents. Keeping it separate created a split that
prevents the agent from reasoning across both layers (e.g. generating HA area/device configs
from room data, or planning switch port assignments from the cabling schedule).

The physical layer is also inherently private (property details, room layout, device
locations) and must never be published to the public repo.

## Decision

Import and maintain physical infrastructure data under **`homelab/physical_infra/`**,
gitignored from the public repo.

**Directory structure:**
```
homelab/physical_infra/
  house/
    rooms.json              ← canonical room/level model (architectural interpreter output)
    schedules/
      data_schema.json      ← port schedule schema
      data_schedule.json    ← ethernet port schedule (eth01–eth21 + future)
      lighting.json         ← lighting design by room
    reviews/
      network_design_review.md
  network/
    vlans.yaml              ← VLAN definitions (mirrors live UniFi config)
    topology.yaml           ← switch, rack, APs, uplink, PoE budget
  compute/
    hosts.yaml              ← physical server specs + switch port assignments
  rack/
    layout.yaml             ← rack U-space assignments
  agents/                   ← agent system prompts from the original project
```

**Schema principle:** data is YAML/JSON (machine-readable first), not prose. Prose goes in
`notes` fields. This enables the agent to generate configs, port maps, and HA definitions
directly from the data rather than parsing markdown.

**Agent continuity:** the original specialised agents (architectural interpreter, lighting
designer, networking design advisor) are preserved in `agents/` with their system prompts.
The networking advisor prompt has been updated to include homelab context (existing VLANs,
monitoring stack, compute hosts) so future reviews are aware of the full picture.

**Gitignore:** `homelab/physical_infra/` is added to the root `.gitignore` re-ignored
section. It is never published. Local-only, backed up by PBS (mgmt-vm image, ADR-012).

## Consequences

- The agent can now reason across physical and logical layers: e.g. derive HA `areas.yaml`
  from `rooms.json`, validate switch port assignments against the cabling schedule,
  or generate VLAN configs that match the physical topology.
- Future work: IoT device inventory per room (`devices/iot.yaml`), HA area/device scaffold
  (`ha/areas.yaml`), and visualisation (diagram generation from YAML) are natural next steps
  once the house is live and devices are onboarded.
- The original house-build repo (`D:\opencode-workspace\house-build`) can be retired or
  kept as a Windows-side working copy — `physical_infra/` is the canonical version going
  forward.
- Any changes to the port schedule, rack layout, or VLAN config must be reflected here
  to keep the design surface accurate.
