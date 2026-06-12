"use client";

import { create } from "zustand";
import type { ViewerUpdate, ZoneState } from "@/lib/types";
import type { MetricId } from "@/lib/constants";

interface AppState {
  buildingId: string;
  replayTimestamp: string | null;
  wsConnected: boolean;
  zoneStates: Record<string, ZoneState>;
  buildingLive: { total_power_kw?: number; occupancy?: number };

  selectedEntityKey: string | null;
  activeMetric: MetricId;
  layers: Record<string, boolean>;
  viewerUpdates: ViewerUpdate[];
  chatbotOpen: boolean;
  activeAgentRunId: string | null;

  setReplay: (ts: string, zones: Record<string, ZoneState>,
              building: { total_power_kw?: number; occupancy?: number }) => void;
  setWsConnected: (v: boolean) => void;
  selectEntity: (key: string | null) => void;
  setMetric: (m: MetricId) => void;
  setLayer: (layer: string, visible: boolean) => void;
  setLayers: (layers: Record<string, boolean>) => void;
  setViewerUpdates: (u: ViewerUpdate[]) => void;
  setChatbotOpen: (v: boolean) => void;
  setActiveAgentRunId: (id: string | null) => void;
  setZoneStates: (z: Record<string, ZoneState>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  buildingId: "b0000000-0000-0000-0000-000000000001",
  replayTimestamp: null,
  wsConnected: false,
  zoneStates: {},
  buildingLive: {},

  selectedEntityKey: null,
  activeMetric: "none",
  layers: { arch_shell: true, spaces: true, fenestration: true },
  viewerUpdates: [],
  chatbotOpen: false,
  activeAgentRunId: null,

  setReplay: (ts, zones, building) =>
    set({ replayTimestamp: ts, zoneStates: zones, buildingLive: building }),
  setWsConnected: (v) => set({ wsConnected: v }),
  selectEntity: (key) => set({ selectedEntityKey: key }),
  setMetric: (m) => set({ activeMetric: m }),
  setLayer: (layer, visible) =>
    set((s) => ({ layers: { ...s.layers, [layer]: visible } })),
  setLayers: (layers) => set({ layers }),
  setViewerUpdates: (u) => set({ viewerUpdates: u }),
  setChatbotOpen: (v) => set({ chatbotOpen: v }),
  setActiveAgentRunId: (id) => set({ activeAgentRunId: id }),
  setZoneStates: (z) => set({ zoneStates: z }),
}));
