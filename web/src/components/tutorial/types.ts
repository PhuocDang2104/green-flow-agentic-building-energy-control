// Tutorial Mode — shared types. The storyboard (tutorialSteps.ts) is pure data
// of this shape; tutorialActions.ts interprets each TutorialAction.

export type TutorialChapter = "observe" | "understand" | "optimize" | "validate";

export type TutorialRoute =
  | "/dashboard"
  | "/electrical"
  | "/agent-actions"
  | "/simulation-baseline";

export type TutorialPlacement = "top" | "right" | "bottom" | "left" | "center";

export type CameraPreset =
  | "building-overview"
  | "zone-focus"
  | "layer-architecture"
  | "layer-electrical"
  | "layer-hvac"
  | "layer-spaces"
  | "technical-stack"
  | null;

export type ZoneMetric = "none" | "energy" | "comfort" | "faults";
export type ValidationMetric = "energy" | "power" | "temperature" | "setpoint" | "loading";

/**
 * A tutorial step's side-effect. Most reuse the existing appStore handlers;
 * a few drive component-local state via the tutorialStore command bridge
 * (camera, validation metric/El-Niño, scripted agent preview).
 */
export type ElectricalColorMode = "status" | "feeder" | "load";

export type TutorialAction =
  | { type: "switchTab"; route: TutorialRoute }
  | { type: "setLayer"; layer: string; enabled: boolean }
  | { type: "setLayers"; layers: Record<string, boolean> }
  | { type: "setHeatmap"; heatmap: "electrical" | "hvac"; enabled: boolean }
  | { type: "setMetric"; metric: ZoneMetric }
  | { type: "selectZone"; zoneId?: string }
  | { type: "clearZone" }
  | { type: "setCamera"; preset: CameraPreset }
  | { type: "showcaseLayers" }
  | { type: "openChatbot"; open: boolean }
  | { type: "startAgentPreview" }
  | { type: "stopAgentPreview" }
  | { type: "setValidationMetric"; metric: ValidationMetric }
  | { type: "toggleElNino"; on: boolean }
  | { type: "setViewerSpin"; on: boolean }   // continuous dashboard 3D orbit
  | { type: "cycleZones" }                    // auto-select a different zone on a loop
  // ---- electrical (tab 2) showcase bridge ----
  | { type: "setElectricalColorMode"; mode: ElectricalColorMode }
  | { type: "focusElectricalBoard"; which: "top" | "clear" }
  | { type: "setElectricalLinks"; on: boolean }
  | { type: "setElectricalShowcase"; on: boolean };

/** A floating illustrative card/image shown at a screen corner during a step. */
export type TutorialMediaAnchor =
  | "top-right" | "bottom-right" | "top-left" | "bottom-left" | "top-center";

export interface TutorialMedia {
  src?: string;        // image src (card/float); omit for a bubble
  alt?: string;
  title?: string;      // bold heading (card / bubble)
  caption?: string;    // paragraph under a card image
  bullets?: string[];  // speech-bubble list
  anchor: TutorialMediaAnchor;
  width?: number;      // px (default 340)
  variant?: "card" | "float" | "bubble"; // framed image+caption / bare PNG / speech bubble
}

export interface TutorialStep {
  id: string;
  chapter: TutorialChapter;
  route: TutorialRoute;
  /** data-tour-id value of the element to spotlight; omit for a centered card. */
  target?: string;
  /** how the primary target is scrolled into view (default "center"). */
  scrollBlock?: ScrollLogicalPosition;
  /** extra targets to also cut a bright box around (e.g. 3D viewer + table). */
  spotlights?: string[];
  /** floating illustrative image/caption cards for this step. */
  media?: TutorialMedia[];
  title: string;
  body: string;
  placement?: TutorialPlacement;
  /** small labelled chips under the body (e.g. "Air Quality", "Energy"). */
  chips?: string[];
  /** a "try it" call-to-action shown in the panel for hands-on steps. */
  hint?: string;
  /** run before the step is shown (navigation, layer toggles, etc.). */
  before?: TutorialAction[];
  /** run when leaving the step forward. */
  after?: TutorialAction[];
  /**
   * By default every anchored step is interactive: the spotlighted region stays
   * fully usable. Set this to make a step read-only (block clicks on the target).
   */
  blockInteraction?: boolean;
}

export const CHAPTERS: { id: TutorialChapter; label: string; accent: string }[] = [
  { id: "observe", label: "Observe", accent: "#0F766E" },     // teal / green
  { id: "understand", label: "Understand", accent: "#0E9488" }, // teal
  { id: "optimize", label: "Optimize", accent: "#2563EB" },    // blue-green
  { id: "validate", label: "Validate", accent: "#D97706" },    // emerald/gold (El Niño)
];
