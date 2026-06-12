# Homelab

## Hosts

### apophis
- Role: Proxmox VE host
- IP: YOUR_PROXMOX_IP
- Status: initial build
- Services: Home Assistant planned

### admin
- Role: Admin VM
- IP: YOUR_MGMT_VM_IP
- Status: initial build
- Services: Git, Claude Code, scripts, SSH client, future Ansible

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
- Admin VM: YOUR_MGMT_VM_IP
- Bridge: vmbr0
- Initial VLAN: Home / untagged

## Next services
- Home Assistant VM migration
- Admin tooling
- Git repo
- Backups
- Monitoring
- Later: Ansible
