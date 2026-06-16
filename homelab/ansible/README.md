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
