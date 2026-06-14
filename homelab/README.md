# Homelab

## Hosts

### apophis
- Role: Proxmox VE host
- IP: YOUR_PROXMOX_IP
- Status: initial build
- Services: Home Assistant planned

### admin
- Role: mgmt-vm
- IP: YOUR_MGMT_VM_IP
- Status: initial build
- Services: Git, Claude Code, scripts, SSH client, Ansible control node

## Design principles
- Keep Proxmox host clean
- Prefer VMs/LXCs over installing directly on host
- Back up before major changes
- Document network, storage, and service decisions
- Avoid exposing services directly to the internet
- Use Cloudflare Tunnel or VPN for remote access
- Use VLANs later, but keep initial setup simple

## Current network
- Gateway: YOUR_GATEWAY_IP
- Proxmox host: YOUR_PROXMOX_IP
- mgmt-vm: YOUR_MGMT_VM_IP
- Bridge: vmbr0
- Initial VLAN: Home / untagged

## Repo layout

```
decisions/   Architecture decision records (ADR-NNN-title.md)
scripts/     Shell scripts for provisioning and maintenance
ansible/     Playbooks and inventory (not yet active)
```

## Hosts

### home-assistant
- Role: Home Assistant OS VM (VMID 200)
- IP: YOUR_HA_IP
- MAC: YOUR_HA_MAC
- Status: running — migrated from dedicated machine, Zigbee confirmed working
- Services: Home Assistant OS, Zigbee2MQTT, SLZB-06 coordinator at YOUR_ZIGBEE_COORD_IP

## Next services
- [x] Home Assistant VM migration (ADR-004)
- [ ] Backups to NAS (longer term)
- [ ] Monitoring
- [ ] Ansible
