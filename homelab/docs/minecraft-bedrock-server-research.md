# Minecraft Bedrock server feasibility research

## Purpose

This note records the primary-source facts needed to decide whether to add a private Minecraft
server for the family. It is a research result, not an accepted architecture or a claim that a
guest has been deployed. Sources were checked on 2026-08-28.

## Conclusion

The homelab can host this without public ingress. The client mix makes **Bedrock Dedicated Server
(BDS)** the appropriate first-party server: Bedrock supports iPad, Windows, Nintendo Switch, and
Nintendo Switch 2, while Java Edition is limited to Windows, macOS, and Linux and the two editions
cannot share a server. The official BDS package is free to download. [Minecraft's edition
comparison](https://www.minecraft.net/en-us/article/java-or-bedrock-edition) and [BDS download and
requirements](https://www.minecraft.net/en-us/download/server/bedrock) support those boundaries.

The existing HA Tailscale subnet routers already advertise `YOUR_LAN_CIDR`, so the server does not
need Tailscale installed and no new route is required. Remote iPad and Windows clients can reach its
LAN address through that route. The important limitation is Nintendo Switch 2: local LAN discovery
has a documented BDS mechanism, but there is no first-party documentation showing an **Add Server**
control or a Tailscale client on Switch. Treat successful discovery and join from the exact installed
Switch build as a commissioning gate, and do not promise remote Switch access.

"No internet exposure" should mean **no inbound WAN port-forward, Cloudflare Tunnel, Tailscale
Funnel, or public DNS**, not no outbound connectivity. BDS's published requirements include a
broadband connection, authenticated mode uses Xbox Live, clients require Microsoft-account
multiplayer, and package/client updates are online operations. Keep ordinary outbound access while
allowing inbound game traffic only from the home LAN and authorised tailnet users. [BDS system
requirements](https://www.minecraft.net/en-us/download/server/bedrock), [BDS
properties](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/server-properties?view=minecraft-bedrock-stable),
and [Minecraft account requirements](https://help.minecraft.net/hc/en-us/articles/19615552270221-Accounts-Required-to-Play-Minecraft)
cover those dependencies.

## Client behavior

| Client | At home | Away from home | Practical implication |
| --- | --- | --- | --- |
| iPad | Add the server's LAN address and port, or use LAN discovery. | Install Tailscale on iOS, sign in as a restricted tailnet user, and use the same LAN address and port. iOS automatically accepts approved subnet routes. | Fully fits the local-plus-Tailscale model. |
| Windows desktop | Add the Bedrock server address and port. | Install Tailscale for Windows and use the same LAN address and port; Windows automatically accepts approved subnet routes. | The operator must launch Bedrock Edition, not Java Edition. |
| Nintendo Switch / Switch 2 | BDS explicitly lists both platforms, and `enable-lan-visibility=true` makes the server answer LAN discovery on the default ports. This must be proven on the installed console build. | No first-party-supported path was found: Tailscale does not publish a Switch client, and Minecraft's first-party instructions do not document entering an arbitrary server address on Switch. | Keep UDP `19132` and LAN visibility enabled. Do not adopt DNS-redirection apps, unofficial proxies, or similar workarounds as part of the supported design. |

Minecraft's server guide says Bedrock clients can add an address and port and that LAN servers appear
during the local-network scan. The BDS property reference says LAN visibility listens on the default
ports even if non-default server ports are configured. [Minecraft server connection
guide](https://www.minecraft.net/en-us/article/how-play-minecraft-server) and [BDS property
reference](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/server-properties?view=minecraft-bedrock-stable).

There is a release-timing wrinkle: Nintendo says the native Switch 2 edition is due on 2026-10-27,
after this research date. Commissioning must therefore test the actual build the boys use now and
repeat the join test after the native upgrade. [Nintendo's Switch 2 release
announcement](https://www.nintendo.com/au/news-and-articles/minecraft-for-nintendo-switch-2-arrives-27th-october/).

For cross-platform multiplayer, each child needs the appropriate platform account and a linked
Microsoft account/gamertag. Nintendo identifies Nintendo Switch Online as required for Minecraft's
online features; allow for that subscription even though the server itself is local. [Minecraft
account matrix](https://help.minecraft.net/hc/en-us/articles/19615552270221-Accounts-Required-to-Play-Minecraft)
and [Nintendo's Minecraft listing](https://www.nintendo.com/store/products/minecraft-switch/).

## Official server envelope

- BDS Linux support is **64-bit Ubuntu 22.04 LTS or later**; other Linux distributions are not
  supported. Run it as a dedicated service user inside an Ubuntu guest rather than on a Proxmox
  host. [Official BDS download page](https://www.minecraft.net/en-us/download/server/bedrock).
- The main requirements table specifies an Intel Core i3-3210 / AMD A8-7600-class CPU, **4 GB RAM**,
  180 MB to 1 GB of install space, and broadband. The same page's FAQ separately says 1 GB can suit a
  small server. Use the conservative 4 GB figure as the minimum guest allocation; world data and
  backups need capacity beyond the install-only storage figure.
- BDS is delivered as a ZIP: extract it into an empty directory and launch
  `LD_LIBRARY_PATH=. ./bedrock_server` on Ubuntu. It generates its data and world directories on
  first start. [Microsoft's BDS getting-started guide](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/getting-started?view=minecraft-bedrock-stable).
- The default game port is **UDP `19132` for IPv4**; IPv6 uses **UDP `19133`**. Microsoft's game
  server reference distinguishes BDS UDP from Java's TCP `25565`. [Microsoft Azure game-server
  reference](https://learn.microsoft.com/en-us/gaming/azure/reference-architectures/multiplayer-basic-game-server-hosting)
  and [BDS properties](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/server-properties?view=minecraft-bedrock-stable).
- The server software is free, but downloading/using it accepts the Minecraft EULA and privacy
  policy. The EULA permits installing the Java server for hosted play but prohibits redistributing
  Mojang's software; the safe automation pattern for either edition is to download the official BDS
  package directly rather than committing or mirroring it. [Official server download
  page](https://www.minecraft.net/en-us/download/server) and [Minecraft
  EULA](https://www.minecraft.net/en-us/eula).

A reasonable **pilot**, not an accepted sizing decision, is 2-4 vCPU, 4 GB RAM, and at least a 16 GB
root disk. CPU, memory, tick distance, and view distance should be observed with the boys' real world
and player count before resizing. The official property reference warns that player count, view
distance, and tick distance affect performance.

## Authentication and family controls

Set these values explicitly rather than relying on package defaults:

```properties
online-mode=true
allow-list=true
default-player-permission-level=member
allow-cheats=false
server-port=19132
enable-lan-visibility=true
```

`online-mode=true` authenticates connected players with Xbox Live. `allow-list=true` restricts the
server to gamertags in `allowlist.json`; add and remove children with `/allowlist add <GamerTag>` and
`/allowlist remove <GamerTag>`. Keep ordinary players at `member`, grant `operator` only to the
parent account, and leave cheats off unless deliberately enabled. [BDS properties](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/server-properties?view=minecraft-bedrock-stable)
and [allow-list/console instructions](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/getting-started?view=minecraft-bedrock-stable).

The official sources currently disagree about one default: the property reference still says
`allow-list=false`, while the 26.30 release notes say new dedicated servers enable the allow list by
default. Explicit configuration removes that ambiguity. [Minecraft 26.30 documentation source](https://github.com/MicrosoftDocs/minecraft-creator/blob/main/creator/Documents/Update1.26.30.md).

Do not turn off authenticated mode to make the server appear "more local." Network reachability and
player identity are separate controls; use both the game allow list and the network policy.

## LAN and Tailscale boundary

The intended flow is:

```text
home iPad / Switch / desktop ──home LAN──┐
                                        ├── YOUR_MINECRAFT_IP:19132/udp
remote iPad / Windows ──Tailscale───────┘
                         via CT 110 or CT 126
```

Implementation implications:

1. Reserve a static `YOUR_MINECRAFT_IP` on the home VLAN before provisioning.
2. Do not create a router port-forward, public hostname, Cloudflare route, or Funnel.
3. On the guest firewall, default-drop inbound and allow UDP `19132` only from
   `YOUR_LAN_CIDR`. The two subnet routers' LAN addresses are within that range.
4. Keep `enable-lan-visibility=true` and the default port for the Switch acceptance test.
5. Give the children separate restricted Tailscale identities. Do not sign their iPads into the
   existing operator identity, which the repository's current policy allows to reach everything.
6. Add a narrow tailnet group and grant to the **single LAN IP and UDP port**. Grants can coexist
   with the repository's legacy ACLs, so this does not require a wholesale policy migration:

   ```json
   {
     "groups": {
       "group:minecraft": ["YOUR_CHILD_TAILSCALE_LOGIN"]
     },
     "grants": [
       {
         "src": ["group:minecraft"],
         "dst": ["YOUR_MINECRAFT_IP"],
         "ip": ["udp:19132"]
       }
     ]
   }
   ```

7. Add policy tests that accept the child identity to `YOUR_MINECRAFT_IP:19132` and deny a sample
   management endpoint. Apply the policy in the Tailscale admin console, which remains the live
   source; update the repository's reference copy in the same focused change.

Tailscale recommends grants for new policy, supports protocol-and-port selectors such as
`udp:19132`, and applies default-deny least privilege. [Tailscale grants](https://tailscale.com/docs/features/access-control/grants)
and [grant syntax](https://tailscale.com/docs/reference/syntax/grants). Subnet routes and grants are
different layers: the route makes the LAN IP reachable, while the grant permits the connection.
[Tailscale route injection](https://tailscale.com/docs/reference/route-injection).

The subnet routers use SNAT by default, so the BDS guest sees a router's LAN address rather than the
remote user's original Tailscale address. Identity restriction therefore belongs in the Tailscale
policy; the guest firewall remains a coarser LAN/source boundary. [Tailscale subnet-router
SNAT](https://tailscale.com/docs/features/subnet-routers).

Invite the child identity into this tailnet instead of trying to share the BDS guest: Tailscale says
invited users can access devices behind subnet routers, while device sharing cannot. [Tailscale
inviting versus sharing](https://tailscale.com/docs/reference/inviting-vs-sharing). iOS and Windows
automatically use approved subnet routes; Linux is the platform that needs `--accept-routes`.
[Tailscale subnet-router client behavior](https://tailscale.com/docs/features/subnet-routers).

## Backups and updates

The world is irreplaceable state even though the guest and service configuration are reproducible.
It needs a deliberate continuity choice under ADR-012/017.

Recommended implementation contract:

- Run BDS under systemd with a dedicated user and persistent data directory.
- Take a daily **application-consistent** backup off the compute host to oneill. The simplest safe
  method for a small family server is a brief attended/off-hours service stop, archive the whole BDS
  data directory (world, properties, allow list, permissions, and packs), restart, and verify the
  service. BDS also provides the dedicated-server `/save` control for coordinating snapshots.
  [Microsoft command reference](https://learn.microsoft.com/en-us/minecraft/creator/commands/commands?view=minecraft-bedrock-stable).
- Register the backup in freshness monitoring. If the implementation uses a new archive target
  rather than a PBS guest image, `backup-freshness.sh` must learn that target.
- Perform and record a restore drill into an isolated throwaway guest before calling recovery proven.
- Keep daily/weekly retention proportional to the world size; never rely on the live guest as its
  own backup.

BDS clients and servers must stay closely aligned: Microsoft documents that protocol versions can
change at minor and even patch releases, producing `Outdated Client` or `Outdated Server` errors.
Treat BDS upgrades as deliberate application changes, not unattended package updates. [BDS version
compatibility](https://learn.microsoft.com/en-us/minecraft/creator/documents/bedrockserver/getting-started?view=minecraft-bedrock-stable).

For each stable update: take/verify a backup, stop BDS, download from the official page into a new
version directory, preserve the old directory for rollback, carry forward reviewed data/config,
start, and test iPad, Windows, and Switch joins. Do not deploy Preview builds. OS security updates can
follow the homelab's automatic-security/no-automatic-reboot policy; BDS version changes stay in the
attended maintenance window.

## What a build would require

This is a small but stateful new-guest project:

1. Confirm the Switch LAN-discovery acceptance test is worth the build; if remote Switch play is a
   requirement, BDS plus Tailscale does not have a first-party-supported solution.
2. Pass the project's new-guest infrastructure-design gate and select placement from **live** CPU,
   memory, and recovery evidence. The published requirements fit the three physical machines, but
   PLAN alone is not enough to choose the node.
3. Allocate a new guest identity/IP/VMID. Under the current interim provisioning model, Ansible
   creates and configures the Ubuntu LXC; Terraform import remains deferred. The playbook owns the
   BDS user, versioned download, explicit properties, systemd unit, guest firewall, patching,
   monitoring, and backup.
4. Add the allowlisted gamertags, narrow Tailscale group/grant/tests, and keep public ingress absent.
5. Add GuestDown/service health, Glance placement/version visibility, backup freshness, and a
   restore/reprovision drill under the existing onboarding checklist.
6. Commission on LAN with iPad, Windows, and the actual Switch build; then prove remote iPad/Windows
   access through each subnet router while confirming an unauthorised tailnet identity is denied.

Relevant local authorities: [Tailscale component](components/tailscale.md),
[ADR-003](../decisions/003-remote-access.md), [ADR-012](../decisions/012-backups.md),
[ADR-015](../decisions/015-patching.md),
[ADR-017](../decisions/017-observability-continuity-by-default.md), and the [new-guest
checklist](operations/runbooks.md#onboarding-a-new-guest--node--storage-adr-017).
