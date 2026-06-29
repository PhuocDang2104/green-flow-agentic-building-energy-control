"use client";

import { create } from "zustand";
import type { ViewerUpdate, WeatherState, ZoneState } from "@/lib/types";
import type { MetricId } from "@/lib/constants";

interface AppState {
  buildingId: string;
  replayTimestamp: string | null;
  wsConnected: boolean;
  streaming: boolean;
  zoneStates: Record<string, ZoneState>;
  weatherState: WeatherState | null;
  buildingLive: { total_power_kw?: number; occupancy?: number };

  selectedEntityKey: string | null;
  activeMetric: MetricId;
  layers: Record<string, boolean>;
  // per-layer technical heatmaps (Technical Systems group), independent of the
  // Spatial/Zone mode bar (activeMetric)
  techHeatmap: { electrical: boolean; hvac: boolean };
  viewerUpdates: ViewerUpdate[];
  chatbotOpen: boolean;
  activeAgentRunId: string | null;

  setReplay: (ts: string, zones: Record<string, ZoneState>,
              building: { total_power_kw?: number; occupancy?: number },
              weather?: WeatherState) => void;
  setWeatherState: (weather: WeatherState) => void;
  setWsConnected: (v: boolean) => void;
  setStreaming: (v: boolean) => void;
  selectEntity: (key: string | null) => void;
  setMetric: (m: MetricId) => void;
  setLayer: (layer: string, visible: boolean) => void;
  setLayers: (layers: Record<string, boolean>) => void;
  setTechHeatmap: (layer: "electrical" | "hvac", on: boolean) => void;
  setViewerUpdates: (u: ViewerUpdate[]) => void;
  setChatbotOpen: (v: boolean) => void;
  setActiveAgentRunId: (id: string | null) => void;
  setZoneStates: (z: Record<string, ZoneState>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  buildingId: "b0000000-0000-0000-0000-000000000001",
  replayTimestamp: null,
  wsConnected: false,
  streaming: false,
  zoneStates: {},
  weatherState: null,
  buildingLive: {},

  selectedEntityKey: null,
  activeMetric: "none",
  layers: { architecture: false, spaces: false, fenestration: false,
            structural: true, hvac: false, electrical: false },
  techHeatmap: { electrical: false, hvac: false },
  viewerUpdates: [],
  chatbotOpen: false,
  activeAgentRunId: null,

  setReplay: (ts, zones, building, weather) =>
    set({ replayTimestamp: ts, zoneStates: zones, buildingLive: building,
          ...(weather ? { weatherState: weather } : {}) }),
  setWeatherState: (weatherState) => set({ weatherState }),
  setWsConnected: (v) => set({ wsConnected: v }),
  setStreaming: (v) => set({ streaming: v }),
  selectEntity: (key) => set({ selectedEntityKey: key }),
  setMetric: (m) => set({ activeMetric: m }),
  setLayer: (layer, visible) =>
    set((s) => ({ layers: { ...s.layers, [layer]: visible } })),
  setLayers: (layers) => set({ layers }),
  setTechHeatmap: (layer, on) =>
    set((s) => ({ techHeatmap: { ...s.techHeatmap, [layer]: on } })),
  setViewerUpdates: (u) => set({ viewerUpdates: u }),
  setChatbotOpen: (v) => set({ chatbotOpen: v }),
  setActiveAgentRunId: (id) => set({ activeAgentRunId: id }),
  setZoneStates: (z) => set({ zoneStates: z }),
}));
