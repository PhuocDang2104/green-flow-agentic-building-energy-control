-- Graph-RAG retrieval queries (DuckDB over the generated artifacts)

-- 1. Which board supplies a given zone (and how confident)?
SELECT target_node_id AS board_id, notes AS category, weight, confidence, evidence_json
FROM read_csv_auto('graph_edges.csv')
WHERE relationship_type='ZONE_LOAD_ALLOCATED_TO_BOARD' AND source_node_id = ?;

-- 2. Highest estimated board demand.
SELECT board_id, device_tag, total_kwh, peak_total_kw, overload_status
FROM read_csv_auto('board_annual_summary.csv') ORDER BY peak_total_kw DESC LIMIT 10;

-- 3. Top contributing zones to a board (annual energy).
SELECT source_node_id AS zone_id, notes AS category, weight
FROM read_csv_auto('graph_edges.csv')
WHERE relationship_type='ZONE_LOAD_ALLOCATED_TO_BOARD' AND target_node_id = ?
ORDER BY weight DESC;

-- 4. Boards with missing ratings.
SELECT board_id, device_tag, floor_id FROM read_csv_auto('board_annual_summary.csv')
WHERE overload_status='rating_missing';

-- 5. Low-confidence / manual-review mappings.
SELECT * FROM read_csv_auto('graph_edges.csv') WHERE confidence IN ('low','manual_review');

-- 6. Neighbours of an entity (graph view).
SELECT * FROM read_csv_auto('graph_edges.csv')
WHERE source_node_id = ? OR target_node_id = ?;
