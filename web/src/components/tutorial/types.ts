// Tutorial Mode — shared types. The storyboard (tutorialSteps.ts) is pure data
// of this shape; tutorialActions.ts interprets each TutorialAction.

export type TutorialChapter = "observe" | "understand" | "optimize" | "validate";

export type TutorialRoute =
  | "/dashboard"
  | "/electrical"
  | "/agent-actions"
  | "/simulation-baseline";

export type TutorialPlacement = "top" | "right" | "bottom" | "left" | "center";

export type CameraPreset = "building-overview" | "zone-focus" | null;

export type ZoneMetric = "none" | "energy" | "comfort" | "occupancy" | "faults";
export type ValidationMetric = "energy" | "power" | "temperature" | "setpoint" | "loading";

/**
 * A tutorial step's side-effect. Most reuse the existing appStore handlers;
 * a few drive component-local state via the tutorialStore command bridge
 * (camera, validation metric/El-Niño, scripted agent preview).
 */
export type TutorialAction =
  | { type: "switchTab"; route: TutorialRoute }
  | { type: "setLayer"; layer: string; enabled: boolean }
  | { type: "setLayers"; layers: Record<string, boolean> }
  | { type: "setHeatmap"; heatmap: "electrical" | "hvac"; enabled: boolean }
  | { type: "setMetric"; metric: ZoneMetric }
  | { type: "selectZone"; zoneId?: string }
  | { type: "clearZone" }
  | { type: "setCamera"; preset: CameraPreset }
  | { type: "openChatbot"; open: boolean }
  | { type: "startAgentPreview" }
  | { type: "stopAgentPreview" }
  | { type: "setValidationMetric"; metric: ValidationMetric }
  | { type: "toggleElNino"; on: boolean };

export interface TutorialStep {
  id: string;
  chapter: TutorialChapter;
  route: TutorialRoute;
  /** data-tour-id value of the element to spotlight; omit for a centered card. */
  target?: string;
  title: string;
  body: string;
  placement?: TutorialPlacement;
  /** small labelled chips under the body (e.g. "Air Quality", "Energy"). */
  chips?: string[];
  /** run before the step is shown (navigation, layer toggles, etc.). */
  before?: TutorialAction[];
  /** run when leaving the step forward. */
  after?: TutorialAction[];
  /** allow the spotlighted target to stay clickable (e.g. Run Optimization). */
  allowInteraction?: boolean;
}

export const CHAPTERS: { id: TutorialChapter; label: string; accent: string }[] = [
  { id: "observe", label: "Observe", accent: "#0F766E" },     // teal / green
  { id: "understand", label: "Understand", accent: "#0E9488" }, // teal
  { id: "optimize", label: "Optimize", accent: "#2563EB" },    // blue-green
  { id: "validate", label: "Validate", accent: "#D97706" },    // emerald/gold (El Niño)
];
