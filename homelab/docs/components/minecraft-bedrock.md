# Minecraft Bedrock (CT 129)

Private persistent family game server using the official native Bedrock Dedicated Server. This file
describes the accepted build; `PLAN.md` remains authoritative for whether the guest is live.

| | |
|---|---|
| Host / CTID | **Carter** / CT 129, unprivileged Ubuntu 24.04 LXC |
| Address | `YOUR_MINECRAFT_IP`, UDP `19132`; HTTP `9098` is health-only |
| Shape | 2 vCPU / 4 GiB RAM / 32 GiB thin ZFS root disk |
| Clients | iPad, Switch/Switch 2 on LAN, and Minecraft for Windows; remote iPad/Windows via Tailscale subnet route |
| Software | Official BDS `1.26.45.1`, URL and SHA-256 pinned in inventory |
| State | `/var/lib/minecraft` (world, allow list, permissions); explicit properties under `/etc/minecraft-bedrock` |
| Backup | Separate daily encrypted PBS stop-mode image to Oneill, 7 daily / 4 weekly; isolated restore drill passed 2026-08-28 (150 s) |

## Access and family controls

The server has normal outbound access for Xbox authentication and updates but no public inbound
path. The guest firewall default-drops inbound traffic and admits UDP `19132` only from the Home
subnet, which includes the two subnet routers' SNAT addresses. No port-forward, Cloudflare route,
Funnel, public DNS record, or Tailscale daemon belongs on the guest.

`online-mode`, `allow-list`, and LAN visibility are explicitly enabled. Players are ordinary
members, cheats are disabled, and only the parent gamertag is an operator. Gamertags live in the
gitignored `minecraft_allowlist` / `minecraft_operators` inventory lists. Remote child iPads must
use separate tailnet identities covered by the versioned single-address `udp:19132` grant; apply
that reference change in the Tailscale admin console before relying on remote child access. Never
sign them into the all-powerful operator identity.

Bedrock resolves operator permissions by XUID only after the account has joined. On a new server,
the parent joins once as an allowlisted member, then the operator reruns the playbook or sends the
documented `op` console command. The playbook reports only resolved counts and never prints names or
XUIDs.

Switch has no supported Tailscale client or dependable arbitrary remote-server entry. Local LAN
discovery is expected and was accepted without a pre-build proof. DNS-redirection and featured-server
proxy workarounds are not part of the supported service.

## Provision and update

First create the allocation without booting it so Proxmox generates the MAC:

```bash
cd ~/homelab/ansible
ansible-playbook playbooks/stage-minecraft-bedrock.yml --limit carter
```

Read the generated MAC from Carter's CT 129 network device, reserve the desired Home-LAN address in
UniFi, and copy that pair plus the private gamertag lists into the gitignored inventory. Then run:

```bash
cd ~/homelab/ansible
ansible-playbook playbooks/provision-minecraft-bedrock.yml --limit carter
```

The playbook creates the LXC under the current interim Ansible provisioning model, verifies the
official archive checksum, installs the native service and console FIFO, applies nftables, enrols
security-only patching, configures the stop-mode PBS job, and takes the first image.

BDS releases are deliberate changes because Bedrock protocol compatibility may change with client
patch releases. Before a bump: verify a current backup, resolve the new official URL, calculate and
review its SHA-256, update the three pinned variables together, run the regression test, re-run the
playbook, then join from iPad, Windows, and Switch. Do not deploy Preview builds.

## Health and operations

- Process/listener: `pct exec 129 -- curl -fsS http://127.0.0.1:9098/` must return `OK`.
- Logs: `pct exec 129 -- journalctl -u minecraft-bedrock --since today`.
- Console: `pct exec 129 -- /usr/local/bin/minecraft-console list` or
  `... /usr/local/bin/minecraft-console allowlist add GAMERTAG`.
- Restart: `pct exec 129 -- systemctl restart minecraft-bedrock`.
- Monitoring: `GuestDown` covers CT 129; `MinecraftUnavailable` checks the service plus bound UDP
  listener through the LAN-only health endpoint; Glance shows placement and health.
- Capacity: Minecraft is shed-first. Stop CT 129 before recovering critical guests on Carter if the
  host approaches the 3 GiB `MemAvailable` guardrail.

## Recovery

Restore the newest `ct/129` PBS image to an unused CTID with its NIC detached or on the isolated Test
network. Confirm `/var/lib/minecraft/worlds`, the allow list, permissions, pinned release, and service
startup before attaching a production NIC. A no-NIC restore to throwaway CT 130 passed on 2026-08-28
in 150 seconds; the binary, world, two allow-list entries, Bedrock service, and health endpoint were
verified before CT 130 and its disk were destroyed. CT 129 remained running and untouched.

## Related

[ADR-027](../../decisions/027-minecraft-bedrock-server.md) ·
[feasibility research](../minecraft-bedrock-server-research.md) ·
[operations](../operations/runbooks.md) · ADR-003 · ADR-012 · ADR-017.
