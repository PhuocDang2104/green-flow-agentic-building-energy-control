# Graph-RAG Usage Guide

Cards: `knowledge_graph_build/graph_rag_entity_cards.jsonl` (+ relationship cards) are
embedded into the pgvector `electrical_kg` collection by `loaders/pgvector.py`.

Ask via `GET /api/graph/rag/answer?question=...`. The endpoint retrieves the most
relevant cards, then answers under `graph_rag_answer_policy.md`: every value is labelled
(measured / simulated / IFC-derived / inferred / assumed / manual-review) and topology is
never overclaimed. See `graph_rag_example_questions.md` and `graph_rag_retrieval_queries.sql`.
