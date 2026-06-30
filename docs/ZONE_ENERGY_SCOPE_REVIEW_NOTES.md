# Zone energy-scope review list

Nguồn: production DB trên VM sau deploy/rebuild electrical KG, ngày 2026-06-29.

File CSV đầy đủ: [ZONE_ENERGY_SCOPE_REVIEW_LIST.csv](./ZONE_ENERGY_SCOPE_REVIEW_LIST.csv)

## Tóm tắt

| Scope | counts_toward_energy | Số zone | Ý nghĩa review |
|---|---:|---:|---|
| `aggregate_context` | false | 20 | Tên aggregate rõ ràng; mặc định bị loại khi bật `dedup` |
| `review_required` | true | 78 | Có tín hiệu nghi ngờ nhưng vẫn được tính năng lượng cho đến khi team xác nhận |

## Cách review đề xuất

1. Review 20 `aggregate_context` trước. Nếu đúng là gross/volume/GFA/net area thì giữ `counts_toward_energy=false`.
2. Review 78 `review_required` theo `scope_reason`:
   - `context_space_name`: thường là `CHASE`, `SHAFT`, `Turning Free Space`, hoặc tên tương tự. Nếu chỉ là geometry/context, đổi sang `aggregate_context` hoặc set `counts_toward_energy=false`.
   - `unusual_height`: kiểm tra thủ công vì có thể là lift/shaft hoặc zone cao thật.
3. Không bật `GREENFLOW_ENERGY_SCOPE_MODE=dedup` làm mặc định cho dashboard cho đến khi list này được chốt.

## Redistribution plan đã encode trong code

Pipeline electrical KG có thêm phase `scope`, sinh file:

```text
storage/knowledge_graph_build/mapping/zone_scope_child_weights.csv
```

Rule hiện tại:

- Mỗi `aggregate_context` chỉ được phân bổ vào child zone cùng storey/floor.
- Child candidate phải là non-aggregate, có diện tích, và không phải `CHASE`, `SHAFT`, `Turning Free Space`, `VENT`, gross/net/volume context.
- Weight mặc định là area share:

```text
child_weight = child_area_m2 / sum(child_area_m2 của child candidates cùng location)
```

Các mode vận hành:

```text
GREENFLOW_ENERGY_SCOPE_MODE=audit          # giữ raw allocation, chỉ báo cáo audit
GREENFLOW_ENERGY_SCOPE_MODE=dedup          # loại aggregate load khỏi board/electrical totals
GREENFLOW_ENERGY_SCOPE_MODE=redistribute   # phân bổ aggregate load sang child zones trong electrical projection
```

Telemetry/Postgres có mode riêng vì cần reload data:

```text
GREENFLOW_TELEMETRY_SCOPE_MODE=audit
GREENFLOW_TELEMETRY_SCOPE_MODE=exclude_aggregate
GREENFLOW_TELEMETRY_SCOPE_MODE=redistribute
```

Nếu bật `GREENFLOW_TELEMETRY_SCOPE_MODE=redistribute`, cần chạy lại:

```bash
python scripts/load_real_data.py
```

Script sẽ materialize lại `telemetry_zone_15m`: bỏ raw aggregate rows, cộng occupancy/power/energy/cost của aggregate vào child zones theo `zone_scope_child_weights.csv`.

## Chỉ số production hiện tại

- `raw_total_kwh`: 350,597.0
- `deduped_total_kwh`: 139,941.7
- `excluded_aggregate_kwh`: 210,655.3
- mode hiện tại: `audit`
