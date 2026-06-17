# Phase 3 — Foundation + observability (backups, monitoring, dashboard)

**Status:** ✅ Complete — 2026-06-17
**Phase gate:** `/phase-gate` — `doc-auditor` + `continuity-reviewer` + `/security-review` (no blockers)

## What was delivered

- **VM-level backups (ADR-012)** — oneill is the backup hub:
  - **PBS** (CT 112) — Proxmox Backup Server, datastore on a quota'd ZFS dataset (`rpool/data/pbs-datastore`, 150 G). apophis wired with a scoped token; **mgmt-vm (VM 100) imaged daily** off-box (keep 7d/4w), GC daily. CTs excluded — reproducible from playbooks.
  - **HA backup share** (CT 113) — minimal Samba/CIFS LXC for HAOS native backups (HAOS mounts CIFS natively; the ADR-012 NFS proposal was changed to Samba at build — recorded in ADR-012).
- **Monitoring (ADR-013)** — CT 114 on oneill, native packages, no Docker:
  - Prometheus + Grafana + **Alertmanager**; node/pve/UniFi(unpoller)/Home-Assistant exporters; TSDB on a quota'd ZFS dataset (~30 d, not backed up — history non-critical).
  - **Alerting:** Prometheus rules → Alertmanager → `am-ntfy.py` stdlib bridge (`127.0.0.1:9095`) → **ntfy** (ntfy has no native AM receiver). Starter rules: TargetDown / NodeFilesystemSpaceLow / NodeMemoryHigh / PVEStorageFull. AM cluster port disabled (single instance). **apophis dead-man's-switch** covers "oneill down". Verified end-to-end against ntfy.
- **Glance dashboard (ADR-014)** — CT 115 on oneill, **replacing Homepage**:
  - Single static Go binary + one rendered `glance.yml`, hardened systemd unit; stateless (config from Ansible). `monitor` widget = 9 service tiles with status + click-through, **links to Grafana**. All 9 tiles verified green (incl. self-signed HTTPS via `allow-insecure`).

## Key decisions / notes

- **Glance over Homepage** (ADR-014): keeps oneill **Docker-free** — Homepage is Docker-first and its non-Docker path is a fragile Node build. The Docker decision is deferred to Phase 5 (Gluetun forces it, on apophis). The **three dashboard surfaces** were untangled: wall tablet → Home Assistant Lovelace (Phase 6); graphs → Grafana; admin front-door → Glance.
- **IP discipline:** Glance's first IP (`group_vars`-picked) collided with a desktop's DHCP-preferred lease and confused UniFi — moved to the static-services band; **reserve static IPs in UniFi *before* provisioning**. Also scrubbed leaked last-octet fragments from committed files (ADR-006).
- **Agents/skills versioned** — `.claude/agents/*.md` + `phase-gate` skill published via narrow `.gitignore` exceptions (transcripts/memory/settings stay private).

## Carried into Phase 4 (from the gate reviews — clear before any new stateful service)

- **[High] HA native partial backup** — add the CIFS share in HAOS, schedule a PARTIAL backup (HA + Zigbee2MQTT pairings — the lab's only irreplaceable data), confirm a file lands on CT 113, then delete the interim local `vzdump-qemu-200` safety net. *Today HA's only backup is a same-host vzdump on apophis — the one uncovered failure class.* (continuity-reviewer)
- **[High] PBS encryption** — confirm whether client-side encryption is enabled on the apophis→PBS job; document the key location off-oneill (or enable + capture it). (continuity-reviewer)
- **[High] First restore drill** — `qmrestore` the mgmt-vm image to a throwaway VMID, verify, destroy; record the date. No restore has been tested for any tier. (continuity-reviewer)
- **Deferrals (tracked, no action now):** off-site copy of oneill backup data (ADR-012); CT 111 reprovision drill; patching ADR.

## Verification

- Monitoring: `amtool alert add` → ntfy push confirmed via the topic poll endpoint; rules loaded; Prometheus shows Alertmanager active.
- Glance: page + content endpoint return all 9 tiles, every status icon `--color-positive` (up).
- doc-auditor: 0 blockers (IP-leak scan clean); should-fix/nits resolved at the gate.
- continuity-reviewer: 0 blockers; carry-forwards above recorded.
