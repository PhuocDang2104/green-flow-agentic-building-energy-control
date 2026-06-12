# GreenFlow — Frontend UI/UX Specification

**File:** `GREENFLOW_UI_UX_SPEC.md`  
**Scope:** UI/UX, frontend structure, page layout, component system, API integration points  
**Target:** MVP web app for pitch + extensible product foundation  
**Primary stack:** Next.js / React + TypeScript + TailwindCSS + shadcn/ui + Three.js / React Three Fiber

---

## 1. Product UI Goal

GreenFlow web phải tạo cảm giác như một **professional building operations platform**, không phải một demo AI rối rắm.

Mục tiêu giao diện:

```text
Clean
Minimal
Data-rich nhưng ít chữ
Dễ scan trong 3 giây
3D digital twin là trung tâm
Agent workflow rõ ràng như ChatGPT/Codex đang chạy task
Simulation có bằng chứng baseline vs optimized
```

Phong cách nên tham khảo các web SaaS/e-commerce đẹp: nhiều khoảng trắng, card rõ ràng, shadow nhẹ, bo góc lớn, typography gọn, trạng thái rõ, màu nhấn vừa đủ. Không dùng giao diện neon/cyberpunk/AI quá lố.

---

## 2. Core UI Principles

### 2.1. White-first, teal-accent theme

Theme chính:

```text
Background: trắng / off-white
Surface: white cards
Accent: teal
Text: slate/neutral dark
Border: gray rất nhẹ
Shadow: mềm, tự nhiên
```

Không dùng quá nhiều màu. Chỉ dùng màu mạnh cho trạng thái cần chú ý.

### 2.2. Less text, more structure

Mỗi page nên có:

```text
1 câu title ngắn
1 dòng subtitle nhỏ
KPI cards
Visual chính
Panel phụ
Action button rõ
```

Tránh paragraph dài trong UI. Phần giải thích dài nên nằm trong:

```text
Chatbot panel
Report PDF
Expandable drawer
Tooltip
Details modal
```

### 2.3. Card-based layout

Tất cả nội dung nên nằm trong card/box có:

```text
border-radius: 18–24px
border: 1px solid rgba(15, 23, 42, 0.06)
shadow: 0 8px 24px rgba(15, 23, 42, 0.06)
background: white
```

### 2.4. Dashboard phải nhìn như product thật

Không để giao diện giống notebook hoặc AI playground. Agent là một phần trong product, không phải toàn bộ product.

Agent logs cần nhìn giống:

```text
Codex / deployment log / automation timeline
```

không phải đoạn chat dài lộn xộn.

### 2.5. Every object should be actionable

Người dùng click vào:

```text
Zone
Floor
HVAC device
Light fixture
Action card
Simulation scenario
KPI card
```

thì phải mở được detail drawer hoặc highlight trên 3D view.

---

## 3. Web Routes

GreenFlow MVP có 3 page chính:

```text
/dashboard
/agent-actions
/simulation-baseline
```

Ngoài ra có thể có route phụ sau này:

```text
/settings
/reports
/projects
```

Nhưng MVP chỉ cần 3 route chính.

---

## 4. Global App Shell

Tất cả page dùng chung `AppShell`.

```text
AppShell
├── TopBar
├── MainTabBar
├── PageContainer
│   └── CurrentPage
├── ChatbotPanel
├── CommandPalette optional
└── Footer
```

### 4.1. TopBar

Chức năng:

```text
Logo GreenFlow
Building selector
Scenario selector
Current timestamp / replay mode
Data status indicator
User/avatar menu
```

Visual:

```text
height: 64px
background: white with blur
border-bottom: 1px solid #eef2f7
position: sticky top-0
z-index cao
```

Example layout:

```text
[GreenFlow logo]  [Nordic Office Concrete ▾] [Replay: Jun 11, 14:00 ▾]
                                                      [Data live ●] [User]
```

### 4.2. MainTabBar

Ba tab chính:

```text
Dashboard & 3D View
Agents & Actions
Control & Simulation
```

Route mapping:

```text
Dashboard & 3D View → /dashboard
Agents & Actions → /agent-actions
Control & Simulation → /simulation-baseline
```

Visual yêu cầu:

```text
Floating pill tabbar
White background
Soft shadow
Active tab teal background hoặc teal underline
Icon nhỏ + label ngắn
```

Không nên dùng sidebar nặng ở MVP. Tabbar ngang giúp pitch dễ hiểu hơn.

### 4.3. ChatbotPanel

Chatbot là component global, xuất hiện ở mọi page.

Vị trí:

```text
Desktop: right-side drawer, width 380–440px
Collapsed: floating button bottom-right
Mobile: full-screen sheet
```

Chức năng:

```text
User hỏi building/energy/HVAC/action/simulation
Orchestrator phân loại intent
Agent trả lời có số liệu, confidence, linked entity
Có nút highlight zone/device trên 3D view
Có suggested action buttons
```

Không gọi là “AI magic”. UI nên gọi là:

```text
Building Copilot
Ask GreenFlow
```

### 4.4. Footer

Footer rất nhẹ:

```text
GreenFlow · Simulation-first building operation · Demo environment
```

Không chiếm nhiều diện tích.

---

## 5. Design System

### 5.1. Color tokens

```ts
const colors = {
  background: "#F8FAFC",
  surface: "#FFFFFF",
  surfaceMuted: "#F1F5F9",
  border: "#E2E8F0",
  textPrimary: "#0F172A",
  textSecondary: "#64748B",
  textMuted: "#94A3B8",
  teal: "#0F766E",
  tealLight: "#CCFBF1",
  tealSoft: "#F0FDFA",
  success: "#16A34A",
  warning: "#F59E0B",
  danger: "#DC2626",
  info: "#2563EB"
}
```

### 5.2. Typography

Font đề xuất:

```text
Inter / Geist / SF Pro style
```

Scale:

```text
Page title: 24–28px, semibold
Section title: 16–18px, semibold
Card title: 13–14px, medium
Metric value: 24–36px, semibold
Body: 14px
Caption: 12px
```

### 5.3. Radius and shadow

```css
--radius-card: 20px;
--radius-button: 12px;
--radius-pill: 999px;
--shadow-card: 0 8px 24px rgba(15, 23, 42, 0.06);
--shadow-floating: 0 16px 40px rgba(15, 23, 42, 0.12);
```

### 5.4. Buttons

Primary button:

```text
Teal background
White text
Rounded 12px
Medium weight
```

Secondary button:

```text
White background
Light border
Slate text
```

Danger button chỉ dùng cho reject/cancel unsafe action.

### 5.5. Status colors

```text
Normal → teal/green
Watch → amber
High risk → red
Pending approval → blue/amber
Executed → green
Rejected/blocked → red/slate
```

---

## 6. Page 1 — Dashboard & 3D View

Route:

```text
/dashboard
```

### 6.1. Purpose

Đây là page chính để user inspect toàn bộ tòa nhà.

Nhiệm vụ:

```text
Xem 3D building
Bật/tắt layer
Xem zone state
Click zone/device để inspect
Xem KPI tổng quan
Tải Building Semantic Report
Hỏi chatbot về zone/building/device
```

### 6.2. Page layout

Desktop layout:

```text
┌──────────────────────────────────────────────────────────────┐
│ TopBar                                                       │
├──────────────────────────────────────────────────────────────┤
│ MainTabBar                                                   │
├──────────────────────────────────────────────────────────────┤
│ Page Header: Dashboard & 3D View       [Download Report]     │
├──────────────────────────────────────────────────────────────┤
│ KPI Row: Energy | Peak | Comfort | Occupancy | Actions       │
├──────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┐ ┌──────────────────────────┐ │
│ │ 3D Building Viewer           │ │ Right Insight Panel       │ │
│ │ Three.js / R3F               │ │ Selected zone/device      │ │
│ │                              │ │ Connected devices         │ │
│ │ Layer controls overlay       │ │ Current state             │ │
│ │ Floor selector               │ │ Action suggestions        │ │
│ └─────────────────────────────┘ └──────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ Bottom strip: zone table / compact timeline / events         │
└──────────────────────────────────────────────────────────────┘
```

Recommended grid:

```text
Main viewer: 70%
Insight panel: 30%
```

### 6.3. Header

```text
Title: Dashboard & 3D View
Subtitle: Real-time digital twin overview for zone, energy, comfort and device state.
Button: Download Building Semantic Report
```

Button behavior:

```text
Click Download Building Semantic Report
→ POST /api/agent/report/building-semantic
→ Orchestrator calls Building Semantic Agent + Report Agent + PDF Tool
→ UI shows report generating state
→ Download link appears
```

### 6.4. KPI cards

Cards nên ngắn, không quá nhiều chữ:

```text
Total Load        428 kW        +8% vs baseline
Peak Risk         Medium        0.62 confidence
Comfort Zones     3 watch       1 high risk
Occupancy         214 people    82% confidence
Auto Actions      2 executed    1 pending
```

Component:

```tsx
<KpiCard
  title="Total Load"
  value="428 kW"
  delta="+8% vs baseline"
  status="warning"
/>
```

### 6.5. 3D Building Viewer

Component:

```tsx
<BuildingViewer />
```

Tech:

```text
Three.js / React Three Fiber
Drei useGLTF
GLB files from object storage/public assets
```

Required features:

```text
Orbit / pan / zoom
Floor selection
Object picking
Layer visibility toggles
Entity highlight
Zone heatmap
Tooltip on hover
Click opens detail panel
Reset camera
Screenshot/export optional
```

3D asset layers:

```text
arch_shell.glb
spaces.glb
thermal_zones.glb
hvac_equipment.glb
hvac_ducts.glb
hvac_pipes.glb
electrical_lights.glb
electrical_outlets.glb
electrical_boards.glb
structural_elements.glb
terrain.glb
```

### 6.6. Layer Toggle Panel

Overlay trên viewer, không chiếm nhiều diện tích.

```text
Architecture
Spaces / Zones
HVAC
Electrical
Structural
Terrain
Energy Heatmap
Comfort Risk
Occupancy
Actions
```

Component:

```tsx
<LayerTogglePanel
  layers={layers}
  onToggle={setLayerVisible}
/>
```

Visual:

```text
Floating white panel
Small checkboxes/switches
Soft shadow
Compact text
```

### 6.7. Floor Selector

```text
All Floors
Basement
Level 01
Level 02
Level 03
Level 04
Level 05
Roof
```

Behavior:

```text
Selecting floor fades other floors
Viewer camera moves to selected floor
KPI cards update scope
Zone table filters by floor
```

### 6.8. Viewer interaction

When user clicks a zone:

```text
1. Highlight selected zone in teal border.
2. Open Right Insight Panel.
3. Fetch entity details.
4. Fetch latest state.
5. Fetch connected devices.
6. Show suggested next actions.
```

API:

```http
GET /api/entities/{entity_id}
GET /api/entities/{entity_id}/state
GET /api/entities/{entity_id}/neighbors
GET /api/zones/{zone_id}/devices
```

### 6.9. Right Insight Panel

Component:

```tsx
<EntityInsightPanel />
```

If selected entity is ThermalZone:

```text
Zone name
Floor
Room type
Area / volume
Temperature
Humidity
Occupancy
Cooling load
Lighting load
Plug load
Comfort risk
Peak risk
Connected HVAC devices
Connected electrical devices
Recent actions
```

If selected entity is HVAC device:

```text
Device name
Device type
Served zone
Current status
Power/state if available
Risk level
Control eligibility
Related actions
```

Panel design:

```text
Compact metrics
Small badges
No long paragraph
Expandable “Details” section
```

### 6.10. Bottom Zone Table

A compact table under the viewer:

```text
Zone | Floor | Occupancy | Temp | Load | Comfort | Peak | Status
```

Click row:

```text
Highlight zone in 3D
Open detail panel
```

---

## 7. Page 2 — Agents & Actions

Route:

```text
/agent-actions
```

### 7.1. Purpose

Đây là workspace cho agent workflow và action management.

Nhiệm vụ:

```text
Run Optimization full flow
Run Prediction riêng
Xem agent logs giống ChatGPT/Codex đang chạy
Xem candidate actions
Xem final action plan
Xem approval queue
Xem audit trail
```

### 7.2. Page layout

```text
┌──────────────────────────────────────────────────────────────┐
│ Header: Agents & Actions     [Run Optimization] [Run Predict]│
├──────────────────────────────────────────────────────────────┤
│ Scenario controls: horizon, floor, mode, auto-action toggle   │
├──────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────┐ ┌────────────────────────┐ │
│ │ Agent Run Timeline / Logs      │ │ Action Queue           │ │
│ │ Codex-like progress            │ │ Candidate/final action │ │
│ │ Streaming steps                │ │ Approval cards         │ │
│ └───────────────────────────────┘ └────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ Prediction panel | Policy summary | Audit table              │
└──────────────────────────────────────────────────────────────┘
```

### 7.3. Header buttons

Buttons:

```text
Run Optimization
Run Prediction
```

Run Optimization:

```http
POST /api/agent/run-optimization
```

Flow:

```text
Building Semantic Agent
→ Data Retrieval
→ Prediction Agent
→ Control Agent
→ Simulation Agent
→ Policy Engine
→ Approval/Mock Execution/Reject
→ Compare Baseline vs Optimized
→ Audit Log
```

Run Prediction:

```http
POST /api/agent/predict
```

Flow:

```text
Building Semantic Agent
→ Data Retrieval
→ Prediction Agent
→ Response Composer
```

### 7.4. Scenario controls

Controls:

```text
Forecast horizon: 15 / 30 / 60 minutes
Scope: whole building / floor / selected zones
Scenario: normal / heatwave / after-hours / high occupancy
Auto-action: on/off
Policy profile: conservative / balanced / aggressive demo
```

### 7.5. Agent Run Timeline

Component:

```tsx
<AgentRunTimeline />
```

Purpose:

```text
Hiển thị tiến trình chạy như ChatGPT/Codex/CI pipeline.
```

Step examples:

```text
[✓] Loaded building semantic graph
[✓] Retrieved latest zone and device states
[✓] Forecasted comfort and peak risk for 60 minutes
[✓] Generated 6 candidate actions
[✓] Simulated top 3 actions
[!] Approval required for pre-cooling strategy
[✓] Audit log saved
```

Each log item:

```json
{
  "step": 4,
  "node": "Prediction Agent",
  "status": "completed",
  "message": "Forecasted comfort and peak risk for 48 zones.",
  "duration_ms": 820,
  "output_summary": {
    "high_comfort_risk_zones": 3,
    "building_peak_risk": 0.67
  }
}
```

### 7.6. Action Queue

Component:

```tsx
<ActionQueue />
```

Tabs inside card:

```text
Recommended
Pending Approval
Executed
Blocked
```

Action card includes:

```text
Action type
Target zone/device
Expected saving
Expected peak reduction
Comfort risk after
Forecast confidence
Policy decision
Approve / Reject / Simulate / Explain
```

### 7.7. Prediction Panel

Shows output of Prediction Agent:

```text
Peak risk forecast
Comfort risk forecast
High-risk zones
Forecast confidence
Top features
```

API:

```http
GET /api/predictions/latest?building_id=...
POST /api/agent/predict
```

### 7.8. Policy Summary Panel

Shows:

```text
Auto-actions enabled/disabled
Max setpoint delta
Min occupancy confidence
Blocked zone types
Recent unsafe actions blocked
```

### 7.9. Audit Table

Columns:

```text
Time | Action | Target | Decision | Saving | Comfort | Status
```

Click row opens `ActionDetailDrawer`.

---

## 8. Page 3 — Control & Simulation

Route:

```text
/simulation-baseline
```

### 8.1. Purpose

Đây là page chứng minh GreenFlow có giá trị bằng mô phỏng.

Nhiệm vụ:

```text
So sánh baseline fixed schedule vs optimized agent result
Xem simulation runs đã chạy
Simulate recommended action/strategy
So sánh nhiều tình huống peak-hour
Hiển thị KPI tiết kiệm và comfort impact
```

### 8.2. Page layout

```text
┌──────────────────────────────────────────────────────────────┐
│ Header: Control & Simulation     [Simulate Recommended]      │
├──────────────────────────────────────────────────────────────┤
│ Scenario selector + run selector + time range                │
├──────────────────────────────────────────────────────────────┤
│ KPI comparison row: kWh | Cost | Peak | Comfort | CO2        │
├──────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────┐ ┌───────────────────────────┐ │
│ │ Baseline vs Optimized Chart │ │ Simulation Summary Panel   │ │
│ └────────────────────────────┘ └───────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ Scenario comparison table + action trace                     │
└──────────────────────────────────────────────────────────────┘
```

### 8.3. Header button

Button:

```text
Simulate Recommended Actions
```

API:

```http
POST /api/simulation/simulate-recommended-actions
```

Flow:

```text
Building Semantic Agent
→ Data Retrieval
→ Control Agent creates recommended strategies
→ Simulation Agent simulates alternatives
→ Policy Engine classifies risk
→ Response Composer returns ranking
```

### 8.4. KPI comparison row

Cards:

```text
Energy Saved       120 kWh       -12.0%
Cost Saved         420,000 VND   estimated
Peak Reduction     18 kW         during 14:00–16:00
Comfort Impact     0 min         violation increase
CO2 Avoided        58 kg         estimate
```

### 8.5. Baseline vs Optimized Chart

Component:

```tsx
<BaselineOptimizedChart />
```

Metrics:

```text
Total electricity
HVAC load
Lighting load
Plug load
Temperature
Comfort risk
Peak demand
```

Chart behavior:

```text
Toggle metric
Hover shows baseline/optimized delta
Mark action timestamps
Highlight peak window
```

### 8.6. Simulation Summary Panel

Shows:

```text
Baseline run
Optimized run
Weather file/scenario
Schedule assumptions
Actions applied
Simulation engine
Confidence/limitations
```

Should be honest:

```text
This is a what-if counterfactual simulation, not direct real-time control.
```

### 8.7. Scenario Comparison Table

Columns:

```text
Scenario | Energy | Cost | Peak | Comfort | Approval | Rank
```

Examples:

```text
Baseline fixed schedule
Lighting reduction only
HVAC eco mode low occupancy
Pre-cooling peak strategy
Demand response conservative
```

### 8.8. Action Trace

Timeline of actions used in optimized scenario:

```text
09:00 — Lighting reduction in Level 03 Meeting Rooms
11:15 — HVAC eco mode for low occupancy open office
13:30 — Pre-cooling before peak window, approval required
14:00 — Peak strategy active
```

---

## 9. Mandatory Components

### 9.1. AppShell

```tsx
<AppShell>
  <TopBar />
  <MainTabBar />
  <PageContainer>{children}</PageContainer>
  <ChatbotPanel />
  <Footer />
</AppShell>
```

### 9.2. MainTabBar

Tabs:

```text
Dashboard & 3D View
Agents & Actions
Control & Simulation
```

### 9.3. ChatbotPanel

Must support:

```text
Streaming response
Suggested prompts
Linked entity chips
Run button suggestions
Highlight in viewer
```

API:

```http
POST /api/chat
GET /api/chat/sessions/{session_id}
```

### 9.4. BuildingViewer

Must support:

```text
Load GLB layers
Object picking
Layer visibility
Heatmap coloring
Entity highlight
Tooltip
Camera reset
Floor isolate
```

### 9.5. Other required components

```text
LayerTogglePanel
EntityInsightPanel
KpiCard
AgentRunTimeline
ActionQueue
ApprovalCard
PredictionPanel
PolicySummaryCard
AuditTable
BaselineOptimizedChart
ScenarioSelector
ScenarioComparisonTable
ActionTraceTimeline
Footer
```

---

## 10. Frontend Folder Structure

Recommended Next.js app structure:

```text
web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── dashboard/
│   │   └── page.tsx
│   ├── agent-actions/
│   │   └── page.tsx
│   ├── simulation-baseline/
│   │   └── page.tsx
│   └── globals.css
│
├── components/
│   ├── shell/
│   │   ├── AppShell.tsx
│   │   ├── TopBar.tsx
│   │   ├── MainTabBar.tsx
│   │   ├── PageHeader.tsx
│   │   └── Footer.tsx
│   ├── viewer/
│   │   ├── BuildingViewer.tsx
│   │   ├── GLBLayer.tsx
│   │   ├── LayerTogglePanel.tsx
│   │   ├── FloorSelector.tsx
│   │   ├── ViewerToolbar.tsx
│   │   └── EntityTooltip.tsx
│   ├── dashboard/
│   │   ├── KpiCard.tsx
│   │   ├── EntityInsightPanel.tsx
│   │   ├── ZoneStateTable.tsx
│   │   └── ReportDownloadButton.tsx
│   ├── agent/
│   │   ├── AgentRunTimeline.tsx
│   │   ├── ActionQueue.tsx
│   │   ├── ActionCard.tsx
│   │   ├── ApprovalCard.tsx
│   │   ├── PredictionPanel.tsx
│   │   ├── PolicySummaryCard.tsx
│   │   └── AuditTable.tsx
│   ├── simulation/
│   │   ├── BaselineOptimizedChart.tsx
│   │   ├── SimulationSummaryPanel.tsx
│   │   ├── ScenarioComparisonTable.tsx
│   │   ├── ScenarioSelector.tsx
│   │   └── ActionTraceTimeline.tsx
│   └── chatbot/
│       ├── ChatbotPanel.tsx
│       ├── ChatMessage.tsx
│       ├── SuggestedPrompts.tsx
│       └── LinkedEntityChips.tsx
├── lib/
│   ├── api.ts
│   ├── types.ts
│   ├── viewer.ts
│   ├── format.ts
│   └── constants.ts
├── hooks/
│   ├── useBuildingState.ts
│   ├── useAgentRun.ts
│   ├── useSimulationRun.ts
│   ├── useChat.ts
│   └── useViewerSelection.ts
└── public/
    └── models/
        └── office_nordic/
            ├── arch_shell.glb
            ├── spaces.glb
            ├── hvac.glb
            ├── electrical.glb
            └── terrain.glb
```

---

## 11. API Integration Contract

### 11.1. Building and dashboard APIs

```http
GET /api/buildings
GET /api/buildings/{building_id}
GET /api/buildings/{building_id}/summary
GET /api/buildings/{building_id}/kpis
GET /api/floors?building_id={building_id}
GET /api/zones?building_id={building_id}&floor_id={floor_id}
GET /api/zones/{zone_id}/state
GET /api/zones/{zone_id}/devices
GET /api/entities/{entity_id}
GET /api/entities/{entity_id}/neighbors
GET /api/entities/{entity_id}/state
```

### 11.2. 3D asset APIs

```http
GET /api/3d/assets?building_id={building_id}
GET /api/3d/mesh-map?building_id={building_id}
GET /api/3d/entity-map?building_id={building_id}
```

### 11.3. Agent APIs

```http
POST /api/agent/run-optimization
POST /api/agent/predict
POST /api/agent/report/building-semantic
POST /api/agent/report/hvac-elec
GET /api/agent/runs/{run_id}
GET /api/agent/runs/{run_id}/logs
GET /api/agent/runs/{run_id}/stream
```

### 11.4. Action APIs

```http
GET /api/actions?building_id={building_id}
GET /api/actions/{action_id}
POST /api/actions/{action_id}/approve
POST /api/actions/{action_id}/reject
POST /api/actions/{action_id}/simulate
GET /api/actions/audit-log?building_id={building_id}
```

### 11.5. Simulation APIs

```http
GET /api/simulations?building_id={building_id}
GET /api/simulations/{run_id}
GET /api/simulations/{run_id}/baseline-vs-optimized
POST /api/simulation/simulate-peak-strategy
POST /api/simulation/simulate-recommended-actions
POST /api/simulation/compare-baseline-optimized
```

### 11.6. Chatbot APIs

```http
POST /api/chat
GET /api/chat/sessions/{session_id}
```

Response should include:

```json
{
  "answer": "...",
  "confidence": 0.84,
  "related_entities": [],
  "viewer_updates": [],
  "suggested_buttons": [],
  "agent_run_id": "run_001"
}
```

---

## 12. UI State Model

Frontend should maintain:

```ts
type UIState = {
  buildingId: string
  currentRoute: "/dashboard" | "/agent-actions" | "/simulation-baseline"
  selectedFloorId?: string
  selectedEntityId?: string
  selectedScenarioId: string
  layers: LayerState
  viewerUpdates: ViewerUpdate[]
  activeAgentRunId?: string
  chatbotOpen: boolean
}
```

Layer state:

```ts
type LayerState = {
  architecture: boolean
  spaces: boolean
  hvac: boolean
  electrical: boolean
  structural: boolean
  terrain: boolean
  energyHeatmap: boolean
  comfortRisk: boolean
  occupancy: boolean
  actions: boolean
}
```

Viewer update:

```ts
type ViewerUpdate = {
  entity_id: string
  style: {
    color?: string
    opacity?: number
    label?: string
    blink?: boolean
    outline?: boolean
  }
}
```

---

## 13. UX Flow Summary

### 13.1. Dashboard report flow

```text
User opens Dashboard
→ sees 3D model + KPI cards
→ selects floor/zone
→ clicks Download Building Semantic Report
→ UI starts report generation
→ Agent logs can appear in compact toast/drawer
→ PDF link appears
```

### 13.2. Optimization flow

```text
User opens Agents & Actions
→ selects scenario and horizon
→ clicks Run Optimization
→ Agent timeline streams logs
→ Candidate actions appear
→ Simulation result appears
→ Policy decision appears
→ Approval required card appears if needed
→ Final action plan saved to audit log
```

### 13.3. Simulation flow

```text
User opens Control & Simulation
→ selects baseline and optimized run
→ sees KPI comparison
→ clicks Simulate Recommended Actions
→ Control Agent proposes strategies
→ Simulation Agent tests scenarios
→ chart/table update
→ user can compare strategies
```

### 13.4. Chatbot flow

```text
User opens chatbot on any page
→ asks about zone/action/simulation/report
→ chatbot calls Orchestrator
→ answer includes evidence and confidence
→ linked chips highlight zone/device/action in UI
```

---

## 14. Responsive Design

Desktop first for pitch.

Breakpoints:

```text
Desktop >= 1280px
Laptop >= 1024px
Tablet >= 768px
Mobile < 768px
```

Desktop:

```text
2-column layouts
3D viewer large
Chatbot drawer right
```

Tablet:

```text
Viewer full width
Insight panel below
Tabbar remains top
```

Mobile:

```text
Cards stack vertically
3D viewer simplified
Chatbot full-screen sheet
Tables become cards
```

MVP priority:

```text
Desktop/laptop polished first.
Mobile acceptable but not primary.
```

---

## 15. Micro-interactions

Use subtle animation only:

```text
Card hover lift: translateY(-1px)
Button hover: slightly darker teal
Tab transition: 150–200ms
Viewer highlight pulse: slow, not distracting
Agent log streaming: line-by-line reveal
Skeleton loading: soft shimmer
```

Avoid:

```text
Overly colorful gradients
Typing animation everywhere
AI robot icons
Excessive glow
Dark cyberpunk theme
```

---

## 16. Accessibility and Readability

Requirements:

```text
Text contrast AA-level
All buttons have labels
Keyboard focus visible
Charts have tooltip and data table fallback
Color is not the only signal: use icon/label too
Click targets >= 40px height
```

---

## 17. Implementation Priority

### P0

```text
AppShell
TopBar
MainTabBar
Dashboard page
3D BuildingViewer basic
LayerTogglePanel
KpiCard
EntityInsightPanel
Agents & Actions page
Run Optimization button
AgentRunTimeline
ActionQueue
Control & Simulation page
BaselineOptimizedChart
ChatbotPanel basic
API client layer
```

### P1

```text
Viewer heatmap
Floor isolate
Report download full flow
Approval queue
Simulation scenario table
Streaming agent logs
Suggested chatbot prompts
```

### P2

```text
Advanced 3D interactions
Section cut / floor explode
Portfolio/building selector
Custom dashboard layout
Advanced report designer
Mobile polish
```

---

## 18. Final UI North Star

GreenFlow UI should feel like:

```text
A clean Apple/Stripe-style SaaS dashboard
+ a polished 3D building viewer
+ a Codex-like agent execution timeline
+ a simulation evidence workspace
```

Not like:

```text
A raw AI chat app
A BIM desktop tool
A chaotic engineering dashboard
A notebook with plots
```

The user should understand the product in this order:

```text
1. This is my building.
2. These are the zones and devices.
3. This is the current energy/comfort state.
4. The agent can explain what is happening.
5. The agent can propose safe actions.
6. Every action is simulated and audited.
7. I can compare optimized operation against baseline.
```
