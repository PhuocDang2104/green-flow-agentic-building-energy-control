# GreenFlow — Nguyên lý AI Agent & LangGraph (đọc một mạch)

> Tổng hợp **đúng theo code đang chạy**: state schema, từng node, sơ đồ flow thật từ
> `agent/graph.py`, guardrails/policy, 2 bề mặt agent, và map doc↔code. Khi tài liệu
> thiết kế mâu thuẫn với code → **tin code**. Nguồn: [backend/greenflow/agent/](../backend/greenflow/agent/).

---

## 0. Hai bề mặt agent (đừng nhầm)

| | **① LangGraph Orchestrator** | **② Chatbot function-calling** |
|---|---|---|
| Code | [agent/graph.py](../backend/greenflow/agent/graph.py) + [agent/service.py](../backend/greenflow/agent/service.py) | [chat/service.py](../backend/greenflow/chat/service.py) + [chat/data_tools.py](../backend/greenflow/chat/data_tools.py) |
| Kích hoạt | Dashboard button + chatbot "hành động" (`/api/agent/*`) | Ô chat hỏi-đáp dữ liệu (`/api/chat`) |
| Bản chất | **State machine** có thứ tự cố định, có policy + audit + approval | **Vòng lặp tool-calling** của LLM (≤4 vòng) |
| LLM vai trò | Điều phối/giải thích; **không** tự quyết safety | Chọn tool + diễn giải; SQL tham số hoá, không tự do |
| Khi nào dùng | predict/optimize/peak/report/compare (có ghi action) | tra cứu KPI/timeseries/alerts; có thể *trigger* run ① |

Tài liệu này tập trung **①** (LangGraph) — phần "agentic" lõi; **②** mô tả ở §7.

---

## 1. Sơ đồ flow THẬT (`agent/graph.py`)

`StateGraph(GreenFlowState)` biên dịch thành chuỗi tuyến tính; mọi nhánh động nằm **bên trong** `plan_executor`:

```
START
  → input_router          # nhận request (chatbot | button | approval_resume)
  → intent_classifier      # phân loại intent + resolve zone/device
  → orchestration_planner  # intent/button → DANH SÁCH bước (orchestration_plan)
  → plan_executor          # DUYỆT plan, dispatch từng node con, log mỗi bước
  → response_composer      # gộp câu trả lời + dashboard cards + viewer updates
  → audit_logger           # ghi audit
  → END
```

`plan_executor` không phải 1 node cố định — nó **chạy tuần tự** các node con theo `orchestration_plan`
(`PLAN_NODES`): `building_semantic, prediction, control, simulation, policy, execution, report, compare`.
Mỗi bước ghi 1 dòng `agent_logs` (DB) → UI stream tiến trình như pipeline CI. Node lỗi **không** phá run
(bắt exception, ghi `errors`, chạy tiếp).

---

## 2. State schema — `GreenFlowState` ([agent/state.py](../backend/greenflow/agent/state.py))

`TypedDict(total=False)` — **một dict chảy qua mọi node**, mỗi node trả `dict` cập nhật (merge vào state). Nhóm chính:

| Nhóm | Field tiêu biểu |
|---|---|
| **Request** | `request_id, building_id, session_id, entrypoint` (chatbot/button/approval_resume) |
| **Input** | `user_query, button_action, selected_zone_ids, scenario_config` |
| **Intent/Plan** | `intent, orchestration_plan[], current_plan_step` |
| **Semantic** | `semantic_context, zones[], zone_equipment_map, abnormal_findings[], missing_metadata[]` |
| **Dynamic state** | `latest_zone_state, occupancy_state, weather_state, baseline_state` |
| **Prediction** | `forecast_result, comfort_risk, peak_risk, demand_forecast, forecast_confidence` |
| **Control** | `candidate_actions[], ranked_actions[], selected_actions[], final_action_plan[]` |
| **Simulation** | `simulation_result, baseline_vs_action, baseline_vs_optimized` |
| **Policy/Approval** | `policy_decisions[], approval_required, approval_requests[], human_decision` |
| **Execution** | `execution_result` |
| **Output** | `final_answer, dashboard_cards[], viewer_updates[], report_markdown, pdf_path` |
| **Observability** | `run_id, agent_logs[], errors[]` |

`new_state(**kwargs)` khởi tạo mặc định (list rỗng, `forecast_horizon_minutes=60`, `approval_required=False`).

---

## 3. Từng node làm gì

**Khung (luôn chạy):**

| Node | File | Nhiệm vụ |
|---|---|---|
| `input_router` | graph.py | Ghi nhận entrypoint, mở `agent_logs`. |
| `intent_classifier` | [nodes/intent.py](../backend/greenflow/agent/nodes/intent.py) | Button→intent cố định. Chatbot→**luật keyword song ngữ vi/en**, có LLM *tinh chỉnh* nếu cấu hình; resolve tên zone→`entity_key`. |
| `orchestration_planner` | [nodes/planner.py](../backend/greenflow/agent/nodes/planner.py) | intent/button → `orchestration_plan` (xem §4). |
| `plan_executor` | graph.py | Duyệt plan, gọi node con, summarize + log. |
| `response_composer` | [nodes/composer.py](../backend/greenflow/agent/nodes/composer.py) | Soạn `final_answer` + `dashboard_cards` + `viewer_updates`. |
| `audit_logger` | composer.audit | Ghi audit cuối run. |

**Node con (chạy theo plan):**

| Node | File | Nhiệm vụ |
|---|---|---|
| `building_semantic` | [nodes/building_semantic.py](../backend/greenflow/agent/nodes/building_semantic.py) | Nạp semantic graph (zones/devices qua [tools/graph_tool.py](../backend/greenflow/agent/tools/graph_tool.py)) + phát hiện bất thường (FDD). |
| `prediction` | [nodes/prediction.py](../backend/greenflow/agent/nodes/prediction.py) | Dự báo tải/comfort/peak ngắn hạn (+ demand 24h), kèm `forecast_confidence`. |
| `control` | [nodes/control.py](../backend/greenflow/agent/nodes/control.py) | Sinh `candidate_actions` (từ [sim/actions.py](../backend/greenflow/sim/actions.py)), xếp hạng → `selected_actions`. |
| `simulation` | [nodes/simulation.py](../backend/greenflow/agent/nodes/simulation.py) | Mô phỏng tác động (surrogate/EnergyPlus) → kWh tiết kiệm, peak giảm, comfort sau. |
| `policy` | [nodes/policy_node.py](../backend/greenflow/agent/nodes/policy_node.py) | Gọi **Policy Engine** (§5) → `policy_decisions` + `final_action_plan` + `approval_required`. |
| `execution` | [nodes/execution.py](../backend/greenflow/agent/nodes/execution.py) | **Mock execute**: ghi `actions/action_targets/approval_requests/audit_logs`; auto→executed, medium→pending_approval, reject→blocked. **Không gửi lệnh BMS thật.** |
| `report` | [nodes/report.py](../backend/greenflow/agent/nodes/report.py) | Render báo cáo → Markdown → PDF (`pdf_path`). |
| `compare` | graph.py `_compare` | Lấy KPI baseline-vs-optimized mới nhất. |

---

## 4. Planner — từ điển bước ([nodes/planner.py](../backend/greenflow/agent/nodes/planner.py))

**Button (workflow cố định):**
```
run_optimization / peak_strategy : building_semantic → prediction → control → simulation → policy → execution
building_semantic_report          : building_semantic → report
compare_baseline_optimized        : building_semantic → compare
run_prediction                    : building_semantic → prediction
```
**Chatbot intent (plan động, cùng từ vựng):** vd `what_if_simulation_query` = `building_semantic → prediction → control → simulation`; `energy_query` = `building_semantic → prediction`; `semantic_query` = `building_semantic`.

> Mọi tên bước **khớp 1:1** với `PLAN_NODES` trong graph.py → thêm agent mới = thêm 1 entry ở cả 2 nơi.

---

## 5. Guardrails / Policy Engine ([agent/policy.py](../backend/greenflow/agent/policy.py) + [policy.yaml](../backend/greenflow/agent/policy.yaml))

**Thuần Python, KHÔNG LLM.** Mỗi candidate action (đã mô phỏng) → 1 trong 3 quyết định:

```
rejected          ← action ∈ rejected_actions (vd whole_building_hvac_shutdown)
                    | zone ∈ blocked_zone_types (server/electrical/security/utility room)
                    | |setpoint_delta| > max(policy, settings)
approval_required ← action ∈ approval_required_actions (pre_cooling, demand_response…)
                    | auto-actions bị tắt
                    | VI PHẠM bất kỳ guardrail auto bên dưới (escalate)
auto_run          ← action ∈ allowed_actions VÀ qua HẾT guardrail
```

**Guardrail cho `auto_run`** (policy.yaml `auto_actions`): `max_setpoint_delta_c=1.5`,
`min_occupancy_confidence=0.8`, `min_forecast_confidence=0.6`, `max_comfort_risk_after=0.25`,
`max_peak_risk_after=0.4`, `max_zones_affected=3`, `allowed_zone_types`, `allowed_actions`.

**Regrettable-substitution check** ([agent/regret.py](../backend/greenflow/agent/regret.py), spine D8): action "thắng" KPI mục tiêu
nhưng "thua" chiều khác (comfort kéo dài >15′, rebound >0.5, peak +>5kW) → **không bao giờ auto_run**.

> Triết lý: LLM điều phối; **safety/write-action do rule quyết**. Mọi quyết định kèm `reasons` + `violated_rules`.

---

## 6. Vòng đời 1 run ([agent/service.py](../backend/greenflow/agent/service.py))

```
start_run()    → INSERT agent_runs (status='running') → trả run_id (UI poll ngay)
execute_run()  → new_state() → get_graph().invoke(state)
               → status = 'awaiting_approval' nếu approval_required, else 'completed'
               → _finish_run(): UPDATE agent_runs (final_answer, dashboard_cards, state_json)
resolve_approval(id, approved|rejected)   # entrypoint 'approval_resume'
               → cập nhật approval_requests + actions + audit_logs (human)
```
- Chạy nền (thread) — chatbot `trigger_agent_action` dùng đúng cơ chế này, không block chat.
- **Streaming**: mỗi node ghi `agent_logs(run_id, step, node, status, message, duration_ms)`
  → API `/api/agent/runs/{id}/logs` → UI hiện tiến trình từng bước.
- Bảng liên quan: `agent_runs, agent_logs, actions, action_targets, approval_requests, audit_logs`.

---

## 7. Bề mặt ② — Chatbot function-calling ([chat/service.py](../backend/greenflow/chat/service.py))

```
user → retrieve(kb_chunks: dense bge-m3 ⊕ lexical → RRF → rerank)
     → LLM(messages, tools=TOOL_SPECS)
     → [tool_calls? → dispatch(name,args) → feed kết quả]×(≤4 vòng) → câu trả lời → lưu lịch sử
```
- Tool = query Postgres **tham số hoá cố định** ([chat/data_tools.py](../backend/greenflow/chat/data_tools.py)): `get_building_kpi, get_zone_timeseries,
  get_top_consumers, get_alerts, list_zones`. LLM **chỉ** chọn tool + điền tham số (whitelist) → không SQL injection.
- `trigger_agent_action` = tool *duy nhất* có side-effect: chạy 1 trong 3 button-workflow của bề mặt ① (vẫn qua policy + audit).
- (Hiện chưa wire graph-RAG điện vào `TOOL_SPECS` — xem [GRAPH_RAG_NGUYEN_LY_VA_AGENT.md](GRAPH_RAG_NGUYEN_LY_VA_AGENT.md) §4③.)

---

## 8. Map doc ↔ code

| Khái niệm | Doc thiết kế | Code (sự thật) |
|---|---|---|
| Tổng thể orchestration | [GreenFlow _ LangGraph Orchestration Blueprint.md](GreenFlow%20_%20LangGraph%20Orchestration%20Blueprint.md) | `agent/graph.py` |
| Triết lý agent + guardrails | [project-readme/AGENT_DESIGN.md](project-readme/AGENT_DESIGN.md), [AGENT_POLICY_PROPOSAL.md](project-readme/AGENT_POLICY_PROPOSAL.md) | `agent/policy.py` + `policy.yaml` |
| State schema | Blueprint §5 | `agent/state.py` |
| Cách agent gọi graph-RAG | [GRAPH_RAG_NGUYEN_LY_VA_AGENT.md](GRAPH_RAG_NGUYEN_LY_VA_AGENT.md) | `agent/tools/*`, `chat/*` |

**Lệch giữa doc và code (lưu ý):** Blueprint vẽ từng agent thành node/edge riêng; code **gộp** chúng vào một
`plan_executor` duyệt `orchestration_plan` (gọn hơn, dễ thêm bước). Bản chất luồng giữ nguyên.

---

## 9. Tóm tắt một câu

> GreenFlow agent ① là một **LangGraph state machine** `intent → plan → execute(plan) → compose → audit`,
> trong đó `plan_executor` chạy tuần tự các agent (semantic→predict→control→simulate→**policy**→execute);
> mọi write-action phải qua **Policy Engine thuần-rule** (auto/approval/reject + regret-check) và đều **mock,
> có audit + approval gate** — LLM chỉ điều phối và diễn giải, không tự quyết an toàn. Bề mặt ② là chatbot
> tool-calling tra cứu dữ liệu, có thể *kích* một run của ①.
