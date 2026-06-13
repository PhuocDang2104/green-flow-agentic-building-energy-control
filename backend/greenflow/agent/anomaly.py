"""Anomaly engine — scans telemetry against anomaly_rules, writes alerts (spine merge).

Deterministic batch rules over a time window (replay clock), not streaming.
Rules live in the anomaly_rules table (seeded by db/seed/anomaly_rules.sql);
alerts are written to the existing alerts table with
alert_type = anomaly_rules.id so the UI needs no schema change.

One handler per rule_type, all over telemetry_zone_15m / telemetry_device_15m:

  hvac_on_empty           hvac_power_kw > min_kw AND occupancy_count = 0
                          sustained >= sustain_min (group runs with a window
                          function: one alert per zone per episode, NOT one
                          per 15-min row).
  lighting_after_hours    lighting_power_kw > min_kw outside [work_start,
                          work_end) or on weekends.
  co2_high                co2_ppm > co2_max_ppm sustained.
  sensor_stuck            value exact-repeated or NULL >= sustain_min.
  device_fault            telemetry_device_15m.fault_state IS NOT NULL OR
                          (status = 'on' AND power_kw = 0) — also the trigger
                          for the fault/resilience demo scenario.
  comfort_violation_sustained  comfort risk while occupied, sustained.

Dedupe: skip if an unresolved alert for the same (alert_type, zone_id/device_id)
overlaps the window (alerts.resolved_at IS NULL).
"""

from __future__ import annotations

from datetime import datetime


def scan_anomalies(conn, building_id, window_start: datetime,
                   window_end: datetime) -> int:
    """Run all enabled rules, insert alerts, return number of new alerts."""
    raise NotImplementedError("see module docstring for per-rule contracts")
