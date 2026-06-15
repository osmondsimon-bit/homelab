# terraform/

Terraform **creates** the lab's infrastructure (VMs, LXCs, disks, NICs) via the `bpg/proxmox`
provider. Ansible **configures** what Terraform creates (ADR-008). Run from the mgmt-vm.

> Status: scaffold only. First `apply`/`import` is a deliberate next step — needs a Proxmox API
> token and careful import of the running VMs.

## Bootstrap (one-time)

```bash
# 1. Install Terraform (or OpenTofu) on the mgmt-vm
#    e.g. via HashiCorp apt repo, or `tofu` from the OpenTofu releases

# 2. In Proxmox: create an API token for Terraform
#    Datacenter → Permissions → API Tokens → Add (user e.g. terraform@pve, token id "tf").
#    Grant it the privileges it needs (VM/LXC create/modify on the target nodes/storage).
#    Copy the secret — shown once.

# 3. Provide credentials (real file is gitignored — never commit it)
cd homelab/terraform
cp terraform.tfvars.example terraform.tfvars
#    edit terraform.tfvars: endpoint, the token (user@realm!tokenid=secret), ssh username

# 4. Init + plan
terraform init
terraform plan
```

## Importing the existing VMs

The running VMs (mgmt-vm=100, home-assistant=200, tailscale=110) predate Terraform. Bring each
under management with `terraform import`, then reconcile the HCL until `terraform plan` shows **no
changes** — so a future `apply` never tries to recreate a live VM. Do this one VM at a time,
plan-only, against the real config. Import is the fiddly part; take it slow.

## Layout

```
terraform/
  providers.tf              # terraform{} + bpg/proxmox provider (root module)
  variables.tf              # endpoint, api_token (sensitive), insecure, ssh user
  main.tf                   # resources (VMs/LXCs) — skeleton until import
  terraform.tfvars.example  # template — copy to terraform.tfvars (gitignored) + fill in
  terraform.tfvars          # YOUR creds (gitignored, not published, not backed up to a repo)
```

## Notes

- `terraform.tfvars` holds the API token — gitignored, and **not** backed up to any repo
  (credentials policy, ADR-006/007). Regenerate the token on restore.
- State (`*.tfstate`) is local and gitignored (it can contain sensitive values). Keep it on the
  mgmt-vm; it's covered by the eventual VM-level backup, not the public repo.
- The provider lock file (`.terraform.lock.hcl`) **is** committed — it pins provider versions.
- Boundary: Terraform = the box exists with the right shape; Ansible = the box is set up.
