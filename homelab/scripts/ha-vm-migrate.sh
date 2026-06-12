#!/usr/bin/env bash
# Provision a Home Assistant OS VM on Proxmox (apophis).
# Run from the Proxmox host as root, or via SSH: ssh root@YOUR_PROXMOX_IP 'bash -s' < ha-vm-migrate.sh
#
# Assumptions:
#   - HAOS qcow2 image already downloaded to /root/ on apophis (see HAOS_IMAGE below)
#   - Storage pool is local-lvm (LVM-thin); adjust STORAGE if different
#   - VM will get a static IP via your router's DHCP reservation or HA network config
#
# After running this script:
#   1. Boot the VM, complete HA onboarding at http://YOUR_HA_TEMP_IP:8123
#   2. Restore your HA backup: Settings → System → Backups → Restore
#   3. Verify everything works for a few days
#   4. Update router DHCP: reassign .10 to this VM's MAC, retire old machine

set -euo pipefail

# --- Configuration -----------------------------------------------------------
VMID=200
VM_NAME="home-assistant"
HAOS_IMAGE="/var/lib/vz/template/iso/haos_ova-17.3.qcow2"
STORAGE="local-lvm"
RAM_MB=4096
CORES=2
DISK_SIZE="64G"
BRIDGE="vmbr0"
# -----------------------------------------------------------------------------

echo "==> Checking image exists..."
if [[ ! -f "$HAOS_IMAGE" ]]; then
  echo "ERROR: Image not found at $HAOS_IMAGE"
  echo "Download from: https://github.com/home-assistant/operating-system/releases"
  echo "Choose the 'haos_ova-<version>.qcow2' asset."
  exit 1
fi

echo "==> Creating VM $VMID ($VM_NAME)..."
qm create "$VMID" \
  --name "$VM_NAME" \
  --machine q35 \
  --bios ovmf \
  --cpu host \
  --cores "$CORES" \
  --memory "$RAM_MB" \
  --net0 virtio,bridge="$BRIDGE" \
  --onboot 1 \
  --boot order=sata0

echo "==> Adding EFI disk..."
qm set "$VMID" --efidisk0 "${STORAGE}:0,efitype=4m,pre-enrolled-keys=0"

echo "==> Importing HAOS disk image (this may take a minute)..."
qm importdisk "$VMID" "$HAOS_IMAGE" "$STORAGE"

echo "==> Attaching imported disk as SATA..."
# SATA is required — OVMF does not scan VirtIO SCSI devices during EFI fallback boot.
# importdisk names the disk: vm-${VMID}-disk-1 (EFI disk took disk-0)
qm set "$VMID" --sata0 "${STORAGE}:vm-${VMID}-disk-1"

echo "==> Resizing disk to $DISK_SIZE..."
qm resize "$VMID" sata0 "$DISK_SIZE"

echo ""
echo "==> Done. VM $VMID created."
echo ""
echo "Next steps:"
echo "  1. In the Proxmox UI, review VM $VMID settings before starting."
echo "  2. Start the VM: qm start $VMID"
echo "  3. Watch console for boot, then open http://<VM-IP>:8123"
echo "  4. Set a static IP of YOUR_HA_TEMP_IP in HA: Settings → System → Network"
echo "  5. Restore your backup: Settings → System → Backups → Restore"
echo "  6. When satisfied, retire the old machine and reassign YOUR_HA_IP"
