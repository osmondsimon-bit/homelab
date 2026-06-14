# ansible/

Ansible is the primary provisioning and configuration layer for the homelab
(see `../decisions/005-activate-ansible.md`). Playbooks run from the **mgmt-vm**
(the control node) and reach the Proxmox host over SSH.

## Bootstrap (one-time, on the mgmt-vm)

```bash
# 1. Install Ansible
sudo apt update && sudo apt install -y ansible

# 2. Create an SSH key if you don't have one
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519 -C "admin-vm"

# 3. Authorise the mgmt-vm on the Proxmox host (asks for apophis root password once)
ssh-copy-id root@YOUR_PROXMOX_IP

# 4. Verify connectivity (run from this directory so ansible.cfg is picked up)
cd ~/homelab/ansible
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
    hosts.ini                  # apophis (root), mgmt-vm (simon), home-assistant
    group_vars/all.yml         # non-secret defaults (CTIDs, IPs, sizing)
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

Dry-run first against production with `--check` where the modules support it, or
test on a Proxmox snapshot.

## Conventions

- One playbook per logical service; promote shared steps to roles when reused.
- Non-secret defaults go in `group_vars/all.yml`. Secrets are prompted at runtime
  (`vars_prompt`) or stored with `ansible-vault` — never committed.
- Idempotent: re-running a playbook should converge, not duplicate.
- The bash scripts in `../scripts/` are manual fallbacks / references, not the
  primary path.
