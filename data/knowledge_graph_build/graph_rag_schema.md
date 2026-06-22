# Graph-RAG Schema

Cards (JSONL) are embedded into the `electrical_kg` pgvector collection:

- **entity cards** (`graph_rag_entity_cards.jsonl`): boards, zones, floors — each with
  `text` (embedded), `properties`, `demand`, `provenance`, `confidence`, `caveats`,
  `linked_entities`, `recommended_dashboard_view`.
- **relationship cards** (`graph_rag_relationship_cards.jsonl`): one per relationship type
  describing meaning + provenance.

Backing structured data: `graph_nodes.csv` / `graph_edges.csv` (full graph),
`board_annual_summary.csv`, `board_estimated_timeseries.parquet`,
`zone_load_to_board_allocation.csv`, `manual_review_items.csv`.
