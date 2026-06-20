# Technitium DNS (CT 111)

Network-wide DNS resolver with ad/tracker/malware blocking. **DNS only** — UniFi keeps
DHCP and hands this out as the resolver (ADR-011).

| | |
|---|---|
| Host / VMID | **oneill** (NUC) / CT 111 (unprivileged LXC, Debian 12) |
| IP | `YOUR_TECHNITIUM_IP` (static, set in the CT config — reserve/exclude in UniFi) |
| Ports | `53` DNS, `5380` web console (LAN-only HTTP) |
| Serves | **home VLAN only** (IoT/guest use the gateway for DNS-by-VLAN-role; camera + management excluded — no internet) |
| Upstreams | DoH forwarders — Cloudflare, Quad9 (`forwarderProtocol: Https`) |
| Blocking | OISD Big (`https://big.oisd.nl/domainswild2`), `NxDomain`, 24h refresh |

## How it's managed

Provisioned **and configured** by `homelab/ansible/playbooks/provision-technitium.yml`:

```bash
cd ~/homelab/ansible && ansible-playbook playbooks/provision-technitium.yml --limit oneill
```

The playbook creates the LXC, installs Technitium, sets the admin password (first install
only, via API, `no_log`), and applies forwarders + blocking + blocklists via the Technitium
API from `technitium_*` vars in `group_vars/all.yml`. It reads the settings back and fails
loudly if anything didn't apply.

> **Invariant:** config changes go through group_vars + a playbook re-run, **not** the web
> console. The console is effectively read-only — manual changes are overwritten on the next
> run and won't survive a reprovision/restore.

## Operations

Health checks, blocking tests, the DHCP cutover/rollback, planned-maintenance fallback, and
the CT-recovery (reprovision) procedure all live in
[docs/operations/runbooks.md](../operations/runbooks.md#technitium-dns-ct-111-dns-only-resolver).

## Continuity

Stateless relative to Ansible (all config in git) → recovery is a reprovision, RTO ~15–20 min.
No LXC-level backup yet; covered by the Phase 3 VM-level backup task. Single instance = DNS
SPOF for now (ADR-011) — second instance planned with the Phase 4 cluster.
