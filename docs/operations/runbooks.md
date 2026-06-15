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

## Technitium DNS (CT 111, DNS-only resolver)

Unprivileged LXC 111 on apophis. **DNS only — UniFi keeps DHCP** (ADR-011). Provisioned
via Ansible (`ansible-playbook playbooks/provision-technitium.yml`, idempotent). Web
console on port `5380`, DNS on `53`. Migrates to the NUC in Phase 4.

### Check status (from apophis)
```bash
pct exec 111 -- systemctl status dns.service --no-pager
```

### Test resolution (from the mgmt-vm)
```bash
dig @YOUR_TECHNITIUM_IP example.com +short                    # should resolve
dig @YOUR_TECHNITIUM_IP securepubads.g.doubleclick.net +short # should be blocked (NXDOMAIN)
```
Note: test with a hostname that is **actually in the list** (e.g. `securepubads.g.doubleclick.net`,
`accounts.doubleclick.net`). OISD lists ad/tracking *hostnames*, not bare apex domains — so
`doubleclick.net` itself resolving is expected and is not a sign blocking is broken.

### Restart Technitium
```bash
pct exec 111 -- systemctl restart dns.service
```

### Logs
Console → **Logs**, or: `pct exec 111 -- journalctl -u dns.service -n 50 --no-pager`

---

### First-run config (in the web console, http://YOUR_TECHNITIUM_IP:5380)

Do this **before** the DHCP cutover below. The playbook installs the engine only.

1. **Forwarders** — Settings → Proxy & Forwarders: add encrypted upstreams
   (e.g. Cloudflare `https://cloudflare-dns.com/dns-query` and Quad9 DoH). Forwarder
   protocol: HTTPS (DoH) or TLS (DoT).
2. **Blocklist** — Settings → Blocking: tick **Enable Blocking**, set **Blocking Type =
   NX Domain**, add the OISD Big (Domains/Wildcards) URL `https://big.oisd.nl/domainswild2`,
   set **Update Interval = 24h**, **Save Settings**, then **Update Now**. One list is enough.
3. **Verify** with the `dig` tests above against the CT directly — a normal name resolves and
   an in-list ad hostname returns NXDOMAIN. The Dashboard **Block List** count should read
   ~300k+ once loaded.

### DHCP → DNS cutover (the actual switch)

The switch is **one UniFi DHCP field**, not a service migration. Reversible.

1. **Pre-flight:** confirm the two `dig` tests above pass against `YOUR_TECHNITIUM_IP`.
   Reserve/exclude `YOUR_TECHNITIUM_IP` in UniFi so the LXC IP never changes.
2. **Cut over (per-network, low-traffic window):** UniFi → Settings → Networks → (your
   LAN/VLAN) → DHCP → **DNS Server** → set to `YOUR_TECHNITIUM_IP`. Leave the secondary
   **blank** by default — a public secondary (e.g. `1.1.1.1`) silently bypasses blocking
   whenever it's used (ADR-011). Add one only if you accept that trade-off for resilience.
3. **Propagate:** clients pick up the new resolver on lease renewal. Force it on a test
   client (`ipconfig /renew`, or toggle Wi-Fi) and confirm `nslookup` shows the new server.
4. **Watch** the Technitium dashboard — query volume should climb as clients renew.
5. **Roll out** to remaining VLANs once the test network is healthy.

### Rollback (if DNS misbehaves)

1. UniFi → the network's DHCP → **DNS Server** → set back to the previous resolver
   (gateway or `1.1.1.1`).
2. Renew a client lease to confirm recovery.
3. Technitium can stay running while you debug — clients no longer depend on it.

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
