# Graph-RAG Answer Policy

When answering electrical / energy questions over this graph, the agent MUST:

1. **Label every value** with how it was obtained:
   - `measured` — from a real meter/sensor (only the building meters + weather here)
   - `energyplus_simulated` — zone Lights/Equipment/HVAC electricity from the gold dataset
   - `ifc_derived` — board/fixture/cable attributes read from the IFC (voltage, phase, system code)
   - `spatially_inferred` — assignment by floor containment / nearest space
   - `naming_inferred` — grouping by Finnish system code (`Järjestelmien tunnukset`)
   - `assumption_based` — estimated current using assumed power-factor/voltage
   - `manual_review` — insufficient evidence; do not use for automated control/risk
2. **Never overclaim topology.** Board→zone supply is *estimated allocation*, not a verified
   circuit schedule, unless an edge confidence is `exact`.
3. **Overload:** only state overload/loading-% when a board has a real `rated_current_a`.
   Otherwise say `rating_missing` and give demand ranking only.
4. **Boards are distribution assets**, never additional consumption; board demand is the
   redistribution of simulated zone energy.
5. Always surface the **confidence** and any **manual-review** flags, and cite the
   evidence (edge method, distance, system code).
