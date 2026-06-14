#!/usr/bin/env bash
# Provision an unprivileged Tailscale LXC on Proxmox (apophis) as a subnet router.
# Run ON THE PROXMOX HOST as root:  bash tailscale-lxc-provision.sh
# (or from the admin VM once SSH works: ssh root@YOUR_PROXMOX_IP 'bash -s' < tailscale-lxc-provision.sh)
#
# Assumptions:
#   - Runs on the Proxmox host (needs pct/pveam/pvesh).
#   - rootfs storage pool is local-lvm; template store is local. Adjust below if different.
#   - The Home VLAN is the bridge's native/untagged VLAN (matches mgmt-vm: no tag on the NIC).
#
# Required input (never hardcode the key — this repo is public):
#   - Tailscale auth key. Generate at https://login.tailscale.com/admin/settings/keys
#     (reusable + pre-approved recommended). Pass via TS_AUTHKEY env var or the prompt.
#
# After running this script:
#   1. In the Tailscale admin console (https://login.tailscale.com/admin/machines):
#        - Approve the advertised subnet route(s) for this node.
#        - Disable key expiry for this node (it's infrastructure).
#   2. Add a DHCP reservation for the LXC's MAC in UniFi if you want a stable LAN IP.
#   3. From a remote device on Tailscale, confirm you can reach YOUR_PROXMOX_IP (Proxmox)
#      and YOUR_HA_IP (Home Assistant).

set -euo pipefail

# Proxmox keeps pct/pveam/pvesh in /usr/sbin; `su` (without -l) drops it from PATH.
export PATH="/usr/sbin:/sbin:$PATH"

# --- Configuration -----------------------------------------------------------
CTID="${CTID:-$(pvesh get /cluster/nextid)}"  # next free VMID unless overridden
HOSTNAME_CT="tailscale"
RAM_MB=256
CORES=1
DISK_SIZE="4"                  # GB
STORAGE="local-lvm"            # rootfs pool
TEMPLATE_STORE="local"         # where the LXC template lives
BRIDGE="vmbr0"
# VLAN_TAG=""                   # leave empty = native/Home VLAN (matches mgmt-vm). Set e.g. 2 to tag.
ADVERTISE_ROUTES="YOUR_LAN_CIDR"  # add IoT/mgmt subnets comma-separated if you want them reachable
TEMPLATE="debian-12-standard_12.12-1_amd64.tar.zst"
# -----------------------------------------------------------------------------

command -v pct >/dev/null || { echo "ERROR: pct not found — run this on the Proxmox host."; exit 1; }

# --- Auth key (kept out of the repo and out of the process list) -------------
TS_AUTHKEY="${TS_AUTHKEY:-}"
if [[ -z "$TS_AUTHKEY" ]]; then
  read -rsp "Enter Tailscale auth key (tskey-auth-...): " TS_AUTHKEY; echo
fi
[[ "$TS_AUTHKEY" == tskey-* ]] || { echo "ERROR: that doesn't look like a Tailscale auth key."; exit 1; }

echo ""
echo "About to create an unprivileged Tailscale LXC:"
echo "  CTID:            $CTID"
echo "  Hostname:        $HOSTNAME_CT"
echo "  RAM / Cores:     ${RAM_MB} MB / ${CORES}"
echo "  Disk:            ${DISK_SIZE} GB on ${STORAGE}"
echo "  Bridge:          ${BRIDGE} (native VLAN)"
echo "  Network:         DHCP (set a reservation in UniFi afterwards)"
echo "  Advertise route: ${ADVERTISE_ROUTES}"
echo ""
read -rp "Proceed? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

echo "==> Ensuring Debian 12 template is present..."
if ! pveam list "$TEMPLATE_STORE" 2>/dev/null | grep -q "$TEMPLATE"; then
  echo "    Downloading $TEMPLATE ..."
  pveam update
  pveam download "$TEMPLATE_STORE" "$TEMPLATE"
fi

echo "==> Creating unprivileged LXC $CTID ($HOSTNAME_CT)..."
pct create "$CTID" "${TEMPLATE_STORE}:vztmpl/${TEMPLATE}" \
  --hostname "$HOSTNAME_CT" \
  --cores "$CORES" \
  --memory "$RAM_MB" \
  --swap 0 \
  --rootfs "${STORAGE}:${DISK_SIZE}" \
  --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1

echo "==> Adding /dev/net/tun passthrough (required for Tailscale in an unprivileged LXC)..."
CONF="/etc/pve/lxc/${CTID}.conf"
grep -q "10:200 rwm" "$CONF" || cat >> "$CONF" <<'EOF'
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
EOF

echo "==> Starting LXC $CTID..."
pct start "$CTID"
sleep 5

echo "==> Installing Tailscale inside the LXC..."
pct exec "$CTID" -- bash -c "apt-get update -qq && apt-get install -y -qq curl >/dev/null && curl -fsSL https://tailscale.com/install.sh | sh"

echo "==> Enabling IP forwarding (needed for subnet routing)..."
pct exec "$CTID" -- bash -c 'cat > /etc/sysctl.d/99-tailscale.conf <<SYSCTL
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
SYSCTL
sysctl -p /etc/sysctl.d/99-tailscale.conf >/dev/null'

echo "==> Bringing Tailscale up as a subnet router..."
pct exec "$CTID" -- tailscale up \
  --authkey="$TS_AUTHKEY" \
  --advertise-routes="$ADVERTISE_ROUTES" \
  --accept-routes \
  --hostname="$HOSTNAME_CT"

echo ""
echo "==> Done. Tailscale LXC $CTID is up."
pct exec "$CTID" -- tailscale ip -4 || true
echo ""
echo "Next steps (manual, in the Tailscale admin console):"
echo "  1. Approve the subnet route ${ADVERTISE_ROUTES} for this node."
echo "  2. Disable key expiry for this node (it's infrastructure)."
echo "  3. Add a DHCP reservation for the LXC in UniFi for a stable LAN IP."
echo "  4. From a remote Tailscale device, ping YOUR_PROXMOX_IP and YOUR_HA_IP to confirm routing."
