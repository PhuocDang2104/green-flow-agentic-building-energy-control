"use client";

import { create } from "zustand";
import type { CameraPreset, ElectricalColorMode } from "./types";

export type TutorialStatus = "idle" | "running" | "completed" | "exited";

interface TutorialState {
  status: TutorialStatus;
  stepIndex: number;

  // ---- command bridge: component-local UI subscribes to these ----
  cameraPreset: CameraPreset;        // GreenFlowViewer (dashboard 3D)
  validationMetric: string | null;   // CampaignWhatIf metric select
  elNinoOverride: boolean | null;    // CampaignWhatIf El-Niño checkbox
  agentPreview: boolean;             // agent-actions scripted timeline
  // electrical twin (tab 2) showcase
  elecColorMode: ElectricalColorMode | null;
  elecFocusBoard: "top" | "clear" | null;
  elecLinks: boolean | null;
  elecShowcase: boolean;             // gentle auto-rotate while demoing

  start: () => void;
  complete: () => void;
  exit: () => void;
  setStepIndex: (i: number) => void;

  setCameraPreset: (p: CameraPreset) => void;
  setValidationMetric: (m: string | null) => void;
  setElNinoOverride: (v: boolean | null) => void;
  setAgentPreview: (v: boolean) => void;
  setElecColorMode: (m: ElectricalColorMode | null) => void;
  setElecFocusBoard: (v: "top" | "clear" | null) => void;
  setElecLinks: (v: boolean | null) => void;
  setElecShowcase: (v: boolean) => void;
}

// clearing every command bridge (used on start/exit/complete so a stale
// preview/camera/metric never leaks outside a tour).
const CLEARED = {
  cameraPreset: null as CameraPreset,
  validationMetric: null as string | null,
  elNinoOverride: null as boolean | null,
  agentPreview: false,
  elecColorMode: null as ElectricalColorMode | null,
  elecFocusBoard: null as "top" | "clear" | null,
  elecLinks: null as boolean | null,
  elecShowcase: false,
};

export const useTutorialStore = create<TutorialState>((set) => ({
  status: "idle",
  stepIndex: 0,
  ...CLEARED,

  start: () => set({ status: "running", stepIndex: 0, ...CLEARED }),
  complete: () => set({ status: "completed", ...CLEARED }),
  exit: () => set({ status: "exited", ...CLEARED }),
  setStepIndex: (i) => set({ stepIndex: i }),

  setCameraPreset: (cameraPreset) => set({ cameraPreset }),
  setValidationMetric: (validationMetric) => set({ validationMetric }),
  setElNinoOverride: (elNinoOverride) => set({ elNinoOverride }),
  setAgentPreview: (agentPreview) => set({ agentPreview }),
  setElecColorMode: (elecColorMode) => set({ elecColorMode }),
  setElecFocusBoard: (elecFocusBoard) => set({ elecFocusBoard }),
  setElecLinks: (elecLinks) => set({ elecLinks }),
  setElecShowcase: (elecShowcase) => set({ elecShowcase }),
}));

/** Convenience for non-React callers (e.g. layout guards). */
export const isTutorialActive = () => useTutorialStore.getState().status === "running";
