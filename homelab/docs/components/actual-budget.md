# Actual Budget (VM 127)

Private personal-finance server on Carter. **Live since 2026-07-15**; first-run security setup,
monitoring, encrypted PBS protection, portable export, and an isolated restore drill are complete.

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

1. Reserve `YOUR_ACTUAL_IP` for `YOUR_ACTUAL_MAC` in UniFi. Set these values as `actual_ip` and
   `actual_mac` in the gitignored `all.yml`; keep `actual_enabled: false` until the VM is healthy.
2. Apply the versioned Tailscale ACL, create a scoped auth key for `tag:actual`, and write only the
   key to `~/.tailscale-actual-authkey` on mgmt-vm with mode `0600`. Never commit the key. Delete the
   one-use file after the node joins; idempotent reruns do not require it while Tailscale is running.
3. From `homelab/ansible`, run:

   ```bash
   ansible-playbook playbooks/provision-actual.yml
   ```

4. Confirm the node is tagged `tag:actual`, disable key expiry, and open the printed HTTPS URL from
   an operator device.
5. Create a strong server password and store it in Vaultwarden. Enable budget E2EE with a different
   password and store that recovery password off VM 127. Losing it can make the budget unrecoverable.
6. Create or import the budget, then download a portable Actual ZIP export.
7. Set `actual_enabled: true`; run `provision-patching.yml`,
   `provision-maintenance-monitoring.yml`, `provision-monitoring.yml`, and `provision-glance.yml`.

Australian banks are not currently among Actual's documented built-in sync providers. Start with
OFX/QFX/CSV file import; do not add bank API credentials as part of this rollout.

## Backup and recovery

The deployment playbook adds VM 127 to the existing cluster backup job targeting `pbs-oneill`:
snapshot mode, daily at 02:30, retention `keep-daily=7,keep-weekly=4`. It also takes the first image
immediately when none exists. Confirm `vm/127` appears in Glance's Backup State after the hourly
collector runs.

**Proven 2026-07-15:** a data-bearing, client-side-encrypted image was restored to throwaway VM 197
on Carter with its NIC removed before boot. The account database, budget files, and Compose definition
were present; measured RTO was 155 seconds. VM 197 was destroyed and production VM 127 was untouched.

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
