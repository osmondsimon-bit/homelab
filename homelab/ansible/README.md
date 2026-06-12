# ansible/

Ansible playbooks for configuration management. Not yet in active use — the admin VM needs Ansible
installed first.

## Prerequisites

```bash
sudo apt install ansible
```

## Layout

```
ansible/
  inventory/
    hosts.ini       # static inventory
  playbooks/        # one playbook per logical role or service
```

## Running a playbook

```bash
ansible-playbook -i inventory/hosts.ini playbooks/<name>.yml
```

## Conventions

- Use roles for anything applied to more than one host.
- Keep secrets out of this repo — use ansible-vault or environment variables.
- Test against a snapshot before running against production hosts.
