# ADR-016: Home Assistant observability — measurements to Prometheus, state/events stay in HA

**Date:** 2026-06-18
**Status:** Accepted

## Context

The monitoring stack (ADR-013) scrapes Home Assistant via its `prometheus`
integration (`/api/prometheus`). Left unfiltered this exports **everything HA
knows**: ~59 metric names / **1,782 series**, of which **81% (1,444 series)** come
from four *per-entity* metrics — `hass_state_change_total`,
`hass_state_change_created`, `hass_entity_available`, `hass_last_updated_time_seconds`
— plus `hass_entity_info`. These scale linearly with entity count.

Today's HA is small. After the house move it will be large: ~50 Zigbee
dimmers/switches, many presence/door sensors, HVAC, etc. The question raised:
should all of that go to Grafana/Prometheus, or stay in HA?

Storage was the feared constraint, but the numbers rule it out: the TSDB is **56 MB
for all targets over 30 days**; even a worst-case "push everything" big-house
scenario (~8,000 HA series) is **~1.2 GB / 30 days** inside a **20 GB** quota.
Prometheus handles millions of series. So the real issues are **signal-to-noise**
and **right-tool-for-the-job**, not cost.

## Decision

Split HA data by *kind*, not by source:

- **Numeric measurements → Prometheus.** Physical quantities (temperature,
  humidity, battery, power, energy, current, voltage, illuminance, signal strength,
  precipitation, pressure, CO₂, PM2.5) and climate current/target temperatures.
  Bounded, cheap, genuinely useful for cross-system trending and alerting
  (low-battery, freezer temp, power draw alongside infra). Enforced two ways
  ("Both" layers):
  - **Source filter (HA):** the `prometheus:` integration's `filter:` is scoped to
    `include_domains: [sensor, climate]` so HA only exports those entity domains —
    switches/lights/binary_sensors/device_trackers/persons/automations are never
    emitted. Reduces HA's own work. *Manual HAOS edit (HA is hand-built, not in
    Ansible); requires a HA restart.*
  - **Scrape keep-list (Prometheus):** `metric_relabel_configs … action: keep` on
    the `home-assistant` job keeps only the measurement/climate metric **names**,
    dropping the residual per-entity noise (`hass_state_change_*`,
    `hass_entity_available`, `hass_*_state`, `unit_*`, timestamps) even for the
    included domains. In code in `provision-monitoring.yml` (reproducible). This is
    the authoritative cap; the source filter is defence-in-depth.

- **State / events → stay in HA.** Switch/dimmer/light states, door/window and
  presence/occupancy, person/device_tracker, automation firings. These are the
  cardinality driver and the wrong fit for a metrics TSDB. They live in HA's
  **recorder** + **Long-Term Statistics** (auto-downsampled 5-min/hourly, kept
  ~forever, cheap) and are queried via HA's own History/Logbook/dashboards.

- **No HA dashboard in Grafana for now.** Grafana stays scoped to infrastructure +
  UniFi network (see the dashboards-as-code work). A small *curated* HA measurement
  panel may return later, but only over the filtered measurement set.

- **Unified external HA analytics → deferred.** If a single external surface for
  HA's *full* history (including state/events) is ever wanted, the purpose-built
  path is **InfluxDB** (HA native integration) as a separate sink, not the infra
  Prometheus. Revisit at the new house.

Effect verified live: with both layers active the HA scrape dropped **1,777 →
946** (source filter) **→ 55 kept** after relabeling, ~13 measurement metric names
remaining.

The keep-list regex is **prefix-agnostic** — it matches both HA's default
`homeassistant_` prefix and a custom `namespace: hass_`. (The source-filter edit
happened to drop a `namespace: hass`, reverting metrics to the `homeassistant_`
default; matching both means the cap survives that setting being present or absent.)

## Consequences

- HA's contribution to the TSDB stays bounded as the home grows — 50 new dimmers
  are light/switch entities that match neither the source filter nor the keep-list,
  so they never balloon Prometheus.
- **Maintenance:** a genuinely new *measurement* device_class (e.g. a new air-quality
  unit) won't appear until its metric name is added to the keep-list regex in
  `provision-monitoring.yml` (and within the included domains at the source). This
  is intentional — additions are deliberate, documented next to the regex.
- State/event history is only in HA — there is no cross-system (Grafana) view of it.
  Accepted; HA's own tools cover it. The InfluxDB option remains open if that changes.
- The source filter is a manual HAOS step; until it's applied, the Prometheus
  keep-list alone still enforces the measurement-only TSDB (HA just does redundant
  work exporting metrics that are then dropped at scrape).
- Builds on ADR-013 (monitoring stack); does not change scrape auth or topology.
