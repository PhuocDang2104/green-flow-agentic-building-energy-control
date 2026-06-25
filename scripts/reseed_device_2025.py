"""Re-seed telemetry_device_15m from the 2025 zone telemetry.

Device telemetry was stale synthetic 2026 data (seed_demo used wall-clock now),
misaligned with the real 2025 zone telemetry — so device state/faults were empty
at the 2025 replay anchor (get_latest_device_state uses timestamp <= anchor).
This derives device rows on the SAME 2025 grid by splitting each zone's HVAC /
electrical power across its mapped devices, so device-level state animates during
streaming and device queries return data. Idempotent (wipes + re-derives).

Run: docker compose exec api python /app/scripts/reseed_device_2025.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import text  # noqa: E402

from greenflow.config import get_settings  # noqa: E402
from greenflow.db import db_conn  # noqa: E402

DERIVE = """
INSERT INTO telemetry_device_15m
  (timestamp, building_id, floor_id, zone_id, device_id, device_type,
   status, setpoint_c, power_kw, energy_kwh, runtime_minutes)
SELECT t.timestamp, :b, d.floor_id, d.zone_id, d.id, d.device_type,
       CASE WHEN calc.pw > 0.01 THEN 'on' ELSE 'off' END,
       CASE WHEN d.device_type = 'hvac' THEN t.setpoint_c END,
       round(calc.pw::numeric, 3),
       round((calc.pw * 0.5)::numeric, 3),
       CASE WHEN calc.pw > 0.01 THEN 30 ELSE 0 END
FROM telemetry_zone_15m t
JOIN devices d ON d.zone_id = t.zone_id AND d.building_id = :b
JOIN (SELECT zone_id, device_type, count(*) AS n FROM devices
      WHERE building_id = :b GROUP BY zone_id, device_type) c
  ON c.zone_id = d.zone_id AND c.device_type = d.device_type
CROSS JOIN LATERAL (SELECT CASE
    WHEN d.device_type = 'hvac'
      THEN coalesce(t.hvac_power_kw, 0) / nullif(c.n, 0)
    WHEN d.device_type = 'electrical'
      THEN (coalesce(t.lighting_power_kw, 0) + coalesce(t.plug_power_kw, 0)) / nullif(c.n, 0)
    ELSE 0 END AS pw) calc
WHERE t.building_id = :b
"""

# Light, deterministic demo fault so the device_fault rule isn't always empty:
# one HVAC device shows an overcurrent fault on Tuesday afternoons.
INJECT_FAULT = """
UPDATE telemetry_device_15m SET fault_state = 'overcurrent', status = 'fault'
WHERE building_id = :b AND device_type = 'hvac'
  AND device_id = (SELECT id FROM devices WHERE building_id = :b
                   AND device_type = 'hvac' ORDER BY id LIMIT 1)
  AND EXTRACT(isodow FROM timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') = 2
  AND EXTRACT(hour FROM timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') BETWEEN 14 AND 15
"""


def main() -> None:
    b = get_settings().default_building_id
    with db_conn() as conn:
        conn.execute(text("DELETE FROM telemetry_device_15m WHERE building_id = :b"), {"b": b})
        conn.execute(text(DERIVE), {"b": b})
        conn.execute(text(INJECT_FAULT), {"b": b})
        row = conn.execute(text(
            "SELECT count(*) AS n, min(timestamp)::date AS lo, max(timestamp)::date AS hi, "
            "count(*) FILTER (WHERE fault_state IS NOT NULL) AS faults "
            "FROM telemetry_device_15m WHERE building_id = :b"), {"b": b}).mappings().first()
    print(f"telemetry_device_15m re-seeded: {row['n']} rows, {row['lo']}..{row['hi']}, "
          f"{row['faults']} fault rows")


if __name__ == "__main__":
    main()
