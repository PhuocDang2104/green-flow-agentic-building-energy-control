# HVAC ↔ Energy Mapping Quality Report

- HVAC IFC extracted: **True** (HVAC_enriched.ifc)
- HVAC devices captured: **1237** (terminals: 1195, served-zone links: 1185)
- EnergyPlus PTAC representatives: **305** zones (relationship = `representative_model`)
- Zone HVAC load edges: one per zone (value class = EnergyPlus simulated)
- Weather context edges: Open-Meteo 2025 → each zone HVAC load

IFC HVAC fans/coils/PTAC are **not** asserted to map 1:1 to EnergyPlus PTAC/fan/coil;
the PTAC is recorded as a representative abstraction of each zone's HVAC. HVAC load
is allocated to a **pseudo HVAC circuit** on the floor's main board (see Phase 6).
