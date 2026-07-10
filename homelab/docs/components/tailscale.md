# Tailscale subnet routers (CT 110 + CT 126 — HA pair)

Remote access to the homelab is via **Tailscale subnet routers** advertising the LAN
(`YOUR_LAN_CIDR`) to the tailnet — no ports forwarded from the internet (ADR-003). Runs as an
**HA pair** so a single node failure doesn't cut remote access.

| | Router #1 | Router #2 |
|---|---|---|
| Guest | **CT 110** `tailscale` | **CT 126** `tailscale2` |
| Node | apophis | oneill |
| LAN IP | `YOUR_TAILSCALE_LAN_IP` | `YOUR_TAILSCALE2_LAN_IP` |
| Advertises | `YOUR_LAN_CIDR` | `YOUR_LAN_CIDR` |
| Shape | 256 MB / 1 core / 4 GB | same |

**Why a pair (added 2026-07-10):** originally only CT 110 (on apophis) advertised the LAN. When
apophis dropped (NIC hang, 2026-07-10), remote/tailnet traffic that hairpinned through CT 110 lost
its route to *every* LAN host even though carter/oneill were up. CT 126 on **oneill** (the stable
node) removes that single chokepoint — Tailscale elects one primary and fails over automatically.

## Key facts

- **`ip_forward=1`** in each CT (subnet routing). Route must be **approved in the Tailscale admin
  console** for each node — advertising ≠ approved. Both approved = bidirectional HA failover.
- **On-LAN clients** should run `tailscale up --accept-routes=false` (or exclude the local subnet)
  so LAN traffic goes **direct**, not hairpinned through a router.
- **Vaultwarden** rides the same tailnet (Tailscale Serve, tailnet-only) — see ADR-018.

## Health monitoring (per-router)

Each CT runs a tiny **health endpoint on `:9099`** (`tailscale-health.service`, deployed by
`provision-tailscale.yml`): returns **200 iff `tailscaled` is active AND the node is advertising the
approved `YOUR_LAN_CIDR` route**, else 503. Glance's **Service Status** tiles (`Tailscale`,
`Tailscale2`) point their `check_url` here — so a *broken* router shows **RED** even when Tailscale's
control plane is fine (the earlier `derpmap` check couldn't tell). Guest up/down is also covered by
**GuestDown** + the LXC panel.

## How it's managed / recovery

```bash
# Provision (router #1 uses the default vars; router #2 via per-instance overrides):
cd ~/homelab/ansible
ansible-playbook playbooks/provision-tailscale.yml --limit oneill \
  -e tailscale_ctid=126 -e tailscale_ip=YOUR_TAILSCALE2_LAN_IP/24 -e tailscale_hostname=tailscale2
# then APPROVE the YOUR_LAN_CIDR route for the new node in the Tailscale admin console.
```

- **Reproducible-from-code, not imaged** (no PBS backup) — rebuild via the play; re-auth with a new
  key + re-approve the route.
- **Health check:** `curl http://<ct-ip>:9099/` → `OK`. **Route/primary:** `pct exec <ct> -- tailscale status --json | grep PrimaryRoutes`.

## Related
ADR-003 (remote access) · ADR-017 (observability/continuity) · [operations/runbooks.md](../operations/runbooks.md)
(2026-07-10 incident) · provision-tailscale.yml · files/tailscale/tailscale-health.py.

**TODO (Phase-8):** parameterise `provision-tailscale.yml` for N routers (currently a 2nd instance
needs `-e` overrides) so the HA pair is fully declarative.
