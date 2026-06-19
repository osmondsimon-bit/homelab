#!/usr/bin/env python3
"""
Homelab Infra Portal Generator (ADR-020)
Reads physical_infra/ YAML/JSON → HTML + D2 diagrams → static site output dir.

Usage:
  python3 infra-portal-generate.py --data-dir ~/homelab/physical_infra --output-dir /tmp/portal-out

Requires: python3-yaml (apt install python3-yaml), d2 (https://d2lang.com) in PATH.
"""

import argparse, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: apt install python3-yaml")

VLAN_COLOURS = {
    "Home":       "#3b82f6",
    "Camera":     "#ef4444",
    "IoT":        "#22c55e",
    "Guest":      "#a855f7",
    "Management": "#6b7280",
}
DEFAULT_COLOUR = "#94a3b8"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(data_dir: str) -> dict:
    d = Path(data_dir)
    data = {}
    for key, path in [
        ("rooms",    d / "house/rooms.json"),
        ("ports",    d / "house/schedules/data_schedule.json"),
        ("lighting", d / "house/schedules/lighting.json"),
    ]:
        if path.exists():
            data[key] = json.loads(path.read_text())
        else:
            print(f"  warning: {path} not found", file=sys.stderr)
            data[key] = {}

    for key, path in [
        ("vlans",    d / "network/vlans.yaml"),
        ("topology", d / "network/topology.yaml"),
        ("compute",  d / "compute/hosts.yaml"),
        ("rack",     d / "rack/layout.yaml"),
    ]:
        if path.exists():
            data[key] = yaml.safe_load(path.read_text()) or {}
        else:
            print(f"  warning: {path} not found", file=sys.stderr)
            data[key] = {}
    return data


def get_ports(data: dict) -> list:
    return data.get("ports", {}).get("data_schedule", {}).get("ports", [])


# ---------------------------------------------------------------------------
# D2 diagram generation
# ---------------------------------------------------------------------------

def network_d2(data: dict) -> str:
    ports    = get_ports(data)
    compute  = data.get("compute", {})
    topology = data.get("topology", {})

    aps     = [p for p in ports if p.get("device_type") == "Access Point" and p.get("switch_port")]
    cameras = [p for p in ports if p.get("purpose") == "Security" and p.get("switch_port")]
    hosts   = compute.get("hosts", [])
    sw      = topology.get("switch", {})
    gw      = topology.get("gateway", {})

    lines = ["direction: right", ""]
    lines += [
        f'ISP: ISP Fiber {{shape: cloud; style.fill: "#f1f5f9"}}',
        f'UDM: {gw.get("model", "UniFi Gateway")} {{style.fill: "#d1fae5"}}',
        f'Switch: {sw.get("model", "Core Switch")}\\n{sw.get("poe_budget_w", "?")}W PoE budget {{style.fill: "#dbeafe"}}',
        "",
        "ISP -> UDM: WAN fiber",
        'UDM -> Switch: SFP+1 10G {style.stroke: "#1d4ed8"; style.stroke-width: 2}',
        "",
    ]

    if hosts:
        lines += ['Servers: Compute {style.fill: "#f5f3ff"}']
        for h in hosts:
            hid  = h["hostname"].replace("-", "_")
            ram  = f"\\n{h['ram_gb']}GB RAM" if h.get("ram_gb") else ""
            role = h.get("form_factor", "")
            lines.append(f'  Servers.{hid}: {h["hostname"]}{ram}\\n{role}')
        lines.append("")
        for h in hosts:
            hid = h["hostname"].replace("-", "_")
            lines.append(f'Switch -> Servers.{hid}: {h.get("switch_port","?")} {{style.stroke: "#7c3aed"}}')
        lines.append("")

    if aps:
        lines += ['APs: Wi-Fi Access Points {style.fill: "#f0fdf4"}']
        for ap in aps:
            aid   = ap["port_id"].replace("-", "_")
            model = (ap.get("notes") or "").split("—")[0].split("–")[0].strip() or "U7 Pro XGS"
            lines.append(f'  APs.{aid}: {ap["room"]}\\n{model}')
        lines.append("")
        for ap in aps:
            aid = ap["port_id"].replace("-", "_")
            lines.append(
                f'Switch -> APs.{aid}: {ap["switch_port"]} PoE 30W {{style.stroke: "#16a34a"}}'
            )
        lines.append("")

    if cameras:
        lines += ['Cameras: Security Cameras {style.fill: "#fef2f2"}']
        for cam in cameras:
            cid   = cam["port_id"].replace("-", "_")
            model = cam.get("notes") or "Camera"
            lines.append(f'  Cameras.{cid}: {cam["room"]}\\n{model}')
        lines.append("")
        for cam in cameras:
            cid = cam["port_id"].replace("-", "_")
            lines.append(
                f'Switch -> Cameras.{cid}: {cam["switch_port"]} PoE {{style.stroke: "#dc2626"}}'
            )

    return "\n".join(lines)


def rack_d2(data: dict) -> str:
    units = data.get("rack", {}).get("units", [])
    FILL = {
        "UPS":    "#fef3c7",
        "Switch": "#dbeafe",
        "Patch":  "#e0e7ff",
        "Dream":  "#d1fae5",
        "UDM":    "#d1fae5",
    }

    lines = ["direction: down", ""]
    ids   = []
    for unit in units:
        u  = str(unit.get("u", "?")).replace("-", "_to_").replace(" ", "_")
        eq = unit.get("equipment", "Empty")
        uid = f"U{u}"
        ids.append(uid)
        fill = next((v for k, v in FILL.items() if k.lower() in eq.lower()), "#f8fafc")
        note = unit.get("notes", "")
        label = f"U{unit.get('u','?')}: {eq}"
        if note:
            label += f"\\n{note[:60]}"
        lines.append(f'{uid}: {label} {{style.fill: "{fill}"}}')

    lines.append("")
    for i in range(len(ids) - 1):
        lines.append(f'{ids[i]} -> {ids[i+1]}: {{style.opacity: 0}}')

    return "\n".join(lines)


def render_d2(source: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".d2", mode="w", delete=False) as f:
        f.write(source)
        src = f.name
    dst = src.replace(".d2", ".svg")
    try:
        r = subprocess.run(["d2", src, dst], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and Path(dst).exists():
            return Path(dst).read_text()
        return f'<pre class="d2-error">D2 render failed:\n{r.stderr[:500]}</pre>'
    except FileNotFoundError:
        return '<pre class="d2-error">d2 not in PATH — install via provision-infra-portal.yml</pre>'
    except Exception as e:
        return f'<pre class="d2-error">Error: {e}</pre>'
    finally:
        for f in [src, dst]:
            try: os.unlink(f)
            except: pass


# ---------------------------------------------------------------------------
# TBD detection
# ---------------------------------------------------------------------------

def find_tbds(data: dict) -> list:
    tbds = []
    for p in get_ports(data):
        for field in ("patch_panel_port", "switch_port", "device_type", "location"):
            if p.get(field) is None:
                tbds.append({"src": "data_schedule.json", "item": p["port_id"],
                              "field": field, "ctx": p.get("room", "")})
    for h in data.get("compute", {}).get("hosts", []):
        for field in ("ram_gb", "hostname"):
            v = h.get(field)
            if v is None or str(v).upper() in ("TBD", "NONE"):
                tbds.append({"src": "compute/hosts.yaml", "item": h.get("hostname", "?"),
                              "field": field, "ctx": h.get("role", "")})
    for u in data.get("rack", {}).get("units", []):
        if "TBD" in str(u.get("equipment", "")):
            tbds.append({"src": "rack/layout.yaml", "item": f"U{u.get('u','')}",
                          "field": "equipment", "ctx": u.get("notes", "")})
    return tbds


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg:#f8fafc; --card:#fff; --border:#e2e8f0;
  --text:#1e293b; --muted:#64748b;
  --tbd-bg:#fef3c7; --tbd-border:#f59e0b;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     background:var(--bg);color:var(--text);font-size:14px}
header{background:#1e293b;color:#f8fafc;padding:14px 24px;
       display:flex;justify-content:space-between;align-items:center}
header h1{font-size:17px;font-weight:600;letter-spacing:-.3px}
header .ts{font-size:11px;color:#94a3b8}
nav{background:#fff;border-bottom:1px solid var(--border);padding:0 20px;display:flex}
nav a{padding:11px 14px;text-decoration:none;color:var(--muted);font-size:13px;
      font-weight:500;border-bottom:2px solid transparent;white-space:nowrap}
nav a:hover,nav a.active{color:#3b82f6;border-bottom-color:#3b82f6}
main{padding:20px;max-width:1600px;margin:0 auto}
section{display:none}
section.active{display:block}
.card{background:var(--card);border:1px solid var(--border);
      border-radius:8px;padding:18px;margin-bottom:18px}
.card h2{font-size:15px;font-weight:600;margin-bottom:14px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.stat{background:#fff;border:1px solid var(--border);border-radius:8px;padding:14px 18px;min-width:110px}
.stat .v{font-size:26px;font-weight:700}
.stat .l{font-size:11px;color:var(--muted);margin-top:2px}
.bar-wrap{background:#e2e8f0;border-radius:4px;height:8px;margin:8px 0;overflow:hidden}
.bar-fill{height:8px;border-radius:4px;background:#3b82f6}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#f1f5f9;text-align:left;padding:8px 10px;
   border-bottom:2px solid var(--border);font-weight:600;
   position:sticky;top:0;z-index:1}
td{padding:6px 10px;border-bottom:1px solid #f1f5f9;vertical-align:top}
tr:hover td{background:#f8fafc}
tr.tbd td{background:var(--tbd-bg)}
tr.tbd:hover td{background:#fde68a}
td.nd{color:#cbd5e1;font-style:italic}
.vb{display:inline-block;padding:2px 7px;border-radius:10px;
    color:#fff;font-size:11px;font-weight:600}
.notes{max-width:280px;color:var(--muted);font-size:12px;line-height:1.4}
.svg-wrap{border:1px solid var(--border);border-radius:8px;overflow:auto;
          padding:12px;background:#fff}
.svg-wrap svg{max-width:100%;height:auto}
.d2-error{background:#fef2f2;border:1px solid #fecaca;border-radius:6px;
          padding:14px;color:#991b1b;font-size:12px;font-family:monospace}
.warn-badge{background:#fef3c7;border:1px solid var(--tbd-border);
            color:#92400e;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600}
.null{color:#cbd5e1}
code{background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:12px}
"""

JS = """
function show(id){
  document.querySelectorAll('section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('nav a').forEach(a=>a.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelector('nav a[data-id="'+id+'"]').classList.add('active');
  history.replaceState(null,'','#'+id);
}
window.addEventListener('DOMContentLoaded',()=>{
  show(location.hash.replace('#','')||'overview');
});
"""


def fmt(v) -> str:
    if v is None: return '<span class="null">—</span>'
    return str(v)


def vlan_badge(vlan) -> str:
    c = VLAN_COLOURS.get(vlan, DEFAULT_COLOUR)
    return f'<span class="vb" style="background:{c}">{vlan or "—"}</span>'


def ports_rows(ports: list) -> str:
    rows = []
    for p in ports:
        tbd = p.get("patch_panel_port") is None or p.get("switch_port") is None
        tr  = ' class="tbd"' if tbd else ""
        poe = f'✓ {p["poe_draw_w"]}W' if p.get("poe_required") else "—"
        ups = "✓" if p.get("ups_backed") else "—"
        pp  = fmt(p.get("patch_panel_port"))
        sw  = fmt(p.get("switch_port"))
        rows.append(
            f'<tr{tr}>'
            f'<td><code>{p["port_id"]}</code></td>'
            f'<td>{p["room"]}</td>'
            f'<td>{fmt(p.get("purpose"))}</td>'
            f'<td>{fmt(p.get("device_type"))}</td>'
            f'<td>{vlan_badge(p.get("vlan"))}</td>'
            f'<td>{poe}</td><td>{ups}</td>'
            f'<td{" class=\"nd\"" if p.get("patch_panel_port") is None else ""}>{pp}</td>'
            f'<td{" class=\"nd\"" if p.get("switch_port") is None else ""}>{sw}</td>'
            f'<td class="notes">{fmt(p.get("notes"))}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


def lighting_rows(data: dict) -> str:
    rows = []
    totals = [0] * 5
    for room in data.get("lighting", {}).get("lighting_schedule", []):
        layers  = room.get("lighting_layers", [])
        total   = sum(l.get("quantity", 0) for l in layers)
        ambient = sum(l.get("quantity", 0) for l in layers if l.get("layer") == "ambient")
        task    = sum(l.get("quantity", 0) for l in layers if l.get("layer") == "task")
        feature = sum(l.get("quantity", 0) for l in layers if l.get("layer") == "feature")
        dimm    = sum(l.get("quantity", 0) for l in layers if l.get("dimmable"))
        for i, v in enumerate([total, ambient, task, feature, dimm]):
            totals[i] += v
        rows.append(
            f'<tr><td>{room["level"]}</td><td>{room["room"]}</td>'
            f'<td>{room.get("ceiling_height_m","?")}m</td>'
            f'<td><strong>{total}</strong></td>'
            f'<td>{ambient or "—"}</td><td>{task or "—"}</td>'
            f'<td>{feature or "—"}</td><td>{dimm or "—"}</td></tr>'
        )
    rows.append(
        f'<tr style="font-weight:700;border-top:2px solid var(--border)">'
        f'<td colspan="3">Totals</td>'
        + "".join(f'<td>{v}</td>' for v in totals)
        + "</tr>"
    )
    return "\n".join(rows)


def tbd_rows(tbds: list) -> str:
    if not tbds:
        return '<tr><td colspan="4" style="color:var(--muted);text-align:center">No outstanding items</td></tr>'
    return "\n".join(
        f'<tr><td><code>{t["src"]}</code></td><td><code>{t["item"]}</code></td>'
        f'<td><code>{t["field"]}</code></td><td style="color:var(--muted)">{t["ctx"]}</td></tr>'
        for t in tbds
    )


def overview_level_rows(data: dict) -> str:
    ports  = get_ports(data)
    levels = data.get("rooms", {}).get("house", {}).get("levels", [])
    rows   = []
    for lvl in levels:
        room_names = {r["name"] for r in lvl.get("rooms", [])}
        lvl_ports  = [p for p in ports if p.get("room") in room_names]
        lvl_aps    = sum(1 for p in lvl_ports if p.get("device_type") == "Access Point")
        lvl_cams   = sum(1 for p in lvl_ports if p.get("purpose") == "Security")
        rows.append(
            f'<tr><td>{lvl["name"]}</td>'
            f'<td>{len(lvl.get("rooms",[]))}</td>'
            f'<td>{len(lvl_ports)}</td>'
            f'<td>{lvl_aps}</td><td>{lvl_cams}</td></tr>'
        )
    return "\n".join(rows)


def vlan_pills(ports: list) -> str:
    counts: dict = {}
    for p in ports:
        v = p.get("vlan") or "None"
        counts[v] = counts.get(v, 0) + 1
    return " ".join(
        f'<span class="vb" style="background:{VLAN_COLOURS.get(v, DEFAULT_COLOUR)}">{v}: {c}</span>'
        for v, c in sorted(counts.items())
    )


def generate_html(data: dict, net_svg: str, rack_svg: str, ts: str) -> str:
    ports     = get_ports(data)
    tbds      = find_tbds(data)
    levels    = data.get("rooms", {}).get("house", {}).get("levels", [])
    total_rooms = sum(len(l.get("rooms", [])) for l in levels)
    total_ports = len(ports)
    n_aps       = sum(1 for p in ports if p.get("device_type") == "Access Point")
    n_cams      = sum(1 for p in ports if p.get("purpose") == "Security")
    n_poe       = sum(1 for p in ports if p.get("poe_required"))
    poe_load    = sum(p.get("poe_draw_w", 0) or 0 for p in ports if p.get("poe_required"))
    poe_budget  = 600
    poe_pct     = round(poe_load / poe_budget * 100)
    tbd_badge   = f' <span class="warn-badge">{len(tbds)}</span>' if tbds else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Homelab Infra Portal</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Homelab Infra Portal</h1>
  <span class="ts">Generated {ts} UTC &mdash; edit physical_infra/ then restart infra-portal-generate.service</span>
</header>
<nav>
  <a data-id="overview"  onclick="show('overview');return false"  href="#overview">Overview</a>
  <a data-id="ports"     onclick="show('ports');return false"     href="#ports">Port Schedule</a>
  <a data-id="network"   onclick="show('network');return false"   href="#network">Network</a>
  <a data-id="rack"      onclick="show('rack');return false"      href="#rack">Rack</a>
  <a data-id="lighting"  onclick="show('lighting');return false"  href="#lighting">Lighting</a>
  <a data-id="tbd"       onclick="show('tbd');return false"       href="#tbd">TBD{tbd_badge}</a>
</nav>
<main>

<section id="overview">
  <div class="stats">
    <div class="stat"><div class="v">{total_rooms}</div><div class="l">Rooms / 3 levels</div></div>
    <div class="stat"><div class="v">{total_ports}</div><div class="l">Ethernet drops</div></div>
    <div class="stat"><div class="v">{n_aps}</div><div class="l">Access points</div></div>
    <div class="stat"><div class="v">{n_cams}</div><div class="l">Cameras</div></div>
    <div class="stat"><div class="v">{n_poe}</div><div class="l">PoE ports</div></div>
    <div class="stat"><div class="v">{len(tbds)}</div><div class="l">TBD items</div></div>
  </div>
  <div class="card">
    <h2>PoE Budget &mdash; USW Pro Max 48</h2>
    <div>{poe_load}W of {poe_budget}W ({poe_pct}% used &mdash; {poe_budget - poe_load}W headroom)</div>
    <div class="bar-wrap"><div class="bar-fill" style="width:{poe_pct}%"></div></div>
    <div style="margin-top:10px">{vlan_pills(ports)}</div>
  </div>
  <div class="card">
    <h2>By Level</h2>
    <table>
      <thead><tr><th>Level</th><th>Rooms</th><th>Ports</th><th>APs</th><th>Cameras</th></tr></thead>
      <tbody>{overview_level_rows(data)}</tbody>
    </table>
  </div>
</section>

<section id="ports">
  <div class="card">
    <h2>Ethernet Port Schedule ({total_ports} ports)</h2>
    <p style="font-size:12px;color:var(--muted);margin-bottom:12px">
      <span style="background:var(--tbd-bg);border:1px solid var(--tbd-border);
                   padding:2px 6px;border-radius:4px">Yellow rows</span> = null patch panel or switch port
    </p>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Port</th><th>Room</th><th>Purpose</th><th>Device</th>
          <th>VLAN</th><th>PoE</th><th>UPS</th>
          <th>Patch Panel</th><th>Switch Port</th><th>Notes</th>
        </tr></thead>
        <tbody>{ports_rows(ports)}</tbody>
      </table>
    </div>
  </div>
</section>

<section id="network">
  <div class="card">
    <h2>Network Topology</h2>
    <div class="svg-wrap">{net_svg}</div>
  </div>
</section>

<section id="rack">
  <div class="card">
    <h2>Rack Layout &mdash; Garage (12U Wall-Mount)</h2>
    <div class="svg-wrap">{rack_svg}</div>
  </div>
</section>

<section id="lighting">
  <div class="card">
    <h2>Lighting Schedule Summary</h2>
    <table>
      <thead><tr>
        <th>Level</th><th>Room</th><th>Ceiling</th>
        <th>Total</th><th>Ambient</th><th>Task</th><th>Feature</th><th>Dimmable</th>
      </tr></thead>
      <tbody>{lighting_rows(data)}</tbody>
    </table>
  </div>
</section>

<section id="tbd">
  <div class="card">
    <h2>TBD / Needs Decision ({len(tbds)} items)</h2>
    <table>
      <thead><tr><th>File</th><th>Item</th><th>Field</th><th>Context</th></tr></thead>
      <tbody>{tbd_rows(tbds)}</tbody>
    </table>
  </div>
</section>

</main>
<script>{JS}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Homelab Infra Portal Generator")
    parser.add_argument("--data-dir",   required=True, help="Path to physical_infra/")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {args.data_dir} ...")
    data = load_data(args.data_dir)

    print("Rendering D2 diagrams ...")
    net_svg  = render_d2(network_d2(data))
    rack_svg = render_d2(rack_d2(data))

    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    html = generate_html(data, net_svg, rack_svg, ts)

    index = out / "index.html"
    index.write_text(html)
    print(f"Done → {index}")


if __name__ == "__main__":
    main()
