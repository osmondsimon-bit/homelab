# ADR-026: Household energy analytics — curated HA semantics to isolated InfluxDB

**Date:** 2026-08-20  
**Status:** Accepted (design; deployment deferred until energy commissioning)

## Context

ADR-016 deliberately retained roughly 30 days of numeric Home Assistant measurements in
Prometheus and deferred unified external analytics until the new house. The house design now has a
provisional Sigenergy solar, battery and backup system, a tariff with time-window incentives, and a
need to compare seasonal demand, battery behaviour, tariff performance and estimates over years.

Prometheus remains the right short-retention infrastructure and alerting store, but it is not the
authoritative long-term household-energy history. Home Assistant must also remain operational if
the analytics service is absent. Actual entity identifiers, tariff/account details and measured
household data are private.

## Decision

Add a separate, unprivileged InfluxDB service and dataset when the new-house energy entities are
commissioned. This decision establishes the boundary now; it does not provision or deploy the
service early.

- Home Assistant exports a curated semantic energy set: grid import/export power and energy, PV,
  house load, battery state-of-charge and charge/discharge, backup/grid state, EV energy where
  present, tariff/reward estimates, and freshness/plant-health signals. Raw Modbus registers are
  excluded by default and may be enabled only temporarily for diagnostics.
- The existing Grafana service reads InfluxDB for long-term tariff, seasonal, demand, battery and
  trend analysis. Home Assistant remains the household operational Energy view. Grafana does not
  become a control surface.
- Prometheus continues unchanged as the approximately 30-day infrastructure metrics and alerting
  store defined by ADR-013/016. The energy history is not duplicated wholesale into Prometheus.
- Analytics is never an input required for native Sigenergy operation or Home Assistant
  automation. A sustained export/query failure creates one maintenance incident; native plant and
  HA operation continue.
- Retention is tiered: raw or 30-second samples for 90 days, 5-minute aggregates for two years,
  hourly and daily aggregates for ten years, and annual aggregates permanently. Capacity and
  compaction are reviewed against measured growth before these become service guarantees.
- PBS protects configuration and retained aggregates, with a restore test before the service is
  relied upon. The high-volume raw tier is reproducible history and need not receive an independent
  backup if the measured backup cost is disproportionate; that choice must be recorded at build.
- Sanitised InfluxDB provisioning, retention policy, generic Grafana dashboard code and runbooks
  belong in this public repository. Actual HA entity mappings, tariff/account configuration and
  household-specific thresholds belong in the private `home-automation` repository under ADR-025.
  Measured data never enters Git.
- InfluxDB and Grafana are LAN/Tailscale-only with no direct internet exposure. HA writes through a
  dedicated least-privilege credential; Grafana receives query-only access. Secrets follow ADR-018.

## Deployment gates

Before provisioning:

1. record the final LXC placement, VMID, CPU/RAM, dataset size/quota and failure-domain impact;
2. approve the new guest through ADR-017's monitoring, backup and restore checklist;
3. commission canonical HA energy entities, units, sign conventions, cumulative-statistic resets,
   update cadence, freshness and comparison tolerances against the revenue meter;
4. define and test downsampling tasks and retention enforcement before enabling permanent export;
5. prove that stopping InfluxDB and denying its network path does not affect HA automations or the
   Sigenergy plant; and
6. security-review the service, credentials, firewall flows and dashboards before deployment.

## Consequences

- The house gains durable energy history without turning the infrastructure Prometheus store into
  a general-purpose household database.
- Grafana can correlate energy and infrastructure while HA keeps the simpler operational view.
- One more stateful service and dataset must be patched, monitored, backed up and restore-tested.
- Long-term detail has an explicit storage cost, controlled by tiered retention and curated export.
- Public automation remains reusable and publishable; private entity/tariff detail stays inside the
  repository intended for it.

This revisits only ADR-016's deferred InfluxDB option. It does not weaken ADR-016's Prometheus
filters or move household states/events wholesale out of Home Assistant.
