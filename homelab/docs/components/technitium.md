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

## Troubleshooting: "ad-blocking isn't working"

Symptom: ads/trackers still appear even though Technitium is up. Work through these in order
— it's almost never the server itself.

**1. Is the server actually blocking?** From any host on the home VLAN:
```bash
dig @YOUR_TECHNITIUM_IP analytics.tiktok.com    # in OISD → expect NXDOMAIN (blocked)
dig @YOUR_TECHNITIUM_IP example.com              # control → expect a real A record
```
Blocked control fails too → server/forwarder problem. Only the tracker fails → engine is fine,
look at the client or the list.

**2. Is the *client* even using Technitium?** This is the usual cause. The DHCP-advertised DNS
is correct (the UDM hands out `YOUR_TECHNITIUM_IP`), so bypass happens at the device level:
- **iPhone/iPad (iOS) — the big one.** A manual `dig`/lookup app hits Technitium and shows
  "blocked", but **Safari** can still load ads because Apple routes it around local DNS via:
  - **iCloud Private Relay** (Settings → [name] → iCloud → Private Relay) — does its own DNS.
  - **"Limit IP Address Tracking"** (Settings → Wi-Fi → ⓘ → toggle) — on by default; sends
    *known-tracker* lookups through Apple's encrypted DNS, bypassing Technitium.
  - A custom DNS profile (Settings → Wi-Fi → ⓘ → Configure DNS should be **Automatic**;
    check General → VPN, DNS & Device Management for 1.1.1.1/NextDNS profiles).
  Turn off Private Relay + Limit IP Address Tracking to let Technitium do the blocking.
- **Desktop browsers:** Chrome/Edge/Firefox "Secure DNS / DNS-over-HTTPS" sends lookups to
  Cloudflare/Google over HTTPS, ignoring the OS resolver. Disable it in browser settings.
- **Smart TVs / IoT apps:** often hardcode `8.8.8.8` and ignore DHCP entirely.

Definitive per-device test: look up `analytics.tiktok.com` *on that device* — real IP = it's
bypassing Technitium; no address/NXDOMAIN = it's using it.

**3. Is it just the list being conservative?** OISD Big's motto is "Block. Don't break." — it
deliberately leaves common trackers unblocked (`google-analytics.com`, bare `doubleclick.net`,
`graph.facebook.com`, `scorecardresearch.com`). The *ad-serving* endpoints it does block are
the ones that matter (e.g. news.com.au's display ads via `securepubads`/`pubads.g.doubleclick.net`,
`pagead2.googlesyndication.com`, and Outbrain are all blocked). For more aggressive blocking,
add a list like **Hagezi Pro** to `technitium_blocklist_urls` in group_vars and re-run the playbook.

**4. Some ads can't be DNS-blocked at all.** Same-origin / in-app ads (YouTube, TikTok,
Instagram, Facebook, sponsored search results) serve from the content domain — no DNS filter
stops them; that needs a client-side blocker.

## Continuity

Stateless relative to Ansible (all config in git) → recovery is a reprovision, RTO ~15–20 min.
No LXC-level backup yet; covered by the Phase 3 VM-level backup task. Single instance = DNS
SPOF for now (ADR-011) — second instance planned with the Phase 4 cluster.
