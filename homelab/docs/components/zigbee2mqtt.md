# Zigbee2MQTT (HAOS add-on)

Bridges the Zigbee mesh to MQTT for Home Assistant. Runs as a **Supervisor add-on inside the
Home Assistant VM** (not a separate guest), talking to a **network** Zigbee coordinator over TCP.

| | |
|---|---|
| Host / VMID | **carter** / VM 200 (HAOS; moved 2026-07-22 under ADR-009's 16 GB capacity model) — add-on `45df7312_zigbee2mqtt` |
| Coordinator | **SLZB-06** (Ethernet, PoE) at `YOUR_ZIGBEE_COORD_IP:6638` — IoT VLAN |
| MQTT broker | `core-mosquitto` add-on (same HA VM) |
| Bridge availability | MQTT topic `zigbee2mqtt/bridge/state` (retain) → HA `binary_sensor.zigbee2mqtt_bridge_connection_state` |
| Add-on real state | `sensor.zigbee2mqtt_addon_state` (Supervisor; `started`/`stopped`/`error`) — see Resilience |

## The failure mode (why this needs resilience)

Z2MQTT **exits on startup if the coordinator is unreachable** (TCP to `:6638`). The dominant
trigger is the **UniFi gateway rebooting** — the SLZB-06 hangs off the gateway's switch port, and
HA reaches it cross-VLAN *through* that gateway, so a gateway reboot drops the link + routing for
~2 min. Z2MQTT then dies and **does not reliably restart itself**: the Supervisor's "start at boot"
gives up after a couple of tries, and its anti-flap watchdog abandons a crash-storming add-on. Net
result without intervention: Zigbee automations silently stop for hours (the 2026-06-21 outage).
Same thing happens on any HA power-cycle while the network is still settling.

## Resilience: self-heal automation keyed on the **Supervisor add-on state**

> **Key gotcha (learned the hard way 2026-06-22):** do **NOT** key the self-heal off the MQTT
> bridge sensor (`binary_sensor.zigbee2mqtt_bridge_connection_state`). On a full power loss,
> Mosquitto dies at the same instant as Z2MQTT, so the last-will never fires and the **retained
> `online` message survives** — the sensor reads a stale `on` while the add-on is actually down.
> The reliable signal is the **Supervisor's real add-on state**, read via a `command_line` sensor.

**1. Supervisor add-on-state sensor** (HA `configuration.yaml`; needs a config reload/restart).
`command_line` is required — it's the only integration that can read `${SUPERVISOR_TOKEN}` (the REST
integration can't). A clean specific value like `error` means it's working (a broken command yields
`unknown`/`unavailable`):

```yaml
command_line:
  - sensor:
      name: Zigbee2MQTT addon state
      unique_id: zigbee2mqtt_addon_state
      command: 'curl -s -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" http://supervisor/addons/45df7312_zigbee2mqtt/info'
      value_template: "{{ (value | from_json).data.state | default('unknown') }}"
      scan_interval: 60
```

**2. Self-heal automation** — restart whenever the add-on is `error` or `stopped`; retry every
5 min after boot until the coordinator/network is reachable:

```yaml
alias: Zigbee2MQTT - keep the add-on running
mode: single
triggers:
  - trigger: homeassistant
    event: start
  - trigger: time_pattern
    minutes: "/5"
  - trigger: state
    entity_id: sensor.zigbee2mqtt_addon_state
    to: ["error", "stopped"]
    for: "00:02:00"
conditions: []
actions:
  - delay: "00:01:30"          # let the sensor populate + a normal start settle
  - condition: template
    value_template: "{{ states('sensor.zigbee2mqtt_addon_state') in ['error', 'stopped'] }}"
  - action: hassio.app_restart
    data:
      app: 45df7312_zigbee2mqtt
  - action: persistent_notification.create
    data:
      notification_id: z2m_autorestart
      title: "Zigbee2MQTT auto-(re)start"
      message: "Add-on was {{ states('sensor.zigbee2mqtt_addon_state') }} — restarted at {{ now().strftime('%H:%M') }}."
```

**Note:** the HA service is `hassio.app_restart` with an `app:` field (renamed from the old
`hassio.addon_restart`/`addon:`). The Supervisor add-on **Watchdog** toggle should also stay on, but
it is *not sufficient* alone — it doesn't cover boot-start failures or coordinator-unreachable loops.

**Test:** Settings → Add-ons → Zigbee2MQTT → Stop; within ~3–4 min it self-restarts (check the
automation's Traces). These live on the HA VM (HAOS), not in Ansible — this doc is their
version-controlled copy.

## Monitoring (CT 114, ADR-013)

- **`ZigbeeCoordinatorUnreachable`** — blackbox TCP probe of `YOUR_ZIGBEE_COORD_IP:6638`
  (`zigbee_coordinator_target`); HA-independent, catches the coordinator dropping. The reliable
  external alarm.
- **`Zigbee2MQTTBridgeDown`** — alerts on the bridge connectivity sensor. ⚠️ Best-effort only: it
  shares the **stale-retained-`online` blind spot** above (can read healthy while the add-on is
  down after a power loss), and is currently inert until HA's `prometheus:` filter exports the
  `binary_sensor` domain. The self-heal automation (Supervisor state) is the primary protection.

See `ansible/files/monitoring/alert-rules.yml` and [monitoring.md](monitoring.md).
