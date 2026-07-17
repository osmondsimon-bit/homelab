# ADR-017: Observability & continuity by default for new infrastructure

**Date:** 2026-06-19
**Status:** Accepted

## Context

The lab has good building blocks — Prometheus/Grafana/Alertmanager (ADR-013), Glance
(ADR-014), PBS + HA-native backups (ADR-012) — but adding a service has been ad-hoc.
Much monitoring already auto-covers new guests by regex:

- `GuestDown` fires on `pve_up{id=~"lxc/.*|qemu/.*"} == 0` (any new VM/LXC).
- Glance VM/LXC CPU/RAM/Disk panels include any guest via the `pve_guest_info` join
  (and the `guest:*` recording rules).
- `PVEStorageFull` + Glance "Storage Pools" cover any `storage/.*`.
- `NodeFilesystemSpaceLow` / `NodeMemoryHigh` cover any scraped node.

But the **manual gaps** are easy to forget and only bite later: the Glance
"Service Status" tile, version/release tracking, scraping a service's *own* metrics,
and — most importantly — the **backup + continuity decision**, which had **no
freshness signal at all** (a silently-failing backup surfaced only at restore time).

## Decision

**Every new guest / node / storage gets observability and a continuity plan as part
of provisioning — not as a later afterthought.** Concretely:

1. **Monitoring.** Rely on the regex-based auto-coverage above. If the service
   exposes its own metrics, add a `scrape_config` (and a dashboard). Add the service
   to the **data-driven** `glance_services` list with physical-node + VM/CT placement and, if it
   has GitHub releases, `glance_release_repos`. Comparable declared pins also join
   `glance_version_currency`. Update the `GuestDown` id-map comment.
2. **Alerting.** Confirm `GuestDown`/`TargetDown` cover it; add service-specific
   alert rules only if there's a meaningful failure mode beyond "process down".
3. **Backup — a deliberate decision** (keep the ADR-012 model; we do **not**
   auto-image everything). Choose one and record it:
   - *Reproducible-from-playbook* (most LXCs) — no image needed; the playbook IS the
     backup. Must still pass a reprovision drill.
   - *App-native* (e.g. HA partial backup) — configure + land it off-box.
   - *PBS image* (stateful guests not reproducible from code, e.g. mgmt-vm) — add to
     the Proxmox backup job.
   Then **register it in backup-freshness monitoring** so staleness is visible:
   `backup-freshness.sh` (provision-backup-monitoring.yml) auto-discovers PBS groups
   and the HA share; the `BackupStale`/`BackupAbsent` alerts, the Glance "Backup
   State" widget, and the Grafana "Backups & Recoverability" dashboard then cover it
   for free. A new *kind* of backup target (new datastore/share) means teaching the
   script that path.
4. **Continuity.** Run a restore/reprovision drill and record the RTO. "A backup you
   haven't restored is a hypothesis."
5. **Docs.** Update `PLAN.md` (infra table + single source of truth), add
   `docs/components/<svc>.md`, and tick the onboarding checklist.

The step-by-step is the **"Onboarding a new guest / node / storage"** checklist in
`docs/operations/runbooks.md`; this ADR is the principle behind it.

## Consequences

- New services are observable and recoverable from day one; silent backup failure is
  caught by `BackupStale`/`BackupAbsent` instead of at restore time.
- Adding a service to the dashboards remains a group_vars edit (`glance_services` with placement,
  `glance_release_repos`, and optionally `glance_version_currency`), not template surgery.
- The backup *decision* stays human (per ADR-012) — automation reports freshness, it
  does not silently start imaging guests. The cost is discipline: the checklist must
  be followed (CLAUDE.md points at it so agent-driven provisioning does too).
- Freshness metrics are filesystem-based (snapshot dir / file mtime on the hub), so
  they prove a backup *landed*, not that it's *restorable* — the restore drill (step
  4) remains the real proof.
- Builds on ADR-012 (backups), ADR-013 (monitoring), ADR-014 (Glance).
