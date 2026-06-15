variable "proxmox_endpoint" {
  description = "Proxmox API endpoint, e.g. https://YOUR_PROXMOX_IP:8006/"
  type        = string
}

variable "proxmox_api_token" {
  description = "Proxmox API token in the form user@realm!tokenid=secret"
  type        = string
  sensitive   = true
}

variable "proxmox_insecure" {
  description = "Skip TLS verification (true for Proxmox's self-signed cert)"
  type        = bool
  default     = true
}

variable "proxmox_ssh_username" {
  description = "SSH username for node-level operations (file/disk uploads)"
  type        = string
  default     = "root"
}
