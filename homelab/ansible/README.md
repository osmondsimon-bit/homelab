# ansible/

Ansible is the primary provisioning and configuration layer for the homelab
(see `../decisions/005-activate-ansible.md`). Playbooks run from the **mgmt-vm**
(the control node) and reach the Proxmox host over SSH.

## Bootstrap (one-time, on the mgmt-vm)

```bash
# 1. Install Ansible
sudo apt update && sudo apt install -y ansible

# 2. Create your local config from the committed templates (real IPs live here;
#    both files are gitignored and never published — see ADR-006)
cd ~/homelab/ansible
cp inventory/hosts.ini.example inventory/hosts.ini
cp inventory/group_vars/all.yml.example inventory/group_vars/all.yml
# then edit both, replacing the YOUR_* placeholders with your real IPs/hosts

# 3. Create an SSH key if you don't have one
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519 -C "mgmt-vm"

# 4. Authorise the mgmt-vm on the Proxmox host (asks for apophis root password once)
ssh-copy-id root@YOUR_PROXMOX_IP

# 5. Verify connectivity (run from inside homelab/ansible so ansible.cfg is picked up)
ansible proxmox -m ping        # expect: apophis | SUCCESS => "ping": "pong"
```

No Proxmox API token or per-container SSH keys are needed — lifecycle is driven via
`pct` over the single root SSH connection. See ADR-005 for why, and the planned
refinement to the `community.general.proxmox` API modules.

## Layout

```
ansible/
  ansible.cfg                  # inventory path, host-key prompt off, pipelining
  inventory/
    hosts.ini.example          # template — copy to hosts.ini (gitignored) + fill in
    hosts.ini                  # YOUR real inventory (gitignored, not published)
    group_vars/
      all.yml.example          # template — copy to all.yml (gitignored) + fill in
      all.yml                  # YOUR real defaults/IPs (gitignored, not published)
  playbooks/                   # one playbook per service
```

## Running a playbook

```bash
cd ~/homelab/ansible
ansible-playbook playbooks/<name>.yml
```

| Playbook | Provisions |
|----------|------------|
| `provision-tailscale.yml` | Tailscale LXC subnet router (prompts for the auth key) |
| `provision-technitium.yml` | Technitium DNS LXC, DNS-only resolver (prompts for admin password; ADR-011) |
| `provision-pbs.yml` | Proxmox Backup Server LXC on oneill — backup hub (prompts for admin password; ADR-012). Run with `--limit oneill` |
| `provision-ha-backup-share.yml` | Samba LXC on oneill for HA native backups (prompts for share password; ADR-012). Run with `--limit oneill` |
| `install-node-exporter.yml` | Installs node_exporter on the Proxmox hosts (ADR-013). Runs on both hosts |
| `provision-monitoring.yml` | Monitoring LXC on oneill — Prometheus + Grafana + Alertmanager + exporters (mints read-only PVE tokens; prompts Grafana pw, blank=keep; ADR-013). Run **without** `--limit` (play 1 hits both hosts) |
| `provision-glance.yml` | Glance dashboard LXC on oneill — front-door launchpad, pinned Go binary (ADR-014). Run with `--limit oneill` |
| `provision-patching.yml` | Unattended **security** upgrades on all guest LXCs (discovered via `pct list`) — no auto-reboot, midday-local timer, ntfy on failure (ADR-015). Run on both hosts (no `--limit`) |
| `provision-backup-monitoring.yml` | Backup-freshness textfile collector on the hub (oneill) — hourly timer writes `homelab_backup_*` from the PBS datastore + HA share; powers BackupStale/BackupAbsent + the Glance/Grafana backup panels (ADR-017). Targets oneill |
| `provision-deadmans-switch.yml` | apophis cron that ntfy-alerts if oneill monitoring/Technitium is unreachable (ADR-013). Run with `--limit apophis` |
| `update-pve-host.yml` | Update a Proxmox VE host — `apt update` + `dist-upgrade` + autoremove, reports reboot-required (running vs newest kernel) — **no reboot** unless `-e do_reboot=true` (ADR-015 host track). **One node at a time**, `--limit <host>` (refuses multiple). Reboot drops oneill services — plan a window |

Dry-run first against production with `--check` where the modules support it, or
test on a Proxmox snapshot.

## Conventions

- One playbook per logical service; promote shared steps to roles when reused.
- Non-secret defaults go in `group_vars/all.yml`. Secrets are prompted at runtime
  (`vars_prompt`) or stored with `ansible-vault` — never committed.
- **Real IPs/hosts are not committed** — they live in the gitignored `inventory/hosts.ini`
  and `inventory/group_vars/all.yml`, created from the `*.example` templates. The public
  repo carries `YOUR_*` placeholders only (ADR-006).
- Idempotent: re-running a playbook should converge, not duplicate.
- The bash scripts in `../scripts/` are manual fallbacks / references, not the
  primary path.
