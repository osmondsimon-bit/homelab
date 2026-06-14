# Runbooks

Common operational procedures for Simon's homelab. Keep entries short — what to run, what to check, what success looks like.

---

## Proxmox host (apophis)

### Check host health
```bash
ssh root@YOUR_PROXMOX_IP 'pvesh get /nodes/apophis/status --output-format json | python3 -m json.tool'
```
Look for: `uptime`, `mem.used` vs `mem.total`, `cpu`.

### List running VMs and LXCs
```bash
ssh root@YOUR_PROXMOX_IP 'qm list && echo "---" && pct list'
```

### Check storage
```bash
ssh root@YOUR_PROXMOX_IP 'pvesm status'
```

---

## Home Assistant

### Check HA is reachable
- Local: http://YOUR_HA_IP:8123
- Remote: via Cloudflare Tunnel URL

### Restart HA (from Proxmox)
```bash
ssh root@YOUR_PROXMOX_IP 'qm reboot 200'
```

### Check Zigbee coordinator
Zigbee2MQTT connects to SLZB-06 at `YOUR_ZIGBEE_COORD_IP`. If Zigbee devices stop responding:
1. Check HA → Zigbee2MQTT add-on logs
2. Ping coordinator: `ping -c 3 YOUR_ZIGBEE_COORD_IP`
3. Restart Zigbee2MQTT add-on from HA UI

---

## mgmt-vm

### Check mgmt-vm connectivity
```bash
ping -c 3 YOUR_MGMT_VM_IP
```

### SSH to mgmt-vm
```bash
ssh simon@YOUR_MGMT_VM_IP
```

---

## Tailscale (CT 110, subnet router)

Unprivileged LXC 110 on apophis (LAN `YOUR_TAILSCALE_LAN_IP`, Tailscale IP `YOUR_TAILSCALE_IP`).
Advertises `YOUR_LAN_CIDR` for remote LAN access. Provisioned via Ansible
(`ansible-playbook playbooks/provision-tailscale.yml`, idempotent).

### Check status (from apophis)
```bash
pct exec 110 -- tailscale status
```

### Restart Tailscale
```bash
pct exec 110 -- systemctl restart tailscaled
```

### Change advertised routes
Edit `tailscale_advertise_routes` in `ansible/inventory/group_vars/all.yml`, re-run
the playbook, then **approve the new route** in the Tailscale admin console.

### If remote access stops working
1. `pct status 110` — is the CT running?
2. `pct exec 110 -- tailscale status` — is Tailscale up?
3. Confirm the subnet route is still approved (admin console → Machines → node).
4. `pct exec 110 -- sysctl net.ipv4.ip_forward` — should be `1`.

---

## Git / repo

### Push latest changes
```bash
git add <files> && git commit -m "..." && git push
```

### Check what's uncommitted
```bash
git status && git diff
```

---

*Add new entries as services are deployed. Each service should have: how to check health, how to restart, where to find logs.*
