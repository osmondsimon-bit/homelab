# Infrastructure resources go here (or in per-service / per-node files).
#
# Terraform CREATES infrastructure (VMs, LXCs, disks, NICs) — Ansible CONFIGURES it (ADR-008).
#
# Existing running VMs (mgmt-vm=100, home-assistant=200, tailscale=110) will be brought under
# management with `terraform import` — deliberately, against live VMs, only after the HCL for each
# matches the real config so `apply` won't try to recreate a running VM. Plan-only until clean.
#
# Example skeleton (commented until the token + import are done):
#
# resource "proxmox_virtual_environment_container" "tailscale" {
#   node_name = "apophis"        # later: the NUC, after migration
#   vm_id     = 110
#   # ... cpu, memory, disk, network_interface, initialization ...
# }
