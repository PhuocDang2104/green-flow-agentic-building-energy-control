# Zone energy-scope redistribution status and review guide

Nguồn: production DB trên VM sau deploy/rebuild electrical KG và reload telemetry
`redistribute`, cập nhật ngày 2026-06-30.

File CSV đầy đủ: [ZONE_ENERGY_SCOPE_REVIEW_LIST.csv](./ZONE_ENERGY_SCOPE_REVIEW_LIST.csv)

## Trạng thái production hiện tại

Production VM hiện đang chạy:

```text
GREENFLOW_ENERGY_SCOPE_MODE=redistribute
GREENFLOW_TELEMETRY_SCOPE_MODE=redistribute
```

Telemetry đã được materialize lại bằng `scripts/load_real_data.py`.

Kết quả reload:

```text
901,824 raw rows -> 843,264 effective rows
aggregate rows redistributed = 58,560
unmapped aggregates = 0
telemetry table replaced: 901,824 -> 843,264 rows
anomaly scan: 30 alerts written
```

Breakdown sau reload:

| Scope | Zone visible | Telemetry rows | Ghi chú |
|---|---:|---:|---|
| `atomic_energy_zone` | 210 | 614,880 | Child/real zones |
| `review_required` | 78 | 228,384 | Vẫn được tính, cần review thủ công |
| `aggregate_context` | 0 trong telemetry | 0 | Raw aggregate rows đã được phân bổ xuống child zones |

Các API/UI chính hiện dùng **288 visible zones**:

- Dashboard `Zone state`: 288 zones, không còn `aggregate_context`.
- Run Optimization semantic log: 288 visible zones.
- KPI/health-score: tính trên 288 counted zones.

Production verify gần nhất:

```text
/api/kpi/current total_kw = 855.71608
/api/kpi/current occupancy = 3438
/api/kpi/current kwh = 8839.8133
/api/kpi/health-score overall = 71
```

Backup trước reload telemetry:

```text
/root/greenflow_telemetry_zone_15m_before_redistribute_2026-06-30_151153.sql.gz
```

## Tóm tắt scope cần review

| Scope | counts_toward_energy | Số zone | Ý nghĩa review |
|---|---:|---:|---|
| `aggregate_context` | false | 20 | Tên aggregate rõ ràng; đã được redistribute xuống child zones |
| `review_required` | true | 78 | Có tín hiệu nghi ngờ nhưng vẫn được tính năng lượng cho đến khi team xác nhận |

## Cách review đề xuất

1. Review 20 `aggregate_context` để xác nhận mapping child-zone là hợp lý.
2. Review 78 `review_required` theo `scope_reason`:
   - `context_space_name`: thường là `CHASE`, `SHAFT`, `Turning Free Space`, hoặc tên tương tự. Nếu chỉ là geometry/context, đổi sang `aggregate_context` hoặc set `counts_toward_energy=false`.
   - `unusual_height`: kiểm tra thủ công vì có thể là lift/shaft hoặc zone cao thật.
3. So sánh dashboard, Run Optimization, electrical overview và Zone state sau reload.
4. Nếu phát hiện zone child nhận tải sai, sửa mapping scope trước rồi reload telemetry lại.

## Redistribution đã encode trong code

Pipeline electrical KG có thêm phase `scope`, sinh file:

```text
data/knowledge_graph_build/mapping/zone_scope_child_weights.csv
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

## Checklist đánh giá tiếp cho teammate

1. Kiểm tra `docs/ZONE_ENERGY_SCOPE_REVIEW_LIST.csv`.
   - 20 `aggregate_context`: xác nhận đúng gross/volume/GFA/net-area.
   - 78 `review_required`: xác nhận có nên giữ counted hay chuyển sang context.

2. Kiểm tra child weights.
   - File: `data/knowledge_graph_build/mapping/zone_scope_child_weights.csv`.
   - Kỳ vọng: 20/20 aggregate mapped, 833 weight rows, 0 unmapped.
   - Mỗi aggregate phải có tổng weight = 1.0.

3. Kiểm tra UI sau deploy.
   - `Zone state` phải hiện 288 zones, không có `VOLUME / OFFICE`, `VOLUME / GARAGE`, `GFA`, `Gross Area Placeholder`.
   - Run Optimization log mới phải hiện `Loaded semantic graph: 288 zones`.
   - Tên zone child nên theo dạng `Floor · Room number · Area`, ví dụ `Basement · ELECT 0302 · 63.8 m2`.

4. Kiểm tra KPI sau reload.
   - `/api/kpi/current`
   - `/api/kpi/health-score`
   - `/api/electrical/overview`
   - Tổng năng lượng effective trong electrical overview được bảo toàn khi redistribute, nhưng Zone state/KPI không còn count aggregate rows.

5. Kiểm tra regression agent.
   - Chạy một Run Optimization mới.
   - Xác nhận candidate actions không target aggregate zones.
   - Xác nhận policy text không nhắc zone aggregate đã ẩn.

## Rollback nhanh

Nếu số liệu sai hoặc UI bất thường, rollback telemetry bằng backup đã tạo:

```bash
cd /opt/green-flow-agentic-building-energy-control
gzip -dc /root/greenflow_telemetry_zone_15m_before_redistribute_2026-06-30_151153.sql.gz \
  | docker compose exec -T db psql -U greenflow -d greenflow
```

Sau đó chuyển mode về audit và rebuild API:

```bash
sed -i 's/^GREENFLOW_ENERGY_SCOPE_MODE=.*/GREENFLOW_ENERGY_SCOPE_MODE=audit/' .env
sed -i 's/^GREENFLOW_TELEMETRY_SCOPE_MODE=.*/GREENFLOW_TELEMETRY_SCOPE_MODE=audit/' .env
docker compose up -d --build api
```

Rollback này đưa dữ liệu về trạng thái trước reload telemetry. Các code commit vẫn còn,
nhưng API sẽ đọc theo mode `audit`.
