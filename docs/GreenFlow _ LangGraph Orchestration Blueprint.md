# **GreenFlow | LangGraph Orchestration Blueprint**

## **Digital Twin, Chatbot Query, Optimization Flow và Report Generation**

## **1\. Mục tiêu**

GreenFlow là một nền tảng **agentic digital twin** cho tòa nhà văn phòng, dùng BIM/IFC để dựng mô hình 3D, semantic building graph, zone-level database, baseline simulation và các workflow tối ưu vận hành.

LangGraph trong GreenFlow không chỉ là chatbot. Nó là lớp **orchestration runtime** để điều phối:

Chatbot query  
→ hiểu câu hỏi  
→ tự lập plan  
→ gọi agent/tool cần thiết  
→ đọc state/database  
→ sinh output có số liệu, confidence và link tới zone/device

Dashboard button  
→ gọi workflow cố định hoặc bán-cố-định  
→ chạy agents theo thứ tự  
→ xuất dashboard cards, report, action plan, audit log

Run Optimization  
→ chạy full flow:  
Semantic context → current state → prediction → control action → simulation → policy → approval/execution → compare baseline

Mục tiêu của orchestration:

1\. Kết nối 3D Digital Twin, GraphDB, TimescaleDB, EnergyPlus/surrogate model và dashboard.  
2\. Cho phép user hỏi bằng chatbot hoặc bấm button.  
3\. Tạo action cuối cho toàn tòa nhà thông qua Run Optimization.  
4\. Sinh report PDF qua Report Agent.  
5\. Đảm bảo mọi action quan trọng đều có prediction, simulation, policy check và audit log.  
6\. Dễ mở rộng thêm agent/tool mới mà không phá kiến trúc chính.

---

## **2\. Nguyên tắc thiết kế mới**

Kiến trúc chuẩn nên theo 5 nguyên tắc:

1\. Không có Anomaly Agent riêng.  
   Mọi bất thường về HVAC, lighting, occupancy, comfort, missing metadata hoặc load đều đi qua Building Semantic Agent.

2\. Button ít, rõ, phục vụ demo/product flow.  
   Chỉ giữ các button chính:  
   \- Run Optimization  
   \- Generate Building Semantic Report  
   \- Generate HVAC/Elec Report  
   \- Simulate Peak-Hour Strategy  
   \- Compare Baseline vs Optimized

3\. Chatbot không route cứng quá nhiều workflow.  
   Chatbot chỉ phân loại intent ban đầu.  
   Sau đó Orchestrator tự lập plan để gọi agent/tool phù hợp.

4\. Building Semantic Agent là agent nền tảng.  
   Nó hiểu building graph, zone-device mapping, missing metadata, abnormal state và context cho các agent khác.

5\. Orchestrator là nơi lập kế hoạch.  
   Agent không tự chạy lung tung. Orchestrator đọc state, gọi tool, gọi agent, kiểm tra output và quyết định bước tiếp theo.

---

## **3\. Kiến trúc tổng quan**

User Interface  
│  
├── Chatbot  
│   └── user query  
│  
├── Dashboard Buttons  
│   ├── Run Optimization  
│   ├── Generate Building Semantic Report  
│   ├── Generate HVAC/Elec Report  
│   ├── Simulate Peak-Hour Strategy  
│   └── Compare Baseline vs Optimized  
│  
└── Human Approval Queue  
    └── approve / reject / modify action

↓ API Layer

FastAPI / Node Backend

↓ LangGraph Runtime

Main Orchestrator  
│  
├── Input Router  
├── Intent Classifier  
├── Orchestration Planner  
├── Building Semantic Agent  
├── Data Retrieval Tools  
├── Prediction Agent  
├── Control Agent  
├── Simulation Agent  
├── Policy Engine  
├── Human Approval Node  
├── Mock Execution Node  
├── Report Agent  
├── PDF Tool  
├── Response Composer  
└── Audit Logger

↓ Data / Tools

PostgreSQL / PostGIS  
TimescaleDB  
GraphDB / Neo4j or graph tables  
pgvector / VectorDB  
Object Storage  
3D Asset Store  
EnergyPlus baseline output  
Surrogate / what-if simulation  
Weather API  
Occupancy module

---

## **4\. Core Agents**

GreenFlow MVP chỉ cần 5 agent/lớp chính.

## **4.1. Main Orchestrator**

Main Orchestrator là trung tâm điều phối. Nó không trực tiếp phân tích energy hay control HVAC, mà quyết định:

\- User đang hỏi gì?  
\- Cần gọi agent nào?  
\- Cần đọc database nào?  
\- Cần prediction hay không?  
\- Cần simulation hay không?  
\- Cần report/PDF hay không?  
\- Có cần human approval không?  
\- Output cuối nên là chatbot answer, dashboard card, report link hay action plan?

Nhiệm vụ:

Input validation  
Intent classification  
Plan generation  
Agent/tool calling  
State update  
Error fallback  
Response composition  
Audit logging

Trong chatbot mode, Orchestrator hoạt động như planner động:

User query  
→ classify intent  
→ resolve building/floor/zone/device  
→ lập plan gồm các step cần chạy  
→ execute từng step  
→ tổng hợp output

Trong button mode, Orchestrator dùng workflow template cố định hơn:

Button action  
→ load workflow template  
→ fill state từ selected building/floor/zone/scenario  
→ execute subgraph  
→ trả dashboard result

---

## **4.2. Building Semantic Agent**

Đây là agent quan trọng nhất của hệ thống.

Building Semantic Agent hiểu:

Building  
Floor  
Room  
ThermalZone  
Surface  
Window  
Door  
Material  
HVAC equipment  
Electrical equipment  
Lighting  
Outlet  
Meter  
Camera  
Schedule  
EnergyPlus mapping  
Zone-equipment mapping  
Missing metadata  
Abnormal state

Nó truy xuất 3 lớp dữ liệu:

GraphDB  
→ floor-room-zone-device-system relationships

Structured DB  
→ diện tích, loại zone, thiết bị, trạng thái, phụ tải, metadata

VectorDB  
→ document/specification/report/notes/mô tả kỹ thuật

Nhiệm vụ:

1\. Tạo semantic context cho query hoặc workflow.  
2\. Trả lời câu hỏi về cấu trúc building.  
3\. Xác định zone nào liên quan tới device nào.  
4\. Xác định HVAC/ELE device nào có thể control.  
5\. Kiểm tra missing metadata hoặc mapping quality.  
6\. Phát hiện và giải thích bất thường dựa trên graph \+ state \+ baseline.  
7\. Cung cấp context cho Prediction Agent và Control Agent.  
8\. Sinh nội dung nền cho Building Semantic Report và HVAC/Elec Report.

Lưu ý quan trọng:

Không tạo Anomaly Agent riêng.  
Nếu có “bất thường”, Building Semantic Agent xử lý bằng cách:  
\- đọc semantic graph  
\- đọc current state  
\- so sánh baseline/schedule  
\- xác định entity liên quan  
\- đưa ra explanation

Ví dụ bất thường:

HVAC chạy ở zone không có người.  
Lighting load cao ngoài giờ làm việc.  
Zone comfort risk cao nhưng airflow thấp.  
Device không map được vào zone.  
Meter không khớp với floor/zone.  
Occupancy confidence thấp.  
Cooling load cao hơn baseline.

Output:

{  
  "semantic\_context": {},  
  "target\_zones": \[\],  
  "related\_hvac\_devices": \[\],  
  "related\_electrical\_devices": \[\],  
  "controllable\_devices": \[\],  
  "missing\_metadata": \[\],  
  "abnormal\_findings": \[\],  
  "confidence": 0.86  
}

---

## **4.3. Prediction Agent**

Prediction Agent dự đoán trạng thái tương lai. Nó không tự đề xuất action.

Input:

semantic\_context  
latest\_zone\_state  
occupancy  
weather  
tariff  
schedule  
baseline simulation  
previous action log

Nhiệm vụ:

\- Dự đoán zone energy/load trong 15/30/60 phút.  
\- Dự đoán zone temperature.  
\- Dự đoán comfort risk.  
\- Dự đoán building peak demand risk.  
\- Ước lượng forecast confidence.  
\- Giải thích top features ảnh hưởng prediction.

Output:

{  
  "forecast\_horizon\_minutes": 60,  
  "zone\_load\_forecast": {},  
  "zone\_temperature\_forecast": {},  
  "comfort\_risk": {},  
  "peak\_risk": {},  
  "forecast\_confidence": 0.82,  
  "prediction\_explanation": {}  
}

Ý nghĩa:

Prediction Agent trả lời:  
“Tương lai gần sẽ xảy ra gì?”

Control Agent trả lời:  
“Nên làm gì với dự đoán đó?”

---

## **4.4. Control Agent**

Control Agent sinh candidate action dựa trên:

semantic context  
current state  
prediction result  
comfort risk  
peak risk  
policy constraints

Action đề xuất:

lighting\_reduction  
turn\_off\_non\_critical\_lighting  
hvac\_eco\_mode  
hvac\_setback\_light  
pre\_cooling  
early\_hvac\_shutdown  
peak\_load\_reduction  
demand\_response  
alert\_or\_ticket

Nhiệm vụ:

1\. Tìm cơ hội control.  
2\. Sinh nhiều candidate actions.  
3\. Gắn target zone/device rõ ràng.  
4\. Ước lượng risk ban đầu.  
5\. Rank actions.  
6\. Chọn action hoặc action plan để đưa sang Simulation Agent.

Output:

{  
  "candidate\_actions": \[  
    {  
      "action\_id": "act\_001",  
      "action\_type": "hvac\_eco\_mode",  
      "target\_zone\_ids": \["zone\_level03\_openoffice\_east"\],  
      "target\_device\_ids": \["airterminal\_00451"\],  
      "reason": "Low occupancy and low comfort risk",  
      "expected\_risk": "low"  
    }  
  \],  
  "ranked\_actions": \[\],  
  "selected\_action": {}  
}

Control Agent không execute trực tiếp. Mọi action phải qua:

Simulation Agent  
→ Policy Engine  
→ Human Approval nếu cần  
→ Mock Execution  
→ Audit Logger

---

## **4.5. Simulation Agent**

Simulation Agent kiểm chứng action trước khi áp dụng.

MVP nên có 3 mức simulation:

Level 1 — Rule-based quick estimate  
Nhanh, phù hợp demo.

Level 2 — Surrogate what-if model  
Dùng ML model dự đoán action impact.

Level 3 — EnergyPlus batch / offline  
Dùng cho baseline hoặc report chi tiết.

Input:

selected\_action  
baseline\_state  
forecast\_result  
latest\_zone\_state  
scenario\_config

Output:

{  
  "simulation\_result": {  
    "expected\_saving\_kwh": 4.8,  
    "expected\_cost\_saving": 1.2,  
    "expected\_peak\_reduction\_kw": 6.3,  
    "comfort\_risk\_before": 0.22,  
    "comfort\_risk\_after": 0.24,  
    "confidence": 0.81  
  },  
  "baseline\_vs\_action": {  
    "baseline\_energy\_kwh": 38.4,  
    "action\_energy\_kwh": 33.6,  
    "delta\_kwh": \-4.8  
  }  
}

Simulation Agent trả lời:

“Nếu làm action này thì hậu quả dự kiến là gì?”

---

## **4.6. Policy Engine**

Policy Engine kiểm soát rủi ro. Nó có thể là node/tool độc lập trong LangGraph, không nhất thiết là LLM agent.

Input:

selected\_action  
semantic\_context  
latest\_state  
forecast\_result  
simulation\_result  
policy\_config

Decision:

auto\_run  
approval\_required  
rejected

Guardrails:

Không auto action nếu:  
\- zone là server room / electrical room / security room / utility room  
\- occupancy confidence thấp  
\- forecast confidence thấp  
\- comfort risk sau action vượt ngưỡng  
\- setpoint delta vượt giới hạn  
\- action ảnh hưởng quá nhiều zone  
\- action thuộc nhóm medium/high-risk

Output:

{  
  "decision": "approval\_required",  
  "risk\_level": "medium",  
  "reasons": \[  
    "Pre-cooling affects multiple zones",  
    "Short-term energy may increase before peak window"  
  \],  
  "violated\_rules": \[\],  
  "allowed\_rules": \["peak\_strategy\_allowed"\]  
}

---

## **4.7. Report Agent**

Report Agent tạo Markdown/PDF report.

Report types trong MVP:

building\_semantic\_report  
hvac\_elec\_report  
peak\_strategy\_report  
baseline\_vs\_optimized\_report  
optimization\_summary\_report

Flow:

Report request  
→ Building Semantic Agent lấy context  
→ Data Retrieval lấy state/baseline nếu cần  
→ Report Agent viết Markdown  
→ PDF Tool render PDF  
→ Object Storage lưu file  
→ trả download link

Output:

{  
  "report\_type": "building\_semantic\_report",  
  "report\_markdown": "...",  
  "pdf\_path": "/reports/building\_semantic\_report\_001.pdf",  
  "summary\_cards": \[\]  
}

---

# **5\. Shared LangGraph State**

Tất cả workflow nên dùng một state chung.

class GreenFlowState(TypedDict):  
    \# Request context  
    request\_id: str  
    user\_id: str  
    building\_id: str  
    session\_id: str  
    entrypoint: Literal\["chatbot", "button", "approval\_resume"\]

    \# User input  
    user\_query: Optional\[str\]  
    button\_action: Optional\[str\]  
    selected\_floor\_id: Optional\[str\]  
    selected\_zone\_ids: list\[str\]  
    selected\_device\_ids: list\[str\]  
    scenario\_config: dict

    \# Intent and plan  
    intent: Optional\[str\]  
    orchestration\_plan: list\[dict\]  
    current\_plan\_step: int

    \# Building semantic context  
    building\_summary: dict  
    floors: list\[dict\]  
    zones: list\[dict\]  
    rooms: list\[dict\]  
    zone\_equipment\_map: dict  
    semantic\_context: dict  
    abnormal\_findings: list\[dict\]  
    missing\_metadata: list\[dict\]

    \# Dynamic state  
    latest\_zone\_state: dict  
    latest\_device\_state: dict  
    occupancy\_state: dict  
    weather\_state: dict  
    tariff\_state: dict  
    baseline\_state: dict  
    timeseries\_context: dict

    \# Prediction  
    forecast\_horizon\_minutes: int  
    forecast\_result: dict  
    comfort\_risk: dict  
    peak\_risk: dict  
    forecast\_confidence: float  
    prediction\_explanation: dict

    \# Control  
    candidate\_actions: list\[dict\]  
    ranked\_actions: list\[dict\]  
    selected\_action: Optional\[dict\]  
    final\_action\_plan: list\[dict\]

    \# Simulation  
    simulation\_request: dict  
    simulation\_result: dict  
    baseline\_vs\_action: dict  
    baseline\_vs\_optimized: dict

    \# Policy / approval  
    policy\_config: dict  
    policy\_decision: dict  
    approval\_required: bool  
    approval\_request: Optional\[dict\]  
    human\_decision: Optional\[dict\]

    \# Execution  
    execution\_result: dict  
    mock\_environment\_state: dict

    \# Report / response  
    report\_type: Optional\[str\]  
    report\_markdown: Optional\[str\]  
    pdf\_path: Optional\[str\]  
    dashboard\_cards: list\[dict\]  
    viewer\_updates: list\[dict\]  
    final\_answer: str

    \# Observability  
    agent\_logs: list\[dict\]  
    audit\_log: dict  
    errors: list\[dict\]

Nguyên tắc:

\- Mọi node đọc/ghi vào GreenFlowState.  
\- Agent logs được cập nhật sau mỗi node.  
\- Dashboard đọc agent\_logs để hiển thị progress.  
\- Audit Logger đọc state cuối để ghi trace.

---

# **6\. Main LangGraph Structure**

LangGraph chính nên có cấu trúc tối giản nhưng mở rộng được:

START  
  ↓  
input\_router  
  ↓  
intent\_classifier  
  ↓  
orchestration\_planner  
  ↓  
plan\_executor  
  ↓  
response\_composer  
  ↓  
audit\_logger  
  ↓  
END

Trong đó:

input\_router  
→ phân biệt chatbot/button/approval\_resume

intent\_classifier  
→ nếu chatbot, phân loại intent  
→ nếu button, map button\_action thành intent cố định

orchestration\_planner  
→ lập plan gồm danh sách step cần chạy

plan\_executor  
→ chạy lần lượt agent/tool/subgraph theo plan

response\_composer  
→ gom kết quả thành chatbot answer/dashboard cards/report/action plan

audit\_logger  
→ ghi lại trace

Điểm mạnh của cấu trúc này:

\- Button vẫn có workflow rõ ràng.  
\- Chatbot linh hoạt vì Orchestrator tự lập plan.  
\- Dễ thêm tool mới.  
\- Không cần tạo quá nhiều subgraph cứng.  
\- Không cần Anomaly Agent riêng.

---

# **7\. Entrypoint Logic**

## **7.1. Button Entrypoint**

Button chỉ có 5 loại:

1\. Run Optimization  
2\. Generate Building Semantic Report  
3\. Generate HVAC/Elec Report  
4\. Simulate Peak-Hour Strategy  
5\. Compare Baseline vs Optimized

Mỗi button map thành một workflow template.

{  
  "entrypoint": "button",  
  "button\_action": "run\_optimization",  
  "building\_id": "office\_nordic\_001",  
  "selected\_floor\_id": "level\_03",  
  "selected\_zone\_ids": \[\],  
  "scenario\_config": {  
    "horizon\_minutes": 60,  
    "allow\_auto\_action": true  
  }  
}

---

## **7.2. Chatbot Entrypoint**

Chatbot đi qua:

User query  
→ LLM/rule-based intent classifier  
→ entity resolver  
→ Orchestration Planner  
→ execute plan  
→ response

Intent đề xuất:

semantic\_query  
hvac\_elec\_query  
energy\_query  
comfort\_query  
occupancy\_query  
what\_if\_simulation\_query  
optimization\_request  
peak\_strategy\_query  
baseline\_comparison\_query  
report\_request  
explain\_action\_query  
general\_help

Ví dụ:

“Zone nào HVAC đang chạy dù không có người?”  
→ intent \= semantic\_query / energy\_query  
→ Orchestrator gọi:  
   Building Semantic Agent  
   Data Retrieval Tool  
   Baseline Tool  
   Response Composer

Ví dụ:

“Nếu tăng setpoint 1°C ở open office thì sao?”  
→ intent \= what\_if\_simulation\_query  
→ Orchestrator gọi:  
   Building Semantic Agent  
   Data Retrieval Tool  
   Prediction Agent  
   Simulation Agent  
   Policy Engine optional  
   Response Composer

Ví dụ:

“Tạo report HVAC”  
→ intent \= report\_request  
→ Orchestrator gọi:  
   Building Semantic Agent  
   Report Agent  
   PDF Tool

---

# **8\. Orchestration Planner**

Orchestration Planner là điểm khác biệt chính so với routing cứng.

Planner nhận:

intent  
user\_query  
button\_action  
selected entities  
current state availability  
scenario config

Planner tạo:

{  
  "plan": \[  
    {  
      "step": 1,  
      "node": "building\_semantic\_agent",  
      "purpose": "load building and zone-device context"  
    },  
    {  
      "step": 2,  
      "node": "data\_retrieval\_tools",  
      "purpose": "load latest telemetry and baseline"  
    },  
    {  
      "step": 3,  
      "node": "prediction\_agent",  
      "purpose": "forecast comfort and peak risk"  
    },  
    {  
      "step": 4,  
      "node": "simulation\_agent",  
      "purpose": "run what-if scenario"  
    },  
    {  
      "step": 5,  
      "node": "response\_composer",  
      "purpose": "compose answer and viewer highlights"  
    }  
  \]  
}

Button có plan template mặc định, nhưng vẫn cho phép Planner bổ sung step nếu thiếu dữ liệu.

Ví dụ nếu Generate HVAC/Elec Report nhưng chưa có latest state:

Planner có thể bỏ qua Prediction Agent  
nhưng thêm Data Retrieval Tool để lấy device state nếu có.

---

# **9\. Tool Registry**

## **9.1. Building / Graph Tools**

get\_building\_summary(building\_id)  
get\_floor\_list(building\_id)  
get\_zone\_list(building\_id, floor\_id)  
get\_room\_list(building\_id, zone\_id)  
get\_zone\_equipment\_map(zone\_id)  
get\_graph\_neighbors(entity\_id, depth)  
query\_semantic\_graph(query)  
get\_missing\_metadata\_report(building\_id)  
get\_abnormal\_state\_summary(building\_id, scope)

`get_abnormal_state_summary` không phải Anomaly Agent. Đây chỉ là tool trong Building Semantic Agent.

---

## **9.2. Timeseries / Telemetry Tools**

get\_latest\_zone\_state(zone\_ids)  
get\_latest\_device\_state(device\_ids)  
get\_timeseries(entity\_id, metric, start, end)  
get\_building\_load\_curve(building\_id, start, end)  
get\_energy\_breakdown\_by\_zone(building\_id)  
get\_baseline\_curve(building\_id, start, end)

---

## **9.3. Prediction Tools**

forecast\_zone\_load(zone\_ids, horizon)  
forecast\_zone\_temperature(zone\_ids, horizon)  
forecast\_comfort\_risk(zone\_ids, horizon)  
forecast\_peak\_demand(building\_id, horizon)  
explain\_prediction(prediction\_id)

Không cần `detect_anomaly` ở Prediction Agent. Nếu cần bất thường, Building Semantic Agent dùng baseline/state để tổng hợp.

---

## **9.4. Simulation Tools**

run\_surrogate\_simulation(building\_id, action\_or\_strategy, horizon)  
run\_energyplus\_baseline(building\_id, scenario)  
run\_energyplus\_what\_if(building\_id, action\_or\_strategy)  
compare\_baseline\_vs\_action(baseline, action\_result)  
compare\_baseline\_vs\_optimized(baseline\_run\_id, optimized\_run\_id)

---

## **9.5. Policy / Approval Tools**

load\_policy\_config(building\_id)  
check\_action\_policy(candidate\_action, context)  
create\_approval\_request(action, simulation\_result, explanation)  
get\_human\_approval(approval\_id)

---

## **9.6. Report Tools**

generate\_markdown\_report(report\_type, context)  
render\_report\_to\_pdf(markdown, template)  
save\_artifact(file\_path, metadata)  
create\_download\_link(file\_id)

---

## **9.7. 3D Viewer Tools**

get\_3d\_asset\_map(building\_id)  
get\_entity\_mesh\_map(entity\_ids)  
create\_viewer\_update(entity\_id, style)  
highlight\_entities(entity\_ids, style)

---

# **10\. Button Workflow Details**

## **10.1. Run Optimization**

Đây là button quan trọng nhất.

Mục tiêu:

Chạy full flow để sinh action/action plan cuối cho toàn tòa nhà.

Flow:

START  
  ↓  
Input Router  
  ↓  
Building Semantic Agent  
  ↓  
Data Retrieval Tools  
  ↓  
Prediction Agent  
  ↓  
Control Agent  
  ↓  
Simulation Agent  
  ↓  
Policy Engine  
  ↓  
Policy Route  
      ├── auto\_run  
      ├── approval\_required  
      └── rejected  
  ↓  
Mock Execution / Approval Queue / Reject Log  
  ↓  
Compare Baseline vs Optimized  
  ↓  
Response Composer  
  ↓  
Audit Logger  
  ↓  
END

Output:

{  
  "final\_action\_plan": \[\],  
  "expected\_saving\_kwh": 0,  
  "expected\_cost\_saving": 0,  
  "expected\_peak\_reduction\_kw": 0,  
  "comfort\_risk\_before\_after": {},  
  "policy\_decision": {},  
  "approval\_queue": \[\],  
  "dashboard\_cards": \[\],  
  "viewer\_updates": \[\],  
  "agent\_logs": \[\]  
}

Nên hiển thị trên dashboard:

\- Agent log từng bước  
\- Action cuối được chọn  
\- Expected saving  
\- Comfort impact  
\- Peak impact  
\- Confidence  
\- Policy decision  
\- Approval card nếu cần  
\- Highlight target zone/device trên 3D viewer

---

## **10.2. Generate Building Semantic Report**

Mục tiêu:

Sinh report tổng quan tòa nhà từ semantic graph \+ normalized data \+ mapping quality.

Flow:

START  
  ↓  
Building Semantic Agent  
  ↓  
Data Retrieval Tools optional  
  ↓  
Report Agent  
  ↓  
PDF Tool  
  ↓  
Artifact Saver  
  ↓  
Response Composer  
  ↓  
END

Nội dung report:

Building overview  
Floor hierarchy  
Room/zone hierarchy  
Thermal zone structure  
ARCH/HVAC/ELE/STRUCT mapping summary  
Zone-equipment mapping  
Material/envelope summary  
Missing metadata  
Abnormal state summary nếu có  
EnergyPlus readiness  
Recommended next steps

Output:

building\_semantic\_report.md  
building\_semantic\_report.pdf  
summary cards  
download link

---

## **10.3. Generate HVAC/Elec Report**

Mục tiêu:

Sinh report riêng cho hệ HVAC và Electrical.

Flow:

START  
  ↓  
Building Semantic Agent  
  ↓  
Data Retrieval Tools  
  ↓  
Report Agent  
  ↓  
PDF Tool  
  ↓  
Response Composer  
  ↓  
END

Nội dung report:

HVAC equipment summary  
Air terminals / ducts / pipes / valves / fans / pumps  
Electrical lighting / outlets / boards / cable trays  
Zone-device mapping  
Controllable devices  
Device state nếu có telemetry  
Mapping confidence  
Missing or unmapped devices  
Abnormal HVAC/ELE behavior nếu có  
EnergyPlus usage:  
  \- HVAC phase 1: Ideal Loads per zone  
  \- ELE: Lights/ElectricEquipment by zone

Output:

hvac\_elec\_report.pdf  
device mapping table  
unmapped device table  
dashboard summary cards

---

## **10.4. Simulate Peak-Hour Strategy**

Mục tiêu:

Tìm chiến lược giảm peak demand trong khung giờ cao điểm hoặc heatwave.

Flow:

START  
  ↓  
Building Semantic Agent  
  ↓  
Data Retrieval Tools  
  ↓  
Prediction Agent  
  ↓  
Control Agent generates peak strategies  
  ↓  
Simulation Agent simulates alternatives  
  ↓  
Policy Engine classifies risk  
  ↓  
Response Composer  
  ↓  
Audit Logger  
  ↓  
END

Candidate strategies:

pre\_cooling  
lighting\_reduction in low-occupancy zones  
hvac\_eco\_mode in low-priority zones  
peak\_load\_reduction  
demand\_response  
delay\_non\_critical\_load

Output:

{  
  "ranked\_peak\_strategies": \[\],  
  "best\_strategy": {},  
  "expected\_peak\_reduction\_kw": 0,  
  "expected\_energy\_delta\_kwh": 0,  
  "comfort\_risk\_after": {},  
  "approval\_required": true  
}

Lưu ý:

Peak strategy thường ảnh hưởng nhiều zone,  
nên đa số cần approval hoặc chỉ recommendation trong MVP.

---

## **10.5. Compare Baseline vs Optimized**

Mục tiêu:

So sánh fixed schedule baseline với kết quả agent optimization.

Flow:

START  
  ↓  
Load Baseline Result  
  ↓  
Load Optimized Run / Action Audit Log  
  ↓  
Compare Metrics  
  ↓  
Report Agent optional  
  ↓  
Response Composer  
  ↓  
END

Metrics:

Energy consumption  
Cost  
Peak demand  
HVAC load  
Lighting load  
Plug/equipment load  
Comfort violation  
CO2 avoided estimate  
Action trace  
Policy decisions  
Approval status

Output:

{  
  "baseline\_vs\_optimized": {  
    "baseline\_kwh": 1000,  
    "optimized\_kwh": 880,  
    "saving\_kwh": 120,  
    "saving\_percent": 12,  
    "peak\_reduction\_kw": 18,  
    "comfort\_violation\_delta": 0  
  },  
  "charts": \[\],  
  "action\_trace": \[\]  
}

---

# **11\. Chatbot Logic**

Chatbot không phải một agent riêng tự làm hết. Chatbot là interface gọi Orchestrator.

Flow:

User Query  
  ↓  
Intent Classifier  
  ↓  
Entity Resolver  
  ↓  
Orchestration Planner  
  ↓  
Plan Executor  
  ↓  
Response Composer

Ví dụ 1:

User: “Tầng 3 có vấn đề gì không?”

Intent:  
semantic\_query \+ state\_summary

Plan:  
1\. Building Semantic Agent: resolve Level\_03 zones/devices  
2\. Data Retrieval: latest state for Level\_03  
3\. Building Semantic Agent: summarize abnormal state from baseline/schedule  
4\. Response Composer: answer \+ viewer highlights

Ví dụ 2:

User: “Nếu tăng setpoint 1°C ở open office thì sao?”

Intent:  
what\_if\_simulation\_query

Plan:  
1\. Building Semantic Agent: resolve open office zones  
2\. Data Retrieval: latest state \+ baseline  
3\. Prediction Agent: forecast comfort/load  
4\. Simulation Agent: simulate setpoint \+1°C  
5\. Policy Engine: check comfort constraint  
6\. Response Composer: saving/risk answer

Ví dụ 3:

User: “Tạo report HVAC/Elec”

Intent:  
report\_request

Plan:  
1\. Building Semantic Agent  
2\. Data Retrieval optional  
3\. Report Agent  
4\. PDF Tool  
5\. Response Composer

Chatbot answer nên gồm:

Direct answer  
Evidence/số liệu  
Confidence  
Related zone/device  
Suggested next button/action  
3D viewer highlight nếu có

---

# **12\. Plan Executor**

Plan Executor chạy từng step trong `orchestration_plan`.

Pseudo logic:

def plan\_executor(state):  
    for step in state\["orchestration\_plan"\]:  
        node\_name \= step\["node"\]

        if node\_name \== "building\_semantic\_agent":  
            state \= run\_building\_semantic\_agent(state)

        elif node\_name \== "data\_retrieval":  
            state \= run\_data\_retrieval\_tools(state)

        elif node\_name \== "prediction\_agent":  
            state \= run\_prediction\_agent(state)

        elif node\_name \== "control\_agent":  
            state \= run\_control\_agent(state)

        elif node\_name \== "simulation\_agent":  
            state \= run\_simulation\_agent(state)

        elif node\_name \== "policy\_engine":  
            state \= run\_policy\_engine(state)

        elif node\_name \== "report\_agent":  
            state \= run\_report\_agent(state)

        elif node\_name \== "pdf\_tool":  
            state \= run\_pdf\_tool(state)

        state\["agent\_logs"\].append({  
            "step": step\["step"\],  
            "node": node\_name,  
            "status": "completed",  
            "purpose": step\["purpose"\]  
        })

    return state

Ưu điểm:

\- Chatbot linh hoạt.  
\- Button vẫn ổn định.  
\- Dễ thêm step mới.  
\- Dễ debug agent log.  
\- Dễ checkpoint từng node.

---

# **13\. Response Composer**

Response Composer tạo output cuối cho UI.

Nếu chatbot:

{  
  "final\_answer": "...",  
  "confidence": 0.84,  
  "related\_entities": \[\],  
  "viewer\_updates": \[\],  
  "suggested\_buttons": \[  
    "Run Optimization",  
    "Generate HVAC/Elec Report"  
  \]  
}

Nếu button:

{  
  "dashboard\_cards": \[\],  
  "tables": \[\],  
  "charts": \[\],  
  "agent\_logs": \[\],  
  "viewer\_updates": \[\],  
  "approval\_queue": \[\],  
  "download\_link": null  
}

Response Composer cũng tạo viewer update:

{  
  "entity\_id": "zone\_level03\_openoffice\_east",  
  "style": {  
    "color": "orange",  
    "opacity": 0.55,  
    "label": "High comfort risk",  
    "blink": true  
  }  
}

---

# **14\. Agent Logs**

Dashboard nên hiển thị log như một terminal:

\[✓\] Input validated  
\[✓\] Loaded semantic building graph  
\[✓\] Retrieved latest zone/device state  
\[✓\] Forecasted energy and comfort risk for 60 minutes  
\[✓\] Generated 6 candidate actions  
\[✓\] Simulated top 3 actions  
\[\!\] Approval required for peak-hour pre-cooling  
\[✓\] Baseline vs optimized comparison completed  
\[✓\] Audit log saved

Log item format:

{  
  "step": 4,  
  "node": "Prediction Agent",  
  "status": "completed",  
  "message": "Forecasted comfort and peak risk for 48 zones.",  
  "duration\_ms": 820,  
  "output\_summary": {  
    "high\_comfort\_risk\_zones": 3,  
    "building\_peak\_risk": 0.67  
  }  
}

---

# **15\. Audit Log**

Audit log cần có cho mọi action/simulation/report quan trọng.

Fields:

{  
  "workflow\_run\_id": "run\_001",  
  "timestamp": "...",  
  "entrypoint": "button",  
  "button\_action": "run\_optimization",  
  "intent": "optimization\_request",  
  "target\_zone\_ids": \[\],  
  "target\_device\_ids": \[\],  
  "selected\_action": {},  
  "trigger\_state": {},  
  "forecast\_result\_summary": {},  
  "simulation\_result\_summary": {},  
  "policy\_decision": {},  
  "human\_decision": {},  
  "execution\_status": "executed\_mock | approval\_required | rejected | report\_generated",  
  "expected\_saving\_kwh": 0,  
  "expected\_peak\_reduction\_kw": 0,  
  "comfort\_risk\_before": 0,  
  "comfort\_risk\_after": 0,  
  "explanation": ""  
}

Audit dùng cho:

\- Explain selected action.  
\- Compare baseline vs optimized.  
\- Report generation.  
\- Debug.  
\- Paper/product demo.

---

# **16\. Persistence và Human-in-the-loop**

GreenFlow nên dùng checkpoint cho LangGraph.

Lý do:

\- Run Optimization có nhiều step.  
\- Human approval cần pause/resume.  
\- PDF generation có thể tách riêng.  
\- Debug cần xem state từng node.  
\- Audit trail cần trace đầy đủ.

Nếu policy trả `approval_required`:

LangGraph tạo approval\_request  
→ lưu checkpoint  
→ dashboard hiển thị approval card  
→ user approve/reject/modify  
→ graph resume từ checkpoint  
→ execute hoặc cancel  
→ audit log

---

# **17\. Error Handling**

Mỗi node cần fallback rõ ràng.

Nếu thiếu semantic mapping:  
→ Building Semantic Agent trả missing\_metadata \+ confidence thấp  
→ không auto action

Nếu thiếu telemetry:  
→ dùng baseline/mock/default  
→ đánh dấu low confidence

Nếu prediction fail:  
→ dùng rule-based estimate  
→ policy tự động chuyển approval\_required

Nếu simulation fail:  
→ không auto-run  
→ chỉ recommendation

Nếu PDF fail:  
→ trả Markdown report \+ thông báo lỗi PDF

Nguyên tắc:

Không có đủ dữ liệu → không auto-control.  
Không simulation được → không auto-control.  
Không qua policy → không execute.

---

# **18\. MVP Scope**

## **P0 — Bắt buộc**

Main Orchestrator  
Input Router  
Intent Classifier  
Orchestration Planner  
Plan Executor  
Building Semantic Agent  
Prediction Agent basic  
Control Agent basic  
Simulation Agent rule/surrogate  
Policy Engine  
Report Agent  
PDF Tool  
Audit Logger  
Agent Logs  
5 dashboard buttons  
Chatbot query mode basic

## **P1 — Nên có**

LangGraph checkpoint/resume  
Human approval queue  
Viewer highlights  
Compare baseline vs optimized charts  
Peak-hour strategy simulation  
Report artifact storage

## **P2 — Roadmap**

Real EnergyPlus what-if  
Real BMS integration  
Advanced MPC  
Portfolio-level multi-building graph  
Automatic BIM repair/mapping assistant

---

# **19\. Kết luận**

Kiến trúc LangGraph chuẩn cho GreenFlow nên là:

Main Orchestrator  
\+ Intent Classifier  
\+ Orchestration Planner  
\+ Plan Executor  
\+ Shared GreenFlowState  
\+ Building Semantic Agent  
\+ Prediction Agent  
\+ Control Agent  
\+ Simulation Agent  
\+ Policy Engine  
\+ Report Agent  
\+ Audit Logger

Không cần Anomaly Agent riêng. Mọi bất thường được xử lý bởi:

Building Semantic Agent  
→ đọc graph \+ state \+ baseline  
→ xác định abnormal finding  
→ giải thích theo zone/device/system

Button MVP chỉ cần:

Run Optimization  
Generate Building Semantic Report  
Generate HVAC/Elec Report  
Simulate Peak-Hour Strategy  
Compare Baseline vs Optimized

Chatbot flow chuẩn:

User query  
→ Intent Classifier  
→ Orchestration Planner  
→ gọi agent/tool cần thiết  
→ đọc state  
→ Response Composer

Run Optimization flow chuẩn:

Semantic Context  
→ Current State  
→ Prediction  
→ Control Candidate  
→ Simulation  
→ Policy  
→ Approval/Execution/Reject  
→ Compare Baseline vs Optimized  
→ Audit Log

Với cấu trúc này, GreenFlow dễ mở rộng, dễ demo, dễ audit và vẫn giữ đúng triết lý sản phẩm:  
**hiểu tòa nhà bằng semantic graph, dự đoán tương lai, mô phỏng trước khi hành động, kiểm soát rủi ro bằng policy, và giải thích mọi quyết định bằng dữ liệu.**

