# Actual Budget (VM 127)

Private personal-finance server on Carter. The deployment is codified but is **not live** until the
operator reserves an address, provisions VM 127, completes first-run setup, and proves the PBS restore.

| | |
|---|---|
| Host / VMID | **carter** / VM 127 (Ubuntu 24.04) |
| Shape | 1 vCPU / 2 GB RAM / 10 GB ZFS disk |
| Packaging | pinned official `actualbudget/actual-server` Docker image |
| Data | `/opt/actual/data` on the VM, mounted at `/data` in the container |
| Access | `https://actual.<tailnet>.ts.net` through Tailscale Serve; no LAN/public listener |
| Authentication | Actual server password only; optional budget E2EE is required by this design |
| Backup | daily encrypted PBS image to oneill, 7 daily/4 weekly; manual ZIP before upgrades |

## Deploy

1. Reserve a free Home-VLAN address in UniFi and set `actual_ip` in the gitignored `all.yml`.
2. Create a tagged Tailscale auth key for `tag:actual`; keep `actual_enabled: false` for now.
3. From `homelab/ansible`, run:

   ```bash
   ansible-playbook playbooks/provision-actual.yml
   ```

4. Confirm the node is tagged `tag:actual`, disable key expiry, apply the versioned ACL, and open the
   printed HTTPS URL from an operator device.
5. Create a strong server password and store it in Vaultwarden. Enable budget E2EE with a different
   password and store that recovery password off VM 127. Losing it can make the budget unrecoverable.
6. Create or import the budget, then download a portable Actual ZIP export.
7. Set `actual_enabled: true`; run `provision-patching.yml`,
   `provision-maintenance-monitoring.yml`, `provision-monitoring.yml`, and `provision-glance.yml`.

Australian banks are not currently among Actual's documented built-in sync providers. Start with
OFX/QFX/CSV file import; do not add bank API credentials as part of this rollout.

## Backup and recovery

In Proxmox, add a **Carter-scoped** job for VM 127 to `pbs-oneill`: snapshot mode, daily at 02:45,
retention `keep-daily=7,keep-weekly=4`. Run it immediately and confirm `vm/127` appears in Glance's
Backup State after the hourly collector runs.

Restore drill:

1. Restore the newest `vm/127` PBS image to an unused throwaway VMID.
2. Remove its NIC before first boot so it cannot collide with production or join Tailscale.
3. Boot it and verify `/opt/actual/data/server-files/account.sqlite`, `user-files/`, and the Compose
   definition exist and are non-empty.
4. Destroy the throwaway VM and record the measured RTO in the runbooks restore-drill table.

For an application-level recovery, import the portable ZIP from Actual's file-selection screen. Before
every pinned-image upgrade, create a fresh ZIP because older clients cannot always load databases that
have already been migrated by a newer release.

## Operations

- Local health: `curl -fsS http://127.0.0.1:5006` inside VM 127.
- Container status: `cd /opt/actual && sudo docker compose ps`.
- Logs: `cd /opt/actual && sudo docker compose logs --tail=100 actual`.
- Upgrade: export the budget, change `actual_image`, review Renovate/release notes, then re-run the
  playbook during the monthly maintenance window. Never deploy a floating `latest` tag.

Related: ADR-023, ADR-012, ADR-015, ADR-017, ADR-018.
