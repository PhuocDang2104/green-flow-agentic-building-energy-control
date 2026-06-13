-- Anomaly rule catalog (spine merge) — read by backend/greenflow/agent/anomaly.py
INSERT INTO anomaly_rules (id, name, description, rule_type, params, severity) VALUES
  ('hvac_on_empty', 'HVAC running in empty zone',
   'hvac_power_kw > min_kw while occupancy_count = 0 for >= sustain_min minutes',
   'schedule_deviation', '{"min_kw": 0.5, "sustain_min": 30}', 'warning'),
  ('lighting_after_hours', 'Lighting on after hours',
   'lighting_power_kw > min_kw outside 07:00-19:00 workdays / all weekend',
   'schedule_deviation', '{"min_kw": 0.2, "work_start": 7, "work_end": 19}', 'warning'),
  ('co2_high', 'CO2 above comfort limit',
   'co2_ppm above zone comfort limit for >= sustain_min minutes',
   'threshold', '{"co2_max_ppm": 1000, "sustain_min": 30}', 'warning'),
  ('sensor_stuck', 'Sensor stuck / dropout',
   'Sensor value unchanged (exact repeat) or NULL for >= sustain_min minutes',
   'stuck_sensor', '{"sustain_min": 60}', 'info'),
  ('device_fault', 'Device fault state',
   'device fault_state set, or power_kw = 0 while status = on',
   'fault', '{}', 'critical'),
  ('comfort_violation_sustained', 'Sustained comfort violation',
   'Comfort violation while occupied for >= sustain_min minutes',
   'threshold', '{"sustain_min": 45}', 'critical')
ON CONFLICT (id) DO NOTHING;
