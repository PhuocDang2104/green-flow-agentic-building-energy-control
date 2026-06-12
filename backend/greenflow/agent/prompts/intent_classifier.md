# Intent Classifier prompt

Used by `nodes/intent.py` when an LLM provider is configured. With
`LLM_PROVIDER=none` the keyword rules in `_KEYWORD_RULES` apply instead.

```text
Classify this building-operations question into exactly one intent from:
semantic_query, hvac_elec_query, energy_query, comfort_query, occupancy_query,
what_if_simulation_query, optimization_request, peak_strategy_query,
baseline_comparison_query, report_request, explain_action_query, general_help.
Reply with the intent only.
Question: {query}
```
