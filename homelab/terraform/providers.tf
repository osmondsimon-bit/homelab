# Root module provider config (ADR-008). Provider is declared here in the root;
# any future child modules carry only the required_providers source mapping.

terraform {
  required_version = ">= 1.6"
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = ">= 0.95.0"
    }
  }
}

provider "proxmox" {
  endpoint  = var.proxmox_endpoint  # https://YOUR_PROXMOX_IP:8006/
  api_token = var.proxmox_api_token # terraform@pve!tf=SECRET (from terraform.tfvars, gitignored)
  insecure  = var.proxmox_insecure  # true for Proxmox's self-signed cert

  # Some bpg/proxmox operations (file/disk uploads) use SSH to the node.
  ssh {
    agent    = true
    username = var.proxmox_ssh_username
  }
}
