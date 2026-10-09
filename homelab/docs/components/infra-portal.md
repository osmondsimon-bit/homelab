# Infra Portal (CT 116)

Static-site visualisation of `physical_infra/` design data — port schedule, network
topology, rack layout, purchase checklist, lighting schedule, HA-05 construction gates, and TBD tracker. Generated on the mgmt-vm,
served from a lightweight nginx LXC on oneill.

**ADR:** [020-infra-portal.md](../../decisions/020-infra-portal.md)  
**Source data:** `homelab/physical_infra/` (gitignored, private — never public)  
**Generator:** `homelab/scripts/infra-portal-generate.py`  
**Provisioning:** `homelab/ansible/playbooks/provision-infra-portal.yml`

## Endpoints

| Surface | URL |
|---------|-----|
| Portal | `http://YOUR_PORTAL_IP` (LAN + Tailscale only) |
| Glance tile | Linked from Glance service status |

## Architecture

```
mgmt-vm
  physical_infra/*.yaml/json
        │
  infra-portal-generate.py  (reads YAML/JSON → HTML + D2 → SVG)
        │
  rsync via portal-deploy SSH key
        ▼
CT 116 (oneill): nginx → /var/www/portal/index.html
```

## Operations

**Trigger regeneration manually:**
```bash
systemctl start infra-portal-generate.service
journalctl -u infra-portal-generate.service -f
```

**Re-run provisioning (idempotent):**
```bash
cd ~/homelab/ansible
ansible-playbook playbooks/provision-infra-portal.yml
```

**After editing physical_infra/ data:**
1. Edit the YAML/JSON source file
2. Run `systemctl start infra-portal-generate.service` (or wait for daily timer)
3. Reload browser

## Backup decision

**Reproducible-from-playbook — no PBS image required.**

The generated static site is fully reproducible:
- CT 116: rebuilt in ~2 min from `provision-infra-portal.yml`
- Webroot content: regenerated in ~10 sec by the mgmt-vm generation service

**The source data (`physical_infra/`) IS backed up** via the mgmt-vm PBS daily image
(ADR-012) — it lives under `~/homelab/` on the mgmt-vm filesystem, which PBS images.
Losing `physical_infra/` would require a mgmt-vm restore, not a CT 116 rebuild.

## Purchase checklist

The **Purchases** tab reads the local-only `physical_infra/rack/purchases.yaml` source.
It separates phase-1 purchases, optional accessories, existing equipment, rack-bundle
inclusions, and future equipment. An item's checkbox means its full quantity is ready;
only phase-1 rows count towards the progress total. Owned rows start checked and can
be corrected in the browser. Included accessories are informational rather than separate purchases.

Each group has a `title`, `kind` (`required`, `optional`, `owned`, `included`, or `future`),
and `items`. Items have a unique stable lowercase `id`, `name`, `quantity`, optional
`notes`, and optional HTTP(S) product `url`. A `quantity_from` value of
`occupied_panels`, `spare_panels`, or `spare_rj45` derives the quantity from the current
two-panel/switch schedule instead of a fixed `quantity`.

Checkmarks are stored only in this browser, under the portal's origin. They survive
refreshes and regeneration while item IDs and the portal address stay the same. They
do not sync across devices, update YAML, or enter PBS backups. Clearing browser site
data resets them; a blocked-storage message appears if the browser cannot save them.
Keep item IDs stable when changing names or quantities, and recheck completed items
when their required quantities change.

Run `python3 homelab/tests/test-infra-portal-purchases.py` from the repository root to
check source loading, rendering, schedule-derived quantities, and browser persistence.
The tests require the existing Python/PyYAML runtime plus Node.js; production adds no dependency.

## Restore drill

1. `pct stop 116 && pct destroy 116` on oneill
2. `ansible-playbook playbooks/provision-infra-portal.yml`
3. `systemctl start infra-portal-generate.service` on mgmt-vm
4. Confirm site loads at portal IP
5. Record RTO in `docs/operations/runbooks.md` restore-drills table

## Security notes

- nginx serves on LAN IP only; no public exposure, no Cloudflare Tunnel
- `portal-deploy` SSH user: key-only, `no-pty`/`no-forwarding` flags in authorized_keys,
  write access to `/var/www/portal` only
- Content is private-property data (floor plans, port schedule) — not secret/credential
  data — acceptable on unauthenticated LAN-only nginx per ADR-020
- Run `/security-review` before committing the playbook

## Phase 2 (post move-in)

- Add `confirmed: true/false` fields to `data_schedule.json` entries → as-built diff view
- Populate `devices/iot.yaml` per room as devices are onboarded
- Generator adds per-room HA area scaffold tab
