# ADR-012: VM/LXC backups — oneill as the backup hub (local cross-host), off-site later

**Date:** 2026-06-16  
**Status:** Accepted

## Context

VM/LXC-level backups have been the standing **[High]** gap (PLAN.md) — config is already
backed up off-box to a private git repo (ADR-007), but nothing captures the guests
themselves. This is now the **Phase 3 entry task**: it must exist before any stateful
service (Monitoring's Prometheus TSDB, etc.) lands on oneill.

Constraints:
- **No dedicated storage** — only the SSDs in the two hosts (apophis ~500 GB; oneill 477 GB
  ZFS, ~455 GB free). No NAS until the new house (deferred).
- **Off-box is the rule:** backing a host up onto itself is worthless if that disk dies.
- Live guest data is small: ~22 GB used total (HA ~14 GB, mgmt-vm ~7 GB, the two CTs <1.5 GB),
  ≈10–13 GB compressed for a full of everything.
- Some guests are **stateless / Ansible-reproducible** (Technitium CT 111, Tailscale CT 110) —
  low backup priority. The crown jewel is **home-assistant** (irreplaceable config + the
  Zigbee2MQTT coordinator/device DB — losing it means re-pairing every Zigbee device).
- HAOS is a sealed appliance — no OS-level backup agent; use its own Supervisor backup system.

## Decision

**oneill is the backup hub** (it has the free space and is the newer ZFS box). Two layers,
**local cross-host only for now** — off-site (cloud) is deferred (see Consequences).

### Layer 1 — Home Assistant: native *partial* backup → share on oneill (primary for HA)
- Use HA's **Supervisor backup** (native scheduler, or `hassio.backup_partial` via the Core
  API) to take **partial** backups of what's irreplaceable: HA core config, the
  **Zigbee2MQTT add-on + data**, and other add-on configs. **Exclude media.**
- Keep the **recorder database** small via `recorder` `purge_keep_days` (~10–14d) — history
  is "nice to have," and it's the bulk of HA's footprint. Result: backups of ~tens–hundreds
  of MB, and **portable** (restore onto a fresh HAOS, not just this VM).
- Land them **off the apophis host** by adding an **SMB/NFS share hosted on oneill** (LXC) as
  HA *network storage* — scheduled backups write there directly. No SSH into HAOS.

### Layer 2 — Whole VM/CT images: Proxmox Backup Server on oneill (fast rebuild)
- Run **PBS** as an LXC on oneill (dedup + incremental + client-side encryption + retention).
- apophis guests back up **over the network to oneill** (off-box). Prioritise the stateful
  ones (HA, mgmt-vm); the stateless CTs are optional (they rebuild from Ansible).
- oneill's own guest (Technitium) backing up to oneill is same-host, but it's stateless, so
  acceptable; revisit when a stateful service lands on oneill.
- Indicative retention (tune): keep-daily 7, keep-weekly 4. Enable PBS encryption even though
  local. **Media is never backed up** (reacquirable; deferred to the NAS).

### Sizing
~15 GB for a full of everything today; ~30–50 GB with the above retention (dedup makes
increments tiny); under 100 GB well past Phase 3. Trivial against oneill's ~455 GB free.

### Build specifics (infra-designer review, 2026-06-16)

- **PBS** runs as an **unprivileged LXC** (CTID **112**, `YOUR_PBS_IP`) with its datastore as
  a **bind-mounted ZFS dataset** — not a VM, not privileged, not a loopback image. 2 GB RAM,
  2 cores, 8 GB rootfs. Dataset `rpool/data/pbs-datastore`, **quota 150 G**, `compression=lz4`.
- **Backup share** for HA backups runs as a **separate** minimal unprivileged LXC (CTID **113**,
  `YOUR_HA_BACKUP_SHARE_IP`) — 512 MB, 1 core, 4 GB rootfs. Dataset `rpool/data/ha-backup-share`,
  **quota 20 G**, lz4. **Build note (implementation chose Samba/CIFS over the NFS first proposed
  here):** HAOS mounts **CIFS** natively as network storage but has no built-in NFS client, so the
  share is **Samba**, scoped to a dedicated `habackup` user, LAN-only / not internet-exposed
  (`provision-ha-backup-share.yml`). Placeholder is `YOUR_HA_BACKUP_SHARE_IP` (was `YOUR_NFS_IP`).
- Reserve both new IPs in UniFi. (Unrelated tidy-up: PLAN.md still has an open item to
  *confirm* the Tailscale CT has a fixed reservation — that's a verify, not a change; it's
  active and stays.)
- **Build in two steps:** PBS first — provision LXC + dataset + quota → add as a storage
  target on apophis → smoke-test by backing up the **Tailscale CT (110)** first, then
  mgmt-vm (100), then **home-assistant (200) last**. NFS share second — provision → mount in
  HAOS as network storage → one manual partial backup, confirm it lands on oneill.
- **Cap `zfs_arc_max`** on oneill before Monitoring lands (ARC defaults to ~50% RAM) — watch-out,
  not a blocker.

## Consequences

- **Single-host failure is covered** (apophis dies → its backups are safe on oneill, and
  vice-versa for stateless guests). This satisfies "2 copies on 2 devices."
- **Not yet disaster-proof (fire/theft):** there is no off-site copy. Accepted, tracked
  deferral — the data is ~15 GB so an encrypted weekly sync from oneill to cloud (Backblaze
  B2 / S3) bolts on later as the "1 off-site" leg. Config already has an off-box copy via git.
- **oneill is a single SSD with no redundancy:** if oneill's disk dies, the backups *and*
  oneill's own guest are lost, but apophis's *live* guests keep running — you'd lose restore
  history, not production. The deferred off-site leg closes this; Phase 4 ZFS replication
  (ADR-009) further reduces it.
- New services to run on oneill: a **PBS LXC** and an **SMB/NFS share LXC**. Provisioning
  these is gated by the `infra-designer` review (CLAUDE.md) before build.
- Recorder-retention tuning trades history depth for small, fast HA backups — deliberate.
- **PBS encryption key/passphrase must be stored off-oneill** (captured by the ADR-007
  config-backup flow, or written down off-box). An encrypted backup whose only key lives on
  the same SSD as the backup is a false sense of security if that SSD is what dies.
- Complements ADR-007 (config) and is the durability prerequisite ADR-009/ADR-010 referenced
  (the password manager and apophis ZFS migration both wait on backups existing).
