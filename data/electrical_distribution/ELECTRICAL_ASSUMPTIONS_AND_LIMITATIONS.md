# Electrical Assumptions & Limitations

- **Energy source:** patched `final_zone_device_power_timeseries` (EnergyPlus simulated),
  scenario `openmeteo_2025_30min_baseline`, 30-min, full-year. EnergyPlus is not re-run.
- **Board ratings:** the IFC `Nimellisvirta` (rated current) is largely a placeholder `0`
  → most boards are `rating_missing`; overload is **not** asserted for them (demand ranking only).
- **Power factor / voltage:** when absent from IFC, current uses assumed defaults
  (PF=0.9, 230/400 V) and is flagged `assumed_default`.
- **No IfcOutlet→circuit schedule:** plug loads use IFC outlet system codes + proximity;
  where absent, a **pseudo plug circuit** (low confidence).
- **HVAC:** no IFC HVAC→board link; HVAC load is a **pseudo HVAC circuit** on the floor
  main board (low). The EnergyPlus PTAC is a *representative model* of zone HVAC, not a
  1:1 map to IFC HVAC devices.
- **Spatial:** floor assignment is by IFC storey containment (high); zone-per-object is by
  nearest space centroid (medium/low) and is not required for allocation.
- **Phase balance:** not computed (no per-phase load allocation).
- Not a certified protection/coordination study.
