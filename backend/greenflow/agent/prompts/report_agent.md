# Report Agent prompt

Used by `nodes/report.py` for the closing assessment paragraph when an LLM is
configured. All report sections (tables, findings, KPI) are rendered from live
DB data by deterministic templates regardless of provider.

```text
Summarize this building operations report in 3 sentences:
{report_markdown}
```
