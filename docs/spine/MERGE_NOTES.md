# Spine merge notes (2026-06-13)

Merge từ spine `Vòng 2/greenflow/` (dựng 2026-06-12) vào repo này. Nguyên tắc:
**additive, không phá flow hiện có** — demo building synthetic (b000…001),
LangGraph graph, API, web giữ nguyên hành vi; 29 test cũ vẫn pass.

## Đã merge

| Phần | Đích | Ghi chú |
|---|---|---|
| `regrettable_substitution_check` (D8) | `backend/greenflow/agent/regret.py` | Port sang dict KPI của `sim.kpi.compare_runs`; wire vào `policy.evaluate_action` (chỉ chạy khi context có `kpi`) + `policy_node` truyền `baseline_vs_optimized` vào. Ngưỡng trong `policy.yaml::regrettable_check`. 8 test mới (`tests/test_regret.py`). |
| ML specs (D10, D11) | `backend/greenflow/ml/` | Skeleton `forecast_service.py` (surrogate LightGBM R²=0.95 từ pipeline thật) + `occupancy_forecaster.py`. Thay heuristic trong `nodes/prediction.py` khi có model file. |
| Anomaly engine | `backend/greenflow/agent/anomaly.py` + bảng `anomaly_rules` (schema.sql, additive) + `db/seed/anomaly_rules.sql` | Dùng bảng `alerts` sẵn có (`alert_type` = rule id), không ALTER. |
| Loader dữ liệu E+ thật | `scripts/load_real_telemetry.py` | Nạp 188 zone × 3 tháng telemetry (EnergyPlus 26.1 thật) thành **building thứ hai** (uuid5 deterministic, `entity_key` = IFC GUID). Demo building không bị đụng. |
| Design docs | `docs/spine/` | `DECISIONS_AND_CRITIQUE.md` (13 quyết định D1–D13), `PARQUET_SCHEMA.md` (contract dữ liệu thật), `openapi.yaml` (contract spine — tham khảo, xem "Khác biệt" dưới). |

## Cố ý KHÔNG merge (tránh xung đột)

- **Schema v2 text-key của spine**: repo này đã giải bài toán D1 theo cách khác
  (uuid PK + cột `entity_key` text unique) — hợp lệ, không ép đổi. Loader đã
  adapt theo (uuid5 từ GUID).
- **world_runs/decision_ticks**: repo này model counterfactual bằng
  `simulation_runs` + `simulation_results` — tương đương về chức năng.
  Hệ quả (D3): telemetry PK `(timestamp, zone_id)` không có chiều run →
  một window chỉ chứa **một** run tag (`scenario_id`); loader wipe-replace
  theo tag. Nếu sau này cần nhiều agent-variant telemetry song song, cân nhắc
  thêm `scenario_id` vào PK (migration nhỏ, đã có cột sẵn).
- **API spine (FastAPI riêng)**: repo đã có routers đầy đủ; `docs/spine/openapi.yaml`
  chỉ làm tham chiếu thiết kế (replay-clock `at`, compare M&V shape), không phải
  contract đang chạy.
- **D9 (archetype trap)**: không áp dụng cho engine synthetic hiện tại — repo
  này sim trực tiếp 5 zone archetype, không expand 188 zone. **Chỉ** áp dụng
  nếu nâng cấp lên EnergyPlus batch với dữ liệu BIM: đọc D9 trước khi viết
  `action_to_idf` cho 188 zone.

## Cách chạy phần mới

```bash
# test (regret check nằm trong suite)
cd backend && python -m pytest tests/ -q          # 37 passed

# seed anomaly rules (sau khi schema áp)
psql $DATABASE_URL -f db/seed/anomaly_rules.sql

# nạp dữ liệu E+ thật (building thứ hai, không đụng demo)
python scripts/load_real_telemetry.py \
  --bim-map "../Dataset/BIM/extracted/office_concrete/zone_equipment_map.json" \
  --data-dir "../tools/datagen/out"               # thêm --with-devices nếu cần 11M dòng
```
