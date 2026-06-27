export type StatusTone = "success" | "warning" | "danger" | "info" | "normal";

export interface StatusBand {
  label: "Good" | "Average" | "Warning" | "No data";
  tone: StatusTone;
  color: string;
  softColor: string;
}

const GOOD: StatusBand = {
  label: "Good", tone: "success", color: "#16A34A", softColor: "#DCFCE7",
};
const AVERAGE: StatusBand = {
  label: "Average", tone: "warning", color: "#D97706", softColor: "#FEF3C7",
};
const WARNING: StatusBand = {
  label: "Warning", tone: "danger", color: "#DC2626", softColor: "#FEE2E2",
};
const NO_DATA: StatusBand = {
  label: "No data", tone: "normal", color: "#64748B", softColor: "#F1F5F9",
};

/** Shared health-score bands used by the breakdown and its matching KPI cards. */
export function healthBand(score?: number | null): StatusBand {
  if (score == null) return NO_DATA;
  if (score >= 70) return GOOD;
  if (score >= 50) return AVERAGE;
  return WARNING;
}

/** Occupancy count has no intrinsic good/bad value, so its state uses confidence. */
export function occupancyConfidenceBand(confidence?: number | null): StatusBand {
  if (confidence == null) return NO_DATA;
  if (confidence >= 0.85) return GOOD;
  if (confidence >= 0.70) return AVERAGE;
  return WARNING;
}
