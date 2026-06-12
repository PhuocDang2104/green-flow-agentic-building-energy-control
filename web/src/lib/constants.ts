export const BUILDING_ID = "b0000000-0000-0000-0000-000000000001";
export const BUILDING_KEY = "greenflow_archetype";
export const MANIFEST_URL = `/assets/buildings/${BUILDING_KEY}/viewer-manifest.json`;

// Keys match the manifest layer names emitted by scripts/build_3d_assets.py
export const LAYER_LABELS: Record<string, string> = {
  architecture: "Architecture",
  arch_shell: "Architecture",
  thermal_zones: "Spaces / Zones",
  spaces: "Spaces / Zones",
  fenestration: "Windows",
  hvac: "HVAC",
  electrical: "Electrical",
  structural: "Structural",
  terrain: "Terrain",
};

// Layers defined by the platform but without assets in the IDF demo building
export const PLANNED_LAYERS = ["hvac", "electrical", "structural", "terrain"];

export const METRICS = [
  { id: "none", label: "Default" },
  { id: "energy", label: "Energy" },
  { id: "comfort", label: "Comfort" },
  { id: "occupancy", label: "Occupancy" },
] as const;

export type MetricId = (typeof METRICS)[number]["id"];

export const ROOM_TYPE_LABELS: Record<string, string> = {
  open_office: "Open office",
  office: "Office",
  meeting_room: "Meeting room",
  amenity: "Amenity",
  hallway: "Circulation",
};

export const SUGGESTED_PROMPTS = [
  "Zone nào đang lãng phí điện?",
  "Nếu tăng setpoint 1°C ở open office thì sao?",
  "Tòa nhà có vấn đề gì không?",
  "Peak risk hôm nay thế nào?",
];
