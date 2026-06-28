# GreenFlow — Tổng kết nâng cấp tuần 21–28/06/2026

> Tài liệu dành cho team phát triển, ML và vận hành. Nội dung được tổng hợp từ 83 commit trên nhánh hiện tại trong 7 ngày, gồm 61 commit của AnHoaiThai và 22 commit của PhuocDang2104.

## 1. Tóm tắt điều hành

Trong tuần qua, GreenFlow được chuyển từ bản demo dùng dữ liệu và giả định rời rạc thành một hệ thống thống nhất hơn quanh bộ dữ liệu El Niño tháng 03–04/2024 với 308 zones. Các thay đổi lớn gồm:

- Đồng bộ dữ liệu telemetry, weather, zone metadata, electrical distribution và mô hình ML theo cùng một dataset contract.
- Retrain và đưa bốn model LightGBM lên MLflow production: building, zone, HVAC và short-term forecast.
- Bổ sung predictive MPC replay và cache what-if để không chạy mô phỏng nhiều tháng trực tiếp trong request web.
- Nâng cấp Agents & Actions thành luồng chat có trace chạy agent, approval/reject và lịch sử session.
- Bổ sung RAG kiến thức hệ thống, voice self-hosted và cơ chế LLM failover/circuit breaker.
- Mở rộng dashboard, fault analytics, climate view, electrical digital twin và CCTV cho toàn bộ 308 zones.
- Đơn giản hóa trang Simulation thành màn hình what-if tập trung vào baseline so với predictive MPC.
- Chuẩn hóa quy trình deploy VM, seed dữ liệu, đăng ký MLflow và kiểm tra production.

## 2. Dữ liệu tòa nhà và contract dùng chung

### 2.1 Dataset chính

Runtime hiện dùng dataset `elnino_2024_mar_apr`:

| Thuộc tính | Giá trị |
|---|---:|
| Scenario | `elnino_2024_mar_apr_baseline` |
| Khoảng thời gian | 01/03/2024 00:30 – 01/05/2024 00:00 |
| Múi giờ | `Asia/Ho_Chi_Minh` |
| Timestep | 30 phút |
| Số zones | 308 |
| Số timestamps | 2.928 |
| Số zone rows | 901.824 |
| Dataset SHA-256 | `4dda0344ff5e2e421d2fba0ce304bad4d66e83cf7e136f5fe9ed4f22985026cc` |

Các pipeline ingest và validation hiện kiểm tra cứng số zones, timestamps, rows, time range và fingerprint dữ liệu. Điều này ngăn model hoặc cache cũ bị dùng nhầm với dataset mới.

### 2.2 Đồng bộ true-building

- Đồng bộ 308 IFC spaces vào bảng zones và telemetry runtime.
- Nạp weather cùng grid 30 phút với telemetry.
- Chuẩn hóa các file Parquet cho building meter, zone/device power, weather và zone metadata.
- Bổ sung script kiểm tra PostgreSQL, DuckDB, electrical artifacts và model contract.
- Xác nhận tổng công suất của 308 zones khớp facility meter với sai số cực đại khoảng `3.87e-12 kW`.
- Facility peak trong dataset là `893.36 kW`.
- Giá trị `855.72 kW` tại thời điểm demo là tổng tải thực của toàn bộ 308 zones, không phải dữ liệu của 14 zones cũ.

### 2.3 Electrical knowledge graph và digital twin

- Bổ sung pipeline electrical-distribution/knowledge-graph, mapping zone → load → circuit → board.
- Thêm scene API và màn hình Electrical 3D Digital Twin.
- Bổ sung provenance, data dictionary, validation report và các báo cáo phân bổ tải/phase balance.
- Cập nhật XKT/IFC assets, object map và metadata để viewer phản ánh đúng phân cấp tòa nhà.

## 3. ML và MLOps

### 3.1 Pipeline train được thiết kế lại

Hai script train chính đã được viết lại theo schema hiện tại:

- `scripts/train_surrogate_real.py`
- `scripts/train_forecast_lag.py`

Thay đổi quan trọng:

- Dùng trực tiếp các target hiện có: facility power, total zone power và HVAC power.
- Dùng `dataset_split` để tách train/validation/test theo thời gian, tránh trộn ngẫu nhiên các timestep.
- Sinh feature thời gian, weather, occupancy, setpoint và đặc trưng hình học từ dataset hiện tại.
- Ghi dataset fingerprint, target, feature list, split và test metrics vào metadata của model.
- Short-term forecast phải vượt persistence baseline mới vượt quality gate.
- Forecast 60 phút được triển khai bằng recursive rollout trên timestep 30 phút, thay vì hiển thị 60 phút nhưng chỉ dự báo một bước.

### 3.2 Model production hiện tại

| Model | MLflow production | Target | Test result chính |
|---|---:|---|---|
| Building surrogate | v2 | `target_facility_power_kw` | R² 0,9341; MAE 50,98 kW |
| Zone surrogate | v2 | `target_total_zone_power_kw` | R² 0,9419; MAE 0,1835 kW |
| HVAC surrogate | v2 | `target_hvac_power_kw` | R² 0,6489; MAE 0,1424 kW |
| Lag forecast | v1 | zone power t+1, recursive | Building R² 0,9894; MAE 16,83 kW |

Lag forecast vượt persistence baseline:

- Building MAE: `16.83 kW` so với persistence `31.56 kW`.
- Zone MAE: `0.088 kW` so với persistence `0.104 kW`.

### 3.3 MLflow registry

- Chạy MLflow Tracking Server với PostgreSQL backend và MinIO artifact store.
- Model runtime dùng alias `@production`, không hard-code version.
- API `/api/ml/model-info` trả về model source, registered model, version, run ID, feature count và dataset contract.
- MLflow được proxy qua GreenFlow API để có thể truy cập trong hạ tầng deploy hiện tại.
- Client MLflow được pin về `2.17.2` để tương thích đúng với registry server.
- Cache MPC đưa model version, run ID và dataset fingerprint vào cache identity; đổi model sẽ không tái sử dụng nhầm cache cũ.

### 3.4 Forecast runtime

- Day-ahead forecast trả 48 điểm cho 24 giờ, timestep 30 phút.
- Tách rõ `total_kw` và `hvac_kw`; không dùng HVAC làm đại diện cho tổng tải tòa nhà.
- Thêm online calibration từ facility/HVAC meter hiện tại để giảm độ lệch giữa model offline và trạng thái replay.
- Contracted demand được chuẩn hóa thành `1.000 kW`, thay cho ngưỡng demo 38 kW của bản 14-zone.
- Prediction trace công bố `zone_coverage`, `horizon_minutes` và `model_horizon_minutes` để frontend và QA kiểm tra được phạm vi model.

## 4. Predictive control và Simulation

### 4.1 Predictive MPC replay

- Bổ sung objective, trajectory generation, predictive controller và replay engine.
- Controller đánh giá candidate trajectories theo energy, peak demand và comfort constraint.
- Bổ sung whole-building efficiency candidate và calibration cho tác động của action.
- Tác động setpoint được suy ra liên tục từ model thay vì phụ thuộc hoàn toàn vào các split rời rạc của decision tree.

### 4.2 Precomputed what-if cache

- Mô phỏng dài ngày được precompute theo chunk và lưu vào PostgreSQL.
- Cache lưu run metadata, daily KPI và timestep series.
- API Simulation đọc dữ liệu campaign-shaped từ cache thay vì chạy replay nhiều tháng trong HTTP request.
- Có script riêng để precompute và validate cache trước khi publish.
- Cache key bao gồm dataset, scenario, policy, controller version, horizon, top-k và model provenance.

### 4.3 Giao diện What-if Analysis

Trang Simulation đã được tập trung lại vào một workflow chính:

- So sánh measured baseline với predictive MPC replay.
- Chọn khoảng ngày/tháng và policy setpoint.
- Hiển thị energy saved, cost saved, peak reduction, comfort impact và CO₂ avoided.
- Chart có trục thời gian và trục công suất rõ ràng, phân biệt baseline/AI.
- Các KPI có ngữ cảnh thời gian để người dùng biết số liệu thuộc ngày hoặc giai đoạn nào.
- Đã bỏ Scenario comparison workbench và Model validation khỏi giao diện chính để giảm nhiễu.
- Các panel được thiết kế lại cho màn hình rộng và thống nhất card hierarchy.

## 5. Agent, chat và approval workflow

### 5.1 Một runtime thống nhất

- Chat và agent dùng chung `ChatRuntime`; loại bỏ endpoint/client chat cũ trùng chức năng.
- Agent loop có retry/fallback, execution budget, self-describing tools và recovery policy.
- Các invariant về data integrity, policy decision và timeseries query được kiểm tra bằng test.
- Thêm post-session report và cơ chế action tự hết hạn.

### 5.2 LLM routing

- Bổ sung `ModelRouter` dùng pool nhiều provider/model.
- Provider lỗi hoặc rate-limit sẽ bị circuit breaker tạm thời và tự failover sang provider tiếp theo.
- Ghi lại provider/model thực sự trả lời để audit.
- Thêm ZenMux với model `z-ai/glm-5.2` vào provider registry.
- Cache embedder và warm RAG model khi backend khởi động để giảm độ trễ request đầu.

### 5.3 RAG và voice

- Bổ sung system-knowledge RAG và routing giữa câu hỏi về building data với câu hỏi kiến thức hệ thống.
- Chat hỗ trợ Markdown và staged thinking indicator.
- Bổ sung STT/TTS self-hosted; voice hiện dùng Piper Amy với tốc độ đã tinh chỉnh.
- Voice download dùng quy trình atomic `.part → rename` để tránh file model hỏng khi tải dở.
- Floating chatbot và ChatThread dùng chung voice workflow.

### 5.4 Agents & Actions UI

- Thiết kế lại thành layout tập trung gồm Sessions, Chat/Run Trace và Action Queue.
- Mỗi prediction/optimization run được lưu như một chat session hoặc gắn vào session hiện tại.
- Node-by-node trace hiển thị inline trong hội thoại, cùng prediction block, control actions và duration.
- Approval/Reject được phục hồi ngay trong action card và inline run trace.
- Action Queue hỗ trợ pending, executed, blocked và recommended.
- Toàn bộ nội dung hiển thị trên tab Agents & Actions đã được chuyển sang tiếng Anh.
- Sửa composer overlap, session deletion và các trạng thái loading/micro-interaction.

## 6. Dashboard, replay và quan sát tòa nhà

### 6.1 Dashboard KPI

- Bổ sung Building Health Score, fault markers và FDD dashboard.
- Thêm energy/performance analytics cho load, peak, comfort và occupancy.
- Đồng bộ logic trạng thái giữa health card và KPI cards bằng cùng status bands.
- KPI có nhãn `Good`, `Average/Watch`, `Warning/Poor` với màu xanh, vàng và đỏ.
- Thêm hover help để giải thích ý nghĩa, cách đọc và ngưỡng của từng chỉ số.
- Sửa comfort label, setpoint N/A và action queue pagination theo các QC issue.

### 6.2 Replay/streaming demo

- Thêm virtual replay clock dùng timeline của telemetry thay vì wall-clock.
- Có chế độ `Go live` để clock tiến liên tục trong demo và loop trong khoảng dữ liệu.
- Replay anchor được snap vào đúng grid telemetry 30 phút để snapshot query không trả rỗng.
- Top bar hiển thị đồng hồ virtual mượt giữa các lần polling.

### 6.3 3D viewer, climate và CCTV

- Nâng cấp 3D viewer, layer panel, view mode, analysis bar và fault highlighting.
- Thêm climate scenario section và Hanoi climate map.
- CCTV được mở rộng cho 308 zones bằng mapping xác định theo `entity_key` và `room_type`.
- Tên camera/feed được gắn theo ngữ nghĩa khu vực: workspace, meeting room, lobby, auditorium, restaurant, kitchen, parking, circulation, service và technical area.
- Các clip hiện tại là representative count-only demo feeds, không phải camera vật lý riêng của từng zone.

## 7. API và vận hành

Các endpoint/workflow đáng chú ý được thêm hoặc thay đổi:

| Nhóm | API/workflow |
|---|---|
| Model | `/api/ml/model-info`, `/api/ml/predict-zone` |
| Forecast | `/api/forecast/demand?horizon_h=24` |
| Agent | prediction/optimization run, run logs, session-linked trace |
| Simulation | campaign what-if và precomputed predictive replay |
| Replay | start/stop/status streaming clock |
| Electrical | scene API và dữ liệu electrical twin |
| Voice | self-hosted transcription/synthesis |

Vận hành/deploy:

- Thêm `scripts/deploy_vm.sh` có thể resume, tách code deploy khỏi data seed.
- Data seed là bước có gate, tránh vô tình ghi lại dữ liệu lớn khi chỉ cập nhật code.
- Docker Compose được bổ sung MLflow/MinIO config và biến môi trường dataset/model.
- Backend production trên VM đã rebuild và chạy với MLflow client/server `2.17.2`.
- Bốn model đã được đăng ký và xác nhận load từ MLflow production thay vì local fallback.

## 8. Kiểm thử và xác nhận production

Các test mới tập trung vào:

- Data-integrity và policy invariants.
- Agent recovery và ModelRouter failover.
- Replay streaming/grid alignment.
- Agent/chat trace persistence.
- Approval API.
- CCTV mapping trên 308 zones.
- Demand forecast, model contract và prediction horizon.
- Electrical knowledge graph.

Kết quả kiểm thử backend sau lần đồng bộ ML gần nhất:

- `78 passed`
- `13 skipped`
- Validation hard checks cho DuckDB, PostgreSQL, electrical artifacts và model metadata đều đạt.

Smoke test production xác nhận:

- Cả bốn model có source `mlflow`.
- Model contract khớp 308 zones/901.824 rows và cùng SHA-256.
- Forecast 24 giờ trả đủ 48 timestep.
- Prediction run 60 phút hoàn thành với `zone_coverage = 308` và `model_horizon_minutes = 60`.

## 9. Thay đổi hành vi cần lưu ý khi phát triển

1. Không dùng lại ngưỡng `38 kW`; ngưỡng contracted demand hiện là `1.000 kW`.
2. Không giả định forecast 60 phút là một bước; timestep model là 30 phút và horizon dài hơn dùng recursive rollout.
3. Không dùng model local nếu production MLflow khả dụng; alias `@production` là selector chuẩn.
4. Mọi cache hoặc artifact ML phải gắn dataset fingerprint và model provenance.
5. Simulation web không nên chạy replay nhiều tháng trực tiếp; phải dùng precompute/cache.
6. Mọi truy vấn “hiện tại” trên telemetry phải dùng replay clock, không dùng wall-clock server.
7. CCTV là representative feed theo loại phòng; không suy diễn đây là mapping camera vật lý đã khảo sát.

## 10. Các điểm còn cần xử lý

- HVAC surrogate có R² thấp hơn building/zone model. MAE tuyệt đối thấp nhưng MAPE cao do nhiều timestep HVAC gần 0; cần đánh giá thêm theo giờ vận hành và theo mức tải.
- Semantic graph hiện vẫn có nhiều zones chưa có device mapping. Điều này không làm giảm ML coverage 308 zones, nhưng ảnh hưởng chất lượng finding và actionability của agent.
- Cần tiếp tục đối chiếu policy threshold và comfort calibration với dữ liệu/vận hành thực tế trước khi cho phép auto-action ngoài môi trường demo.
- Cần bổ sung model signature/input example khi log MLflow để loại bỏ warning và kiểm tra schema input sớm hơn.
- Representative CCTV feeds cần được thay bằng camera inventory thực nếu triển khai tại tòa nhà thật.

## 11. Commit mốc để tra cứu

| Commit | Nội dung chính |
|---|---|
| `e038b48` | FDD dashboard và occupancy thực tế hơn |
| `14cc002` | Energy & performance analytics |
| `22d74df` | Electrical knowledge graph/digital-twin pipeline |
| `f56a91a` | Electrical 3D viewer và scene API |
| `1b1d83e` | ModelRouter, failover và circuit breaker |
| `222f95b` | Replay streaming mode |
| `9065613` | Self-hosted STT/TTS |
| `851c905` | System-knowledge RAG |
| `21f9d14` | MLflow tracking/registry với PostgreSQL + MinIO |
| `6e8f4c5` | Scientific scenario comparison workbench |
| `2346f25` | Period campaign what-if engine |
| `f8b341a` | Persistent agent run trace trong chat session |
| `4123bcf` | Đồng bộ true-building 308 zones và predictive control |
| `007d9f4` | Đồng bộ KPI status bands và hover help |
| `23ecb3f` | CCTV mapping cho toàn bộ building zones |
| `846aa9a` | Khôi phục approval controls |
| `4e68df4` | Precomputed predictive MPC cache |
| `08ff112` | Retrain và đồng bộ ML theo dataset 308 zones |
| `bbf4310` | Pin MLflow client theo registry server |

## 12. Trạng thái cuối kỳ

- Branch tổng hợp: `zenmux-deploy`
- Remote production branch: `origin/main`
- Commit production tại thời điểm lập tài liệu: `bbf4310`
- Backend API/MLflow trên VM: đang chạy và đã smoke test
- Working tree trước khi tạo tài liệu: sạch

