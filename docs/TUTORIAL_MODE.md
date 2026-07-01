# GreenFlow Tutorial Mode — Engineering Reference

> **TL;DR (VI):** Tutorial Mode là tour hướng dẫn 29 bước, tự lái web qua 4 tab
> (Observe → Understand → Optimize → Validate). Nút bấm nằm bên trái top header. Mọi bước
> **tương tác thật** (soft-spotlight, không khoá web), có "preparing…" chờ web
> chạy xong mới khoanh vùng, thanh tiến độ **dọc góc dưới-trái**. Toàn bộ code
> nằm trong `web/src/components/tutorial/`. Không gọi API thật (chương Agents là
> timeline mô phỏng). Muốn sửa nội dung: **chỉ sửa `tutorialSteps.ts`**.

A custom, dependency-light guided product walkthrough. No tour library — built on
`motion` v12 + `zustand` + `createPortal` + Tailwind tokens.

Spec/source: `docs/tutorial-source/greenflow_tutorial_mode_spec.md`.

---

## 1. Entry & file map

All code lives in **`web/src/components/tutorial/`**:

| File | Responsibility |
|---|---|
| `types.ts` | `TutorialStep`, `TutorialAction`, `CHAPTERS`, enums |
| `tutorialSteps.ts` | **The storyboard as data (29 steps).** Edit content here. |
| `tutorialStore.ts` | Zustand store: run status, step index, **command-bridge** fields |
| `tutorialActions.ts` | Interprets each step's `before`/`after` actions; `showcaseLayers` |
| `tutorialStorage.ts` | localStorage completion + version gate |
| `useTutorialTarget.ts` | Resolves `[data-tour-id]` → rect (poll, scroll, track) |
| `TutorialProvider.tsx` | Orchestrator: route enforce, run actions, keys, render |
| `TutorialOverlay.tsx` | Soft spotlight (dim + pulsing ring), portal to `body` |
| `TutorialPanel.tsx` | Floating step card (title/body/hint/chips/controls) |
| `TutorialProgressRail.tsx` | **Vertical** 4-chapter rail, bottom-left |
| `TutorialEntryButton.tsx` | Header button ("Tutorial") |
| `TutorialAgentTimeline.tsx` | Scripted, safe agent run for the Optimize chapter |

**Mount points (outside the module):**
- `web/src/components/shell/AppShell.tsx` — wraps children in `<TutorialProvider>`.
- `web/src/components/shell/TopBar.tsx` — renders `<TutorialEntryButton>` at the left of the top header.

**Routes** (spec name → real route): dashboard → `/dashboard`, electrical →
`/electrical`, agents → `/agent-actions`, validation → `/simulation-baseline`.

---

## 2. How it works (lifecycle)

```
Header button → tutorialStore.start()  (status="running", stepIndex=0)
   │
   ▼  TutorialProvider effect on [running, stepIndex]:
   1. if current route ≠ step.route → router.push(step.route)
   2. runTutorialActions(step.before)          // navigate / toggle layers / camera / …
   │
   ▼  useTutorialTarget(step.target):
   • poll for [data-tour-id="…"] up to ~5s
   • scrollIntoView({block:"center"}), track rect on scroll/resize
   • status: "pending" → "found" | "missing" (missing ⇒ centered fallback)
   │
   ▼  Render (only while running):
   • TutorialOverlay  (dim + ring around rect; page stays clickable)
   • TutorialPanel    (anchored beside rect, or centered; "Preparing…" while pending)
   • TutorialProgressRail (vertical, bottom-left)

Next → runTutorialActions(step.after) → stepIndex++      (last ⇒ finish())
Back → stepIndex--                                        (re-runs that step's before)
Skip/Esc → exit()   Finish → markTutorialCompleted()+complete()   Replay → start()
```

- **Route is enforced every step** by the Provider, so Back across a tab boundary
  still lands on the right page (don't rely on `switchTab` alone).
- Before each chapter tab change there is a sidebar-nav spotlight step
  (`go-to-electrical-tab`, `go-to-agents-tab`, `go-to-validation-tab`) so the
  user can click the next tab and understand the route transition before
  continuing.
- On start/exit/complete the store **clears all command-bridge fields** so no
  camera/preview/metric leaks outside a tour.

---

## 3. Store & command bridges (`tutorialStore.ts`)

`status: "idle"|"running"|"completed"|"exited"`, `stepIndex: number`.

Component-local UI can't be driven by props from the tour, so the store exposes
**command fields** that those components subscribe to via `useEffect`:

| Field | Consumed by | Effect |
|---|---|---|
| `cameraPreset` | `viewer/GreenFlowViewer.tsx` | fly to `building-overview`, `zone-focus`, or layer-showcase camera presets |
| `validationMetric`, `elNinoOverride` | `simulation/CampaignWhatIf.tsx` | sync metric select + El-Niño checkbox |
| `agentPreview` | `app/(app)/agent-actions/page.tsx` | render `TutorialAgentTimeline`; guards Run button |
| `elecColorMode`, `elecFocusBoard`("top"/"clear"), `elecLinks`, `elecShowcase` | `app/(app)/electrical/page.tsx` | color mode / isolate largest board / links / auto-rotate + Feeder/Load cycling |

Pattern in the consumer (idempotent, null = "not driven"):
```ts
const v = useTutorialStore((s) => s.cameraPreset);
useEffect(() => { if (v) flyTo(v); }, [v]);
```

---

## 4. Step schema & actions (`types.ts`)

```ts
type TutorialStep = {
  id: string;
  chapter: "observe"|"understand"|"optimize"|"validate";
  route: "/dashboard"|"/electrical"|"/agent-actions"|"/simulation-baseline";
  target?: string;         // data-tour-id value; omit → centered card
  title: string; body: string;
  placement?: "top"|"right"|"bottom"|"left"|"center";
  chips?: string[];        // small labelled chips
  hint?: string;           // "try it" cue (green callout)
  before?: TutorialAction[]; after?: TutorialAction[];
  blockInteraction?: boolean; // read-only step (blocks the target); default = interactive
};
```

`TutorialAction` (interpreted in `tutorialActions.ts`):
`switchTab · setLayer · setLayers · setHeatmap · setMetric · selectZone · clearZone
· setCamera · showcaseLayers · openChatbot · startAgentPreview · stopAgentPreview
· setValidationMetric · toggleElNino · setElectricalColorMode · focusElectricalBoard
· setElectricalLinks · setElectricalShowcase`.

Most reuse existing `appStore` handlers; camera/validation/agent/electrical go via
the store command bridge. `selectZone` with no id picks a live zone from
`appStore.zoneStates` at runtime.

---

## 5. Interaction model (the important design choice)

**Soft spotlight, hands-on.** `TutorialOverlay` is a `pointer-events-none` layer:
a box-shadow dim + a pulsing green ring around the target. The page underneath
**stays fully clickable** at every step — orbit the 3D, tick heatmaps, click
zones/charts/filters. This is intentional (the user wanted real interaction, not
view-only).

- **Interactive by default** for any step with a `target`.
- Dashboard 3D layer/heatmap steps target `digital-twin-viewer`, not the small
  floating controls, so the spotlight bounds the whole 3D frame.
- Electrical graph explanation/filter steps target `electrical-graph-canvas`, so
  the full 3D electrical frame stays boxed while controls animate inside it.
- `blockInteraction: true` → a transparent blocker covers **only the target**
  (rest of page still usable). Used for the report button (don't fire a real report).
- **Centered** steps (no `target`) → full dim + block, like a modal (welcome/finish).
- **Wait-for-ready:** while the target is still resolving (tab switch, run in
  progress), the panel shows a **"Preparing this view…"** card; the box only binds
  once the element mounts. Focus trap (`Tab`) applies to modal/read-only steps only.

Z-order: overlay `9998` · rail `9999` · panel `10000`.

---

## 6. Selector contract — `data-tour-id`

Steps target **stable `data-tour-id` attributes**, never class names/text. Add the
attribute to the outermost wrapper of a target; no logic change.

| data-tour-id | File |
|---|---|
| `tutorial-entry` | shell/TopBar.tsx (the button) |
| `nav-dashboard-3d` / `nav-electrical-graph` / `nav-agents-actions` / `nav-validation` | shell/SideBar.tsx |
| `dashboard-health-index` | dashboard/BuildingHealthCard.tsx (loaded + loading `<section>`) |
| `digital-twin-viewer` | viewer/GreenFlowViewer.tsx (root) |
| `digital-twin-layers` / `layer-technical-systems` / `layer-spatial-analytics` | viewer/LayerPanel.tsx |
| `system-heatmaps` | viewer/AnalysisBar.tsx |
| `zone-inspector` / `cctv-occupancy-preview` | dashboard/EntityInsightPanel.tsx |
| `zone-state-table` | dashboard/ZoneStateTable.tsx |
| `weather-context-panel` | dashboard/ClimateScenarioSection.tsx |
| `electrical-kpis` | dashboard/EnergyAnalyticsSection.tsx |
| `electrical-graph-canvas` / `electrical-filter-controls` / `electrical-node-inspector` | app/(app)/electrical/page.tsx |
| `ai-chatbot-launcher` / `ai-chatbot-panel` | chatbot/ChatbotPanel.tsx |
| `agent-session-list` / `agent-main-chat` / `run-optimization-button` | app/(app)/agent-actions/page.tsx |
| `agent-execution-timeline` / `simulation-agent-block` / `prediction-agent-block` / `control-agent-block` / `policy-engine-block` / `action-queue` / `approval-card` | tutorial/TutorialAgentTimeline.tsx |
| `validation-summary-cards` / `validation-timeseries-chart` / `validation-metric-selector` / `validation-el-nino-toggle` | simulation/CampaignWhatIf.tsx |
| `building-semantic-report-button` | app/(app)/simulation-baseline/page.tsx |

Current full-frame 3D steps intentionally target `digital-twin-viewer` /
`electrical-graph-canvas` even when the copy talks about layers, heatmaps, mode
buttons, or links. The smaller control IDs remain useful for future narrower
steps, but are not used for the main graph spotlights.

If a target never mounts (data-dependent, e.g. CCTV needs a camera-bearing zone),
the step degrades gracefully to a centered card.

---

## 7. Showcases & the safe Agents chapter

- **`showcaseLayers`** (dashboard, step "Explore by Layer"): first removes the
  structural shell, then auto-cycles full-frame layer/camera views every ~1.25s
  (architecture → electrical → HVAC → spaces → full technical stack). Cancellable
  via a token that `runTutorialActions` bumps on every step change, so timers
  never fight the next step.
- **Electrical showcase** (tab 2): `setElectricalShowcase(true)` → gentle
  `autoRotate` on `ElectricalTwin3D`; `focusElectricalBoard("top")` selects and
  zooms the camera into the highest-demand board; Feeder and Load-heat modes
  alternate every ~1.35s; the Links button pulses while supply lines blink on/off.
- **`TutorialAgentTimeline`** (tab 3): a **canned, deterministic** run rendered in
  the `agent-main-chat` column when `agentPreview` is on. Nodes reveal one-by-one
  ("running…" → complete) reusing the real `SemanticMiniViewer` (exported from
  `chatbot/InlineRunSteps.tsx`). The real **Run Optimization** button is guarded:
  in a tour it sets `agentPreview` instead of calling the live endpoint.

**Safety:** no step calls a real execution/approval/report endpoint. Approve/Reject
in the preview are disabled; the report button is `blockInteraction`.

---

## 8. How to change things

**Edit copy / reorder / add a step** → `tutorialSteps.ts` only. Progress counter
and rail update automatically from the array length + `chapter`.

**Spotlight a new element** →
1. add `data-tour-id="my-thing"` to its wrapper;
2. add a step with `target: "my-thing"` (+ `placement`, `hint`).

**Drive component-local state** (needs a bridge) →
1. add a field + setter to `tutorialStore.ts` (and clear it in `CLEARED`);
2. add a `TutorialAction` variant in `types.ts` + a case in `tutorialActions.ts`;
3. `useEffect`-subscribe in the target component (`if (v != null) apply(v)`).

**Persistence/versioning** → `tutorialStorage.ts`. Bump `TUTORIAL_VERSION` when the
content changes so returning users are re-offered the tour (button still reads
"Tutorial"; aria/title distinguish replay).

---

## 9. Accessibility, motion, verify

- `role="dialog"` + `aria-modal`, `aria-labelledby/─describedby`, focus restored to
  the entry button on exit, `useReducedMotion()` disables ring pulse / long morphs.
- Chapter accents (`types.ts` `CHAPTERS`): Observe/Understand green-teal, Optimize
  blue, Validate amber (El-Niño).
- **Verify:** `cd web && npx tsc --noEmit` (clean) · `npm run build` (11 pages) ·
  `npm run dev` → click **Tutorial**, walk all 29 steps; confirm interaction
  works inside each spotlight, "Preparing…" waits for the run, and **no real agent
  run / approval / report fires**.

_Related notes: `docs/tutorial-source/greenflow_tutorial_mode_spec.md` (original spec)._
