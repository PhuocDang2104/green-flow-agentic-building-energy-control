export const BUILDING_ID = "b0000000-0000-0000-0000-000000000001";
export const BUILDING_KEY = "greenflow_archetype";
export const MANIFEST_URL = `/assets/buildings/${BUILDING_KEY}/viewer-manifest.json`;

// Keys match the manifest layer names emitted by build_3d_assets_ifc.py
export const LAYER_LABELS: Record<string, string> = {
  architecture: "Architecture",
  arch_shell: "Architecture",
  spaces: "Spaces / Zones",
  thermal_zones: "Spaces / Zones",
  fenestration: "Windows",
  structural: "Structural",
  hvac: "HVAC",
  electrical: "Electrical",
};

// Every layer now has real IFC-derived geometry — no placeholders.
export const PLANNED_LAYERS: string[] = [];

// Swatch colours (match the discipline themes in bim/ifc_geometry.py).
export const LAYER_COLORS: Record<string, string> = {
  architecture: "#DCDFE3",
  spaces: "#0F766E",
  fenestration: "#7AB5DB",
  structural: "#9EA3AB",
  hvac: "#338CC7",
  electrical: "#EBA833",
};

export const METRICS = [
  { id: "none", label: "Default" },
  { id: "energy", label: "Energy" },
  { id: "comfort", label: "Comfort" },
  { id: "faults", label: "Faults" },
] as const;

export type MetricId = (typeof METRICS)[number]["id"];

export const ROOM_TYPE_LABELS: Record<string, string> = {
  open_office: "Open office",
  office: "Office",
  meeting_room: "Meeting room",
  amenity: "Amenity",
  hallway: "Circulation",
};

const LEGACY_PROMPT_TRANSLATIONS: Record<string, string> = {
  "Tòa nhà tiêu thụ bao nhiêu điện hôm nay?": "How much energy has the building used today?",
  "Zone nào tiêu thụ điện nhiều nhất tuần này?": "Which zone used the most energy this week?",
  "Có cảnh báo nào đang mở không?": "Are there any open alerts?",
  "Liệt kê các zone trong tòa nhà": "List all zones in the building",
};

export function displayPromptInEnglish(text: string): string {
  return LEGACY_PROMPT_TRANSLATIONS[text] ?? text;
}

export const SUGGESTED_PROMPTS = Object.values(LEGACY_PROMPT_TRANSLATIONS);
