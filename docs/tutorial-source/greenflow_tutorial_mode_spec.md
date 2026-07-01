# GreenFlow Tutorial Mode - Technical Product Spec

Source PDF for Claude Code to inspect:

`/workspace/.cache/Greenflow TUTORIAL .pdf`

Markdown-safe PDF copy:

`/workspace/outputs/greenflow_tutorial_source.pdf`

Rendered visual previews generated from the PDF:

- Tab 1 contact sheet: `/workspace/tmp/pdfs/tab1_contact.png`
- Tab 2 contact sheet: `/workspace/tmp/pdfs/tab2_contact.png`
- Tab 3 contact sheet: `/workspace/tmp/pdfs/tab3_contact.png`
- Tab 4 contact sheet: `/workspace/tmp/pdfs/tab4_contact.png`

PDF structure:

- Pages 1-17: Tab 1, `Dashboard & 3D View`
- Pages 18-26: Tab 2, `Electrical Graph`
- Pages 27-33: Tab 3, `Agents & Actions`
- Pages 34-39: Tab 4, `Validation`

## 1. Product Goal

Build an `Enter Tutorial Mode` button for GreenFlow that launches a professional guided demo of the four main tabs. The tutorial should feel like a product walkthrough for a serious energy digital twin platform, not a static slide deck.

The core idea:

1. Orient the user: show what each tab is for.
2. Demonstrate value: show how GreenFlow observes the building, understands risk, simulates control, asks for human approval, and validates impact.
3. Keep the user in control: allow skip, back, next, pause, replay, and exit.
4. Avoid destructive actions: tutorial mode must never execute real building controls.

The tutorial is for first-time users, demos, judges, investors, and operators who need to understand the product quickly.

## 2. Recommended UX Direction

Use a guided demo mode, not a long tooltip-only tour.

Patterns reviewed:

- React Joyride supports step-based tours with controlled callbacks and is easy to integrate in React apps: https://docs.react-joyride.com/callback
- Driver.js supports animated product tours, spotlight overlay, progress display, overlay color/opacity, and custom popovers: https://driverjs.com/docs/animated-tour and https://driverjs.com/docs/styling-overlay
- Appcues onboarding guidance recommends tours that are short, contextual, tied to activation goals, and not forced through every feature: https://www.appcues.com/blog/product-tours-walkthroughs-ultimate-guide
- WAI-ARIA modal dialog guidance requires focus trapping, Escape handling, and correct modal semantics for overlay experiences: https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/

GreenFlow has complex 3D scenes, tabs, charts, agent timelines, and simulated workflows. Because of that, a custom `TutorialProvider` is preferred over a fully black-box product-tour library. A small tour library can still be used for popover positioning, but route switching, 3D camera movement, chart hover simulation, and agent timeline playback should be owned by GreenFlow.

Recommended implementation:

- Use a custom `TutorialProvider` and `TutorialOverlay`.
- Use `data-tour-id` attributes as stable selectors.
- Use `framer-motion` or existing animation utilities if already installed.
- Use `@floating-ui/react` or existing popover primitives for panel positioning.
- If the codebase already uses a UI library with Dialog/Popover components, reuse it.
- Avoid adding a heavy onboarding vendor dependency unless the app already has one.

## 3. Entry Points

Add a primary tutorial entry button:

- Label: `Tutorial Mode`
- Icon: play-circle, sparkle, route, or help-circle from the existing icon set.
- Position: top-right header area, near `Go live` or user/avatar controls.
- Tooltip: `Walk through GreenFlow in 3 minutes`
- Visual style: secondary outline button by default, green filled button during first login prompt.

Also add optional entry points:

- First-login modal: `Take the 3-minute tour` and `Skip for now`
- Help menu item: `Replay tutorial`
- Empty-state CTA in dashboard: `Show me how GreenFlow works`

Persistence:

- Store completion in local storage or user profile:
  - `greenflow.tutorial.completed = true`
  - `greenflow.tutorial.completedAt = ISO timestamp`
  - `greenflow.tutorial.version = "2026-07-greenflow-v1"`
- If the tutorial content changes, show `Replay updated tour` instead of forcing it again.

## 4. Tutorial Mode State Machine

States:

- `idle`
- `preparing`
- `running`
- `paused`
- `completed`
- `exited`
- `error`

Events:

- `START_TUTORIAL`
- `NEXT_STEP`
- `PREVIOUS_STEP`
- `SKIP_TUTORIAL`
- `PAUSE_TUTORIAL`
- `RESUME_TUTORIAL`
- `COMPLETE_TUTORIAL`
- `ROUTE_READY`
- `TARGET_READY`
- `TARGET_MISSING`
- `ACTION_PREVIEW_READY`

Important behavior:

- Tutorial mode controls tab navigation.
- Tutorial mode can open panels, select layers, select zones, switch graph filters, run simulated optimization, and change validation metric views.
- Tutorial mode must not call real execution endpoints.
- If a target selector is missing, show a centered fallback card instead of breaking the tour.

## 5. Global UI Behavior

Overlay:

- Dark translucent app overlay: `rgba(3, 12, 18, 0.56)`.
- Spotlight cutout around active UI element.
- Use 12-16 px spotlight padding.
- Spotlight border: soft GreenFlow green glow, not thick dashed lines.
- For dashboard/3D steps, allow the highlighted 3D canvas to remain visually bright.

Panel:

- Compact floating panel, max width 380-440 px.
- Rounded 8 px, clean shadow, no nested cards.
- Header includes:
  - Step title
  - Current section label: `Dashboard`, `Electrical Twin`, `Agents`, `Validation`
  - Progress: `4 / 24`
- Body:
  - 1 short paragraph, 2-3 lines max.
  - Optional mini metric chips.
- Footer:
  - `Back`
  - `Next`
  - `Skip`
  - `Pause` if auto-play is enabled.

Progress rail:

- A subtle bottom progress bar divided into 4 chapters:
  - Observe
  - Understand
  - Optimize
  - Validate
- Each chapter maps to one tab.

Motion:

- Overlay fade: 160-220 ms.
- Spotlight morph: 280-420 ms.
- Popover slide/fade: 180-260 ms.
- 3D camera movement: 800-1400 ms with ease-out.
- Graph node pulse: 900 ms loop, max 2-3 loops.
- Timeline reveal in Agents tab: sequential 250-400 ms per agent.
- Respect `prefers-reduced-motion`: disable camera auto-orbit, pulse, and long transitions.

## 6. Selector Contract

Claude Code should add stable `data-tour-id` attributes to the existing UI. Do not rely on CSS class names or text content.

Recommended selectors:

| UI Area | `data-tour-id` |
|---|---|
| Tutorial button | `tutorial-entry` |
| Sidebar Dashboard tab | `nav-dashboard-3d` |
| Sidebar Electrical tab | `nav-electrical-graph` |
| Sidebar Agents tab | `nav-agents-actions` |
| Sidebar Validation tab | `nav-validation` |
| Health index cards wrapper | `dashboard-health-index` |
| Air quality card | `health-air-quality` |
| Energy/load card | `health-energy-load` |
| Thermal comfort card | `health-thermal-comfort` |
| Equipment health card | `health-equipment-health` |
| 3D viewer canvas/wrapper | `digital-twin-viewer` |
| Layer panel | `digital-twin-layers` |
| Technical systems group | `layer-technical-systems` |
| Spatial analytics group | `layer-spatial-analytics` |
| Zone inspector | `zone-inspector` |
| Zone state table | `zone-state-table` |
| CCTV occupancy preview | `cctv-occupancy-preview` |
| Weather panel/map | `weather-context-panel` |
| Electrical KPI cards | `electrical-kpis` |
| Electrical graph canvas | `electrical-graph-canvas` |
| Electrical filter controls | `electrical-filter-controls` |
| Electrical node inspector | `electrical-node-inspector` |
| Chatbot launcher | `ai-chatbot-launcher` |
| Chatbot panel | `ai-chatbot-panel` |
| Agents chat/session list | `agent-session-list` |
| Agents main chat | `agent-main-chat` |
| Run optimization button | `run-optimization-button` |
| Agent execution timeline | `agent-execution-timeline` |
| Prediction agent block | `prediction-agent-block` |
| Control agent block | `control-agent-block` |
| Simulation agent block | `simulation-agent-block` |
| Policy engine block | `policy-engine-block` |
| Action queue | `action-queue` |
| Approval card | `approval-card` |
| Validation summary cards | `validation-summary-cards` |
| Validation chart | `validation-timeseries-chart` |
| Validation metric selector | `validation-metric-selector` |
| El Nino toggle | `validation-el-nino-toggle` |
| Building semantic report button | `building-semantic-report-button` |

## 7. Route And Tab Orchestration

Each tutorial step should define:

```ts
type TutorialStep = {
  id: string;
  chapter: "observe" | "understand" | "optimize" | "validate";
  route: "/dashboard" | "/electrical" | "/agents" | "/validation";
  target?: string;
  title: string;
  body: string;
  placement?: "top" | "right" | "bottom" | "left" | "center";
  before?: TutorialAction[];
  after?: TutorialAction[];
  waitFor?: string[];
  allowInteraction?: boolean;
  autoAdvanceMs?: number;
};
```

Supported `TutorialAction` examples:

```ts
type TutorialAction =
  | { type: "switchTab"; tab: "dashboard" | "electrical" | "agents" | "validation" }
  | { type: "setLayer"; layer: string; enabled: boolean }
  | { type: "setHeatmap"; heatmap: "electricalLoad" | "hvacPower" | "energy" | "comfort" | "occupancy" | "faults"; enabled: boolean }
  | { type: "selectZone"; zoneId: string }
  | { type: "setCameraPreset"; preset: string }
  | { type: "highlightGraphNode"; nodeId: string }
  | { type: "setElectricalFilter"; filter: "overview" | "panel" | "loadhead" }
  | { type: "openChatbot"; prompt?: string }
  | { type: "startOptimizationPreview" }
  | { type: "revealAgentTimeline"; until: "semantic" | "prediction" | "control" | "simulation" | "approval" }
  | { type: "setValidationMetric"; metric: "energyUse" | "powerDemand" | "hvacControl" | "co2" }
  | { type: "scrubChartTo"; timestamp: string };
```

## 8. Full Tutorial Storyboard

Target duration:

- Manual mode: 3-5 minutes.
- Auto-play demo mode: 2.5-3 minutes.
- Recommended step count: 24 steps.

The PDF has 39 visual pages, but the implementation should merge related pages into stronger, fewer tutorial steps.

### Chapter 1 - Observe: Dashboard & 3D View

PDF pages: 1-17.

Step 1 - Welcome to GreenFlow

- Route: Dashboard & 3D View.
- Target: centered modal, no specific element.
- Purpose: set context.
- Copy:
  - `GreenFlow helps operators see building performance, inspect the digital twin, run risk-controlled optimization, and validate energy impact. This tutorial shows the full loop.`
- Animation: subtle zoom into dashboard, progress rail appears.

Step 2 - Building Performance Index

- Target: `dashboard-health-index`.
- PDF reference: page 1.
- Copy:
  - `This first view summarizes the building across air quality, energy/load demand, thermal comfort, and equipment health. Higher scores mean better operational condition.`
- Visual behavior:
  - Pulse the four score cards once.
  - Show metric chips: `Air Quality`, `Energy`, `Comfort`, `Equipment`.

Step 3 - Enter the 3D Digital Twin

- Target: `digital-twin-viewer`.
- PDF reference: pages 2-3.
- Before:
  - Set camera to `building-overview`.
  - Enable `Architecture`.
  - Disable heavy heatmaps.
- Copy:
  - `The 3D digital twin turns BIM and operational data into an explorable building model. Users can move from whole-building context to zone-level detail.`
- Animation:
  - Smooth camera orbit from exterior to front facade.

Step 4 - Technical Layers

- Target: `digital-twin-layers`.
- PDF reference: pages 4-8.
- Before:
  - Toggle `Structural`, `Electrical`, and `HVAC` in sequence.
- Copy:
  - `Layers separate architecture, structure, electrical systems, HVAC, and spaces so users can inspect only what matters for the current decision.`
- Animation:
  - Layer checkboxes activate one by one.
  - Electrical and HVAC colors brighten briefly.

Step 5 - System Heatmaps

- Target: bottom-right heatmap controls in 3D viewer.
- PDF reference: pages 7-10.
- Before:
  - Enable `Electrical % Load heatmap`.
  - Enable `HVAC Power heatmap`.
- Copy:
  - `Technical systems can show their own heatmaps, such as electrical load percentage and HVAC power. This avoids mixing system-level risk with zone comfort scores.`
- Animation:
  - Heatmap legend sweeps from low to high.

Step 6 - Inspect A Zone

- Target: selected zone or `zone-inspector`.
- PDF reference: pages 9-11.
- Before:
  - Enable `Spaces / Zones`.
  - Select a demo zone, for example `Open Office` or zone `220`.
  - Set camera preset `zone-focus`.
- Copy:
  - `Clicking a zone opens its technical state: temperature, setpoint, occupancy, load, HVAC, lighting, area, volume, comfort status, and peak-risk status.`
- Animation:
  - Selected zone glows green.
  - Inspector slides in from right.

Step 7 - CCTV Occupancy Intelligence

- Target: `cctv-occupancy-preview`.
- PDF reference: pages 11-13.
- Copy:
  - `GreenFlow can use computer vision to estimate real-time occupancy from CCTV feeds, helping the control system understand how the building is actually being used.`
- Animation:
  - Draw bounding boxes over the CCTV preview.
  - Add a small `occupancy confidence` chip.

Step 8 - Zone Table And Filtering

- Target: `zone-state-table`.
- PDF reference: pages 14-16.
- Copy:
  - `The zone table turns the 3D context into an operational list. Operators can sort and filter zones by occupancy, temperature, load, comfort, and peak risk.`
- Animation:
  - Highlight `Load` column, then `Peak` column.
  - Apply a temporary filter: `peak risk = high`.

Step 9 - Weather And External Context

- Target: `weather-context-panel`.
- PDF reference: page 17.
- Copy:
  - `External weather affects cooling demand, comfort risk, and peak load. GreenFlow keeps weather context close to the building view so operators understand why demand changes.`
- Animation:
  - Map/weather panel expands.
  - Weather chips fade in: `Outdoor temperature`, `Humidity`, `Forecast`, `Heat stress`.

### Chapter 2 - Understand: Electrical Graph

PDF pages: 18-26.

Step 10 - Electrical Distribution Twin

- Route: Electrical Graph.
- Target: `electrical-kpis`.
- PDF reference: page 18.
- Copy:
  - `The Electrical Distribution Twin summarizes energy, cost, peak demand, emissions intensity, load risk, system mix, and top consuming zones.`
- Animation:
  - KPI cards count up quickly from zero to their current values.

Step 11 - Network Graph Overview

- Target: `electrical-graph-canvas`.
- PDF reference: pages 19-20.
- Before:
  - Set graph view to `overview`.
- Copy:
  - `The graph shows how power moves through transformers, distribution boards, panels, circuits, and connected loads.`
- Animation:
  - Edges draw from upstream to downstream.
  - Topology settles into 3D/2D layout.

Step 12 - Panel-Level Inspection

- Target: `electrical-node-inspector`.
- PDF reference: pages 21-22.
- Before:
  - Highlight a representative board or panel node, for example `RX101`.
  - Open right-side inspector.
- Copy:
  - `Selecting a panel reveals voltage, phase, demand, annual energy, upstream connection, peak information, and connected downstream loads.`
- Animation:
  - Node pulse.
  - Inspector metrics slide in.

Step 13 - Filters And Loadhead View

- Target: `electrical-filter-controls`.
- PDF reference: pages 23-24.
- Before:
  - Switch filter from `Overview` to `Panel`, then `Loadhead`.
- Copy:
  - `Filters let operators move between high-level topology and detailed loadhead analysis without losing the electrical context.`
- Animation:
  - Filter pills toggle.
  - Non-relevant nodes fade to 30 percent opacity.

Step 14 - Ask The Building Chatbot

- Target: `ai-chatbot-launcher`.
- PDF reference: pages 25-26.
- Before:
  - Open chatbot panel.
  - Pre-fill or show sample prompt: `What is the peak load today?`
- Copy:
  - `Operators can ask for building insight by text or voice. The chatbot should answer from the current digital twin, not from generic assumptions.`
- Animation:
  - Launcher bounces once.
  - Chat panel opens with a sample response.

### Chapter 3 - Optimize: Agents & Actions

PDF pages: 27-33.

Step 15 - Agent Workspace

- Route: Agents & Actions.
- Target: `agent-main-chat`.
- PDF reference: page 27.
- Copy:
  - `This tab is where GreenFlow explains what it sees, proposes actions, and reports the reasoning behind each decision.`
- Animation:
  - Highlight chat area and sessions list.

Step 16 - Run Optimization

- Target: `run-optimization-button`.
- PDF reference: page 28.
- Copy:
  - `Click Run Optimization to start a risk-controlled workflow. In tutorial mode, this is only a simulation preview and will not execute real controls.`
- Behavior:
  - Allow user to click `Run Optimization`, or auto-click in demo mode.
  - Use a mock/tutorial endpoint or local state.
- Animation:
  - Button turns into loading state.

Step 17 - Building Semantic Agent

- Target: `agent-execution-timeline`.
- PDF reference: page 29.
- Before:
  - Reveal timeline until `Building Semantic Agent`.
- Copy:
  - `The Building Semantic Agent reads the current timestep: zones, devices, abnormal findings, heatmaps, and semantic graph relationships.`
- Animation:
  - Timeline node changes from pending to success.
  - 3D preview appears inside the agent card.

Step 18 - Prediction Agent

- Target: `prediction-agent-block`.
- PDF reference: page 30.
- Before:
  - Reveal timeline until `Prediction Agent`.
- Copy:
  - `The Prediction Agent forecasts demand, peak-load zones, and comfort risk, so the system can act before problems become expensive.`
- Animation:
  - Bar chart grows.
  - Forecast line draws forward.

Step 19 - Control Agent

- Target: `control-agent-block`.
- PDF reference: page 31.
- Before:
  - Reveal timeline until `Control Agent`.
- Copy:
  - `The Control Agent compares the predictions and creates candidate control trajectories for the next 8 timesteps.`
- Animation:
  - Candidate action rows appear one by one.
  - Show labels like `lighting_reduction`, `peak_load_reduction`, `hvac_setback_light`.

Step 20 - Simulation And Policy Gate

- Target: `simulation-agent-block`.
- PDF reference: page 32.
- Before:
  - Reveal timeline until `Simulation Agent` and `Policy Engine`.
- Copy:
  - `GreenFlow does not directly apply actions. It simulates top-k plans, checks policy constraints, and only forwards approved candidates to the human approval queue.`
- Animation:
  - Top-k action cards move from agent timeline to queue.

Step 21 - Human Approval Queue

- Target: `action-queue`.
- PDF reference: page 33.
- Copy:
  - `Actions that affect real operation wait for human approval. Every recommendation includes estimated savings, peak reduction, comfort impact, risk notes, and an audit trail.`
- Animation:
  - Queue card highlights `Approve` and `Reject`.
  - Do not auto-approve in tutorial mode.

### Chapter 4 - Validate: Validation Experiment

PDF pages: 34-39.

Step 22 - Validation Experiment

- Route: Validation.
- Target: `validation-summary-cards`.
- PDF reference: page 34.
- Copy:
  - `The Validation tab compares baseline operation with GreenFlow optimization using recorded 2024 data. This is where impact is measured, not just claimed.`
- Animation:
  - With AI and Without AI bars animate.

Step 23 - Severe Climate Context

- Target: `validation-el-nino-toggle`.
- PDF reference: pages 34-36.
- Before:
  - Turn on `El Nino` overlay/toggle.
  - Scrub chart to early April.
- Copy:
  - `The El Nino period helps show how the system responds under heat stress, when cooling demand and peak pressure become more severe.`
- Animation:
  - Highlight the April region in the time-series chart.

Step 24 - Operational Impact Metrics

- Target: `validation-summary-cards`.
- PDF reference: pages 35-38.
- Copy:
  - `GreenFlow translates control performance into practical outcomes: less wasted energy, lower indirect emissions, reduced grid pressure, and longer asset lifetime.`
- Visual chips:
  - `Energy saved`
  - `CO2 avoided`
  - `Peak demand reduction`
  - `Comfort violation: 0 min`

Step 25 - Generate Monthly Report

- Target: `building-semantic-report-button`.
- PDF reference: page 39.
- Copy:
  - `Finally, operators can generate a monthly building performance report for internal review, paperwork, ESG reporting, or stakeholder communication.`
- Behavior:
  - Do not generate by default.
  - Show preview state only, or ask user to click intentionally.

Step 26 - Completion

- Target: centered modal.
- Copy:
  - `You have seen the GreenFlow loop: observe the building, understand the electrical twin, optimize through risk-controlled agents, and validate the impact.`
- Buttons:
  - `Finish`
  - `Replay`
  - `Explore dashboard`

## 9. Suggested Tutorial Copy For Demo Narration

Use this as voiceover or condensed panel copy:

```text
Before we make any decision, we need to know what is happening in the building.

The first tab gives an overview of performance across air quality, energy and load demand, thermal comfort, and equipment health. Each score runs from zero to one hundred, where a higher score means better operation.

Below that, the 3D digital twin lets users explore the building through architecture, electrical systems, HVAC, and zone layers. When a zone is selected, GreenFlow shows its technical state, including temperature, setpoint, occupancy, load, HVAC power, lighting demand, comfort status, and peak risk.

GreenFlow can also estimate real-time occupancy from CCTV using deep-learning computer vision, and it keeps external weather context visible because weather affects demand, comfort, and control decisions.

The second tab is the Electrical Distribution Twin. It shows how power is distributed across the building, which panels are overloaded, what equipment they connect to, and where potential faults may occur. Users can also ask the AI chatbot questions by text or voice.

The third tab is where optimization happens. Unlike many AI systems that act directly on data, GreenFlow uses a risk-controlled workflow. The Building Semantic Agent reads the current building condition. The Prediction Agent forecasts energy demand, peak-load zones, and comfort risk. The Control Agent creates candidate control trajectories for the next 8 timesteps.

GreenFlow does not execute actions immediately. The simulation engine tests the top-k plans, the policy engine checks risk constraints, and selected actions go into a human approval queue. Every decision is simulated, validated, and recorded before execution.

The Validation tab evaluates impact using recorded 2024 data, including the period when El Nino heat stress became significant. The charts compare baseline operation with GreenFlow optimization and show reductions in wasted energy, emissions, grid pressure, and asset stress.

Finally, users can generate a monthly building performance report for documentation and stakeholder review.
```

## 10. Visual Design Requirements

Style:

- Professional, clean, technical, green energy theme.
- Use GreenFlow green as the primary accent.
- Avoid cartoonish tutorial bubbles.
- Avoid thick dashed green boxes in the final product. The PDF uses dashed outlines as annotations; the product should use polished spotlight rings and soft glow.

Panel design:

- Background: white or very light green-tinted surface.
- Border: `1px solid rgba(10, 125, 95, 0.16)`.
- Shadow: soft, not dramatic.
- Radius: 8 px.
- Typography: match existing app font.
- Copy should be short. Do not place long paragraphs inside tooltips.

Highlight design:

- Active target gets:
  - 2 px green outline or glow.
  - Optional pulse for interactive elements.
  - No layout shift.
- Non-active UI dimmed, but still recognizable.

Chapter colors:

- Observe: Green
- Understand: Teal
- Optimize: Blue-green
- Validate: Emerald/gold accent for El Nino

## 11. Interaction Rules

Default mode:

- User advances manually with `Next`.
- The app auto-prepares each screen before showing the step.

Demo/autoplay mode:

- Add optional `Auto-play demo` toggle.
- Each step can auto-advance after 5-9 seconds.
- User can pause anytime.

Interactivity:

- Most steps should block background interaction except:
  - Click zone step
  - Run optimization step
  - Chatbot step
  - Report generation step
- For allowed interactions, only the target element should be clickable.

Exit behavior:

- `Esc` exits or opens an exit confirmation, depending on progress.
- `Skip` closes tutorial and marks it skipped, not completed.
- `Finish` marks completed.

## 12. Safety Requirements

Tutorial mode must not:

- Execute real control actions.
- Approve queued actions.
- Mutate live building state.
- Send real commands to BMS/BAS systems.
- Create permanent reports unless the user explicitly confirms.

Implementation guard:

- Add `tutorialMode: true` to orchestration context.
- API calls from tutorial mode should use mock/demo endpoints or a dry-run flag.
- Disable `Approve` buttons or convert them into preview-only actions during tutorial playback.

Recommended API convention:

```ts
{
  tutorialMode: true,
  dryRun: true,
  source: "greenflow_tutorial"
}
```

## 13. Accessibility Requirements

Follow modal/dialog accessibility expectations:

- Overlay/panel uses `role="dialog"` and `aria-modal="true"` when it blocks the app.
- The panel has `aria-labelledby` and `aria-describedby`.
- Focus moves into the tutorial panel on open.
- Focus is trapped inside the panel unless a step explicitly allows target interaction.
- `Tab` and `Shift+Tab` loop correctly.
- `Escape` exits or asks for confirmation.
- Focus returns to `Tutorial Mode` button after exit.
- Buttons have accessible labels.
- Announce step changes with an `aria-live="polite"` region.
- Respect `prefers-reduced-motion`.
- Maintain contrast ratio for overlay text and buttons.

## 14. Responsive Behavior

Desktop:

- Use side popovers anchored to highlighted targets.
- Keep 3D viewer visible when explaining layers and zones.

Tablet:

- Prefer bottom sheet panel.
- Spotlight active target above the bottom sheet.

Mobile:

- Tutorial should still work, but it can use condensed steps.
- Use full-screen sheet with screenshot-like target highlight if the actual dashboard is too dense.
- Do not rely on hover.

Fallback:

- If a target is offscreen, scroll it into view with `block: "center"`.
- If a target is not mounted after timeout, show a centered explanatory card and continue.

## 15. Analytics

Track:

- `tutorial_started`
- `tutorial_step_viewed`
- `tutorial_step_completed`
- `tutorial_skipped`
- `tutorial_completed`
- `tutorial_exited`
- `tutorial_error_target_missing`
- `tutorial_replayed`

Payload:

```ts
{
  tutorialVersion: "2026-07-greenflow-v1",
  stepId: "dashboard-health-index",
  chapter: "observe",
  route: "/dashboard",
  elapsedMs: 12345,
  mode: "manual" | "autoplay",
  userRole: "operator" | "demo" | "admin" | "unknown"
}
```

Success metrics:

- Completion rate.
- Drop-off by step.
- Replay rate.
- Time to first meaningful action after tutorial.
- Whether users later run validation/report/chatbot workflows.

## 16. Suggested File Structure

Adjust to the actual repo structure, but aim for this shape:

```text
src/
  features/
    tutorial/
      TutorialProvider.tsx
      TutorialOverlay.tsx
      TutorialPanel.tsx
      TutorialSpotlight.tsx
      tutorialSteps.ts
      tutorialActions.ts
      tutorialStorage.ts
      tutorialAnalytics.ts
      types.ts
      styles.css
```

If the app uses Next.js App Router:

```text
app/
  components/
    tutorial/
```

If the app already has a shared UI system:

```text
components/
  guided-tour/
```

## 17. Minimal Component Responsibilities

`TutorialProvider`

- Holds current state and step index.
- Handles start, next, back, skip, complete.
- Executes `before` and `after` actions.
- Waits for route and target readiness.

`TutorialOverlay`

- Renders dim overlay.
- Computes spotlight position from target rect.
- Handles window resize and scroll updates.

`TutorialPanel`

- Renders title, copy, progress, controls.
- Handles keyboard navigation.
- Supports centered and anchored placement.

`tutorialActions`

- Bridges tutorial steps to app behavior:
  - Switch tabs.
  - Toggle 3D layers.
  - Select zone.
  - Control camera.
  - Open chatbot.
  - Run optimization preview.
  - Reveal agent timeline.
  - Change validation metric.

`tutorialSteps`

- Stores the storyboard as data.
- Does not contain React component logic.

## 18. Example Step Data

```ts
export const tutorialSteps: TutorialStep[] = [
  {
    id: "dashboard-health-index",
    chapter: "observe",
    route: "/dashboard",
    target: "[data-tour-id='dashboard-health-index']",
    title: "Start with building health",
    body: "GreenFlow summarizes air quality, energy/load demand, thermal comfort, and equipment health so operators know where to focus first.",
    placement: "bottom",
    before: [
      { type: "switchTab", tab: "dashboard" }
    ]
  },
  {
    id: "dashboard-3d-layers",
    chapter: "observe",
    route: "/dashboard",
    target: "[data-tour-id='digital-twin-layers']",
    title: "Explore the building by layer",
    body: "Turn architecture, electrical, HVAC, and zone layers on or off to inspect the model from different operational angles.",
    placement: "right",
    before: [
      { type: "setCameraPreset", preset: "building-overview" },
      { type: "setLayer", layer: "Electrical", enabled: true },
      { type: "setLayer", layer: "HVAC", enabled: true }
    ]
  },
  {
    id: "agents-run-optimization",
    chapter: "optimize",
    route: "/agents",
    target: "[data-tour-id='run-optimization-button']",
    title: "Run a safe optimization preview",
    body: "Tutorial mode starts a dry-run workflow so users can see the agents reason without executing real controls.",
    placement: "left",
    allowInteraction: true,
    before: [
      { type: "switchTab", tab: "agents" }
    ],
    after: [
      { type: "startOptimizationPreview" }
    ]
  }
];
```

## 19. Implementation Checklist

Phase 1 - Foundation:

- Add `Tutorial Mode` button.
- Add `TutorialProvider`.
- Add overlay, panel, spotlight, progress controls.
- Add local storage persistence.
- Add Escape, skip, finish behavior.

Phase 2 - Selector preparation:

- Add `data-tour-id` attributes across all four tabs.
- Verify all targets exist on desktop.
- Add fallback behavior for missing targets.

Phase 3 - Screen orchestration:

- Implement route/tab switching.
- Implement 3D layer toggles and camera presets.
- Implement zone select demo action.
- Implement electrical graph node highlight.
- Implement chatbot open action.
- Implement dry-run optimization preview.
- Implement validation metric switching and chart scrub.

Phase 4 - Polish:

- Add motion transitions.
- Add progress rail.
- Add chapter labels.
- Add reduced-motion support.
- Add responsive bottom sheet behavior.

Phase 5 - Safety and testing:

- Ensure tutorial never calls real execution APIs.
- Test skip/exit from every tab.
- Test browser refresh during tutorial.
- Test missing selector fallback.
- Test keyboard-only flow.
- Test mobile and desktop.

## 20. Acceptance Criteria

Functional:

- User can start tutorial from a visible `Tutorial Mode` button.
- Tutorial moves through all four tabs in the correct order.
- Tutorial highlights the correct UI elements from the PDF flow.
- User can go back, next, skip, replay, and finish.
- Completion state persists.
- Tutorial can be replayed after completion.

UX:

- The experience feels like a guided GreenFlow demo, not a static slideshow.
- Each step has short, meaningful copy.
- 3D camera/layer changes make the product feel alive.
- Electrical graph and agent timeline have clear motion cues.
- Validation charts clearly show baseline vs optimized impact.

Safety:

- No real action is approved or executed.
- Run Optimization in tutorial mode is dry-run only.
- Report generation is preview-only unless user explicitly confirms.

Accessibility:

- Keyboard navigation works.
- Focus is managed correctly.
- Reduced-motion users are respected.
- Screen readers receive step changes.

Performance:

- Tutorial overlay should not cause visible layout shift.
- Spotlight updates should be throttled or use `requestAnimationFrame`.
- 3D viewer should not reload heavy assets between tutorial steps if already mounted.

## 21. Notes For Claude Code

Start by locating the existing tab routing and component structure. Then:

1. Find the existing top header and add the `Tutorial Mode` entry.
2. Find each tab component and add stable `data-tour-id` attributes.
3. Implement tutorial state and overlay as isolated components.
4. Wire tutorial actions into existing state handlers instead of duplicating business logic.
5. For any real execution endpoint, add a tutorial dry-run path.
6. Keep the first implementation desktop-first, then add responsive bottom-sheet fallback.

The PDF annotations are directionally correct, but the final UI should be more polished than the dashed green boxes shown there. Treat the PDF as storyboard and content reference, not final visual styling.
