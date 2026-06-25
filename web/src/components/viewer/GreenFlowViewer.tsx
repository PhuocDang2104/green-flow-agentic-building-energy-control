"use client";

/**
 * GreenFlow xeokit viewer.
 *
 * Static geometry (XKT per layer) + dynamic overlay (colorize/opacity from
 * zone state, agent viewer_updates, selection highlight) — the architecture
 * from "3D View & Mapping IFC for Digital Twin Building".
 *
 * Loads XKT via XKTLoaderPlugin when the manifest says geometry_format=xkt;
 * falls back to building a SceneModel from geometry.json otherwise.
 */

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { MANIFEST_URL } from "@/lib/constants";
import type { ObjectMapEntry, ViewerManifest } from "@/lib/types";
import { api } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";
import LayerPanel from "./LayerPanel";
import AnalysisBar from "./AnalysisBar";
import ViewModeToolbar from "./ViewModeToolbar";
import MetricLegend from "./MetricLegend";
import EntityTooltip from "./EntityTooltip";

type XeokitViewer = any;
type AlertSeverity = "critical" | "warning" | "info";

const ZONE_BASE_COLOR: [number, number, number] = [0.06, 0.46, 0.43];

// Fault overlay palette (matches FaultsPanel / MetricLegend severity colors).
const ALERT_COLOR: Record<AlertSeverity, [number, number, number]> = {
  critical: [0.86, 0.13, 0.13],
  warning: [0.96, 0.6, 0.04],
  info: [0.58, 0.64, 0.7],
};
const ALERT_RANK: Record<AlertSeverity, number> = { info: 0, warning: 1, critical: 2 };

const LAYER_RENDER_ORDER: Record<string, number> = {
  architecture: 0,
  structural: 8,
  fenestration: 12,
  spaces: 18,
  electrical: 90,
  hvac: 100,
};

export default function GreenFlowViewer({ heightClass = "h-[560px]" }: { heightClass?: string }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const viewerRef = useRef<XeokitViewer | null>(null);
  const modelsRef = useRef<Record<string, any>>({});
  const objectMapRef = useRef<Record<string, ObjectMapEntry>>({});
  const xeokitRef = useRef<{ SceneModel: any; buildSphereGeometry: any } | null>(null);
  const occupancyModelRef = useRef<any>(null);
  const alertModelRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  // zone_key -> highest open-alert severity, drives the "Faults" view overlay
  const [alertByZone, setAlertByZone] = useState<Record<string, AlertSeverity>>({});

  const layers = useAppStore((s) => s.layers);
  const techHeatmap = useAppStore((s) => s.techHeatmap);
  const activeMetric = useAppStore((s) => s.activeMetric);
  const zoneStates = useAppStore((s) => s.zoneStates);
  const selectedEntityKey = useAppStore((s) => s.selectedEntityKey);
  const viewerUpdates = useAppStore((s) => s.viewerUpdates);
  const selectEntity = useAppStore((s) => s.selectEntity);
  const setLayers = useAppStore((s) => s.setLayers);

  // --- init viewer once ---------------------------------------------------
  useEffect(() => {
    let disposed = false;
    const cleanups: Array<() => void> = [];

    (async () => {
      try {
        const [{ Viewer, XKTLoaderPlugin, SceneModel, buildSphereGeometry }, manifestRes] =
          await Promise.all([
            import("@xeokit/xeokit-sdk"),
            fetch(MANIFEST_URL),
          ]);
        if (disposed || !canvasRef.current) return;
        xeokitRef.current = { SceneModel, buildSphereGeometry };
        const manifest: ViewerManifest = await manifestRes.json();

        const objectMap: ObjectMapEntry[] = await (
          await fetch(manifest.object_map_src)
        ).json();
        objectMapRef.current = Object.fromEntries(
          objectMap.map((o) => [o.xeokit_object_id, o]));

        const viewer = new Viewer({
          canvasElement: canvasRef.current,
          transparent: true,
          antialias: true,
        });
        viewer.scene.gammaOutput = true;
        // Default view matches the product screenshot: low isometric, close,
        // architecture-forward rather than a top-down technical fit.
        viewer.camera.eye = [72, 34, 86];
        viewer.camera.look = [0, 8, 0];
        viewer.camera.up = [0, 1, 0];
        viewer.cameraControl.followPointer = true;
        viewerRef.current = viewer;

        const initialLayers: Record<string, boolean> = {};

        if (manifest.geometry_format === "xkt") {
          const loader = new XKTLoaderPlugin(viewer);
          let firstLoaded = false;
          for (const asset of manifest.assets) {
            const model = loader.load({
              id: asset.model_id,
              src: asset.src,
              metaModelSrc: asset.metadata_src,
              saoEnabled: false,
              edges: true,
              renderOrder: LAYER_RENDER_ORDER[asset.layer] ?? 0,
            } as any);
            (model as any).visible = asset.default_visible;
            (model as any).renderOrder = LAYER_RENDER_ORDER[asset.layer] ?? 0;
            // Only spaces are pickable so clicks fall through the shell to the
            // zone behind; other layers are visual context.
            (model as any).pickable = asset.pickable === true;
            modelsRef.current[asset.layer] = model;
            initialLayers[asset.layer] = asset.default_visible;
            // style/refit progressively; never block the UI on load events
            model.on("loaded", () => {
              styleDefaults(viewer);
              if (!firstLoaded) {
                firstLoaded = true;
                flyToDefaultBuildingView(viewer, 0.8);
              }
            });
            model.on("error", (e: any) =>
              console.error(`XKT load failed for ${asset.layer}:`, e));
          }
        } else {
          // SceneModel fallback from geometry.json
          const geo = await (await fetch(manifest.geometry_json_src)).json();
          for (const [layerName, layer] of Object.entries<any>(geo.layers)) {
            const model = new SceneModel(viewer.scene, {
              id: `model_${layerName}`,
              isModel: true,
              visible: layers[layerName] !== false,
            });
            for (const obj of layer.objects) {
              model.createMesh({
                id: `${obj.id}_mesh`,
                primitive: "triangles",
                positions: obj.positions,
                indices: obj.indices,
                color: obj.color,
                opacity: obj.opacity,
              } as any);
              model.createEntity({ id: obj.id, meshIds: [`${obj.id}_mesh`], isObject: true });
            }
            model.finalize();
            modelsRef.current[layerName] = model;
            initialLayers[layerName] = layerName !== "fenestration";
          }
        }

        if (disposed) return;
        setLayers(initialLayers);
        styleDefaults(viewer);

        let pickedOnPointer = false;
        let pointerDown: { x: number; y: number } | null = null;
        const canvas = canvasRef.current;
        if (canvas) {
          const onPointerDown = (event: PointerEvent) => {
            pickedOnPointer = false;
            pointerDown = { x: event.clientX, y: event.clientY };
          };
          const onPointerUp = (event: PointerEvent) => {
            if (!pointerDown) return;
            const moved = Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y);
            pointerDown = null;
            if (moved > 4) return;
            window.setTimeout(() => {
              if (!pickedOnPointer) selectEntity(null);
            }, 0);
          };
          canvas.addEventListener("pointerdown", onPointerDown);
          canvas.addEventListener("pointerup", onPointerUp);
          cleanups.push(() => {
            canvas.removeEventListener("pointerdown", onPointerDown);
            canvas.removeEventListener("pointerup", onPointerUp);
          });
        }

        viewer.cameraControl.on("picked", (e: any) => {
          pickedOnPointer = true;
          const id = e.entity?.id as string | undefined;
          if (!id) return;
          const entry = objectMapRef.current[id];
          // surfaces/windows resolve to their zone for inspection
          const key = entry?.entity_type === "ThermalZone"
            ? entry.entity_key
            : entry?.zone_key || entry?.entity_key || id;
          selectEntity(key);
        });
        viewer.cameraControl.on("pickedNothing", () => {
          pickedOnPointer = false;
          selectEntity(null);
        });
        viewer.cameraControl.on("hoverEnter", (e: any) => {
          const id = e.entity?.id as string | undefined;
          if (id && e.canvasPos) setHover({ id, x: e.canvasPos[0], y: e.canvasPos[1] });
        });
        viewer.cameraControl.on("hoverOut", () => setHover(null));
        setReady(true);
      } catch (err: any) {
        console.error("viewer init failed", err);
        setError(String(err?.message || err));
      }
    })();

    return () => {
      disposed = true;
      cleanups.forEach((fn) => fn());
      occupancyModelRef.current = null;
      alertModelRef.current = null;
      viewerRef.current?.destroy?.();
      viewerRef.current = null;
      modelsRef.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function styleSpace(entity: any, entry: ObjectMapEntry) {
    // live (curated) zones pop in teal; the other 294 spaces are faint context
    if (entry.live) {
      entity.colorize = ZONE_BASE_COLOR;
      entity.opacity = 0.42;
    } else {
      entity.colorize = [0.55, 0.62, 0.66];
      entity.opacity = 0.14;
    }
  }

  function styleDefaults(viewer: any) {
    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      const entity = viewer.scene.objects[id];
      if (entity && entry.layer === "spaces") {
        styleSpace(entity, entry);
        // Only the 14 curated/live zones are clickable — they match the table
        // below; the other ~294 spaces are visual context, not selectable.
        entity.pickable = !!entry.live;
      }
    }
    viewer.scene.highlightMaterial.fillColor = [0.06, 0.46, 0.43];
    viewer.scene.highlightMaterial.fillAlpha = 0.5;
    viewer.scene.highlightMaterial.edgeColor = [0.02, 0.3, 0.28];
  }

  // --- layer visibility + x-ray architecture when a discipline is on -------
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;
    for (const [layer, model] of Object.entries(modelsRef.current)) {
      if (model) {
        model.visible = layers[layer] !== false;
        model.renderOrder = LAYER_RENDER_ORDER[layer] ?? 0;
      }
    }
    // Electrical & HVAC must always read FULLY even when stacked under other
    // layers: when either MEP layer is on, x-ray the opaque shell and spaces so
    // MEP stays visually above architecture / zones. MEP itself is never x-rayed.
    const mep = !!(layers.hvac || layers.electrical);
    const xrayShell = mep || activeMetric !== "none";
    for (const shell of ["architecture", "structural", "fenestration"]) {
      const m = modelsRef.current[shell];
      if (m) m.xrayed = xrayShell;
    }
    const spaces = modelsRef.current.spaces;
    if (spaces) spaces.xrayed = mep;
    for (const mepLayer of ["electrical", "hvac"]) {
      const m = modelsRef.current[mepLayer];
      if (m) {
        m.xrayed = false;
        m.opacity = 1;
        m.renderOrder = LAYER_RENDER_ORDER[mepLayer];
      }
    }
    viewer.scene.xrayMaterial.fillAlpha = mep ? 0.035 : 0.05;
    viewer.scene.xrayMaterial.edgeAlpha = mep ? 0.08 : 0.2;

    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      if (entry.layer !== "electrical" && entry.layer !== "hvac") continue;
      const entity = viewer.scene.objects[id];
      if (!entity) continue;
      entity.visible = layers[entry.layer] !== false;
      entity.xrayed = false;
      entity.opacity = 1;
    }
  }, [layers, ready, activeMetric]);

  // --- heatmap overlay from live zone state --------------------------------
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;
    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      if (entry.layer !== "spaces") continue;
      const entity = viewer.scene.objects[id];
      if (!entity) continue;
      // Faults view: tint zones with an open alert by severity, dim the rest.
      if (activeMetric === "faults") {
        const sev = alertByZone[entry.entity_key];
        if (sev) {
          entity.colorize = ALERT_COLOR[sev];
          entity.opacity = sev === "critical" ? 0.62 : 0.5;
        } else {
          styleSpace(entity, entry);
          entity.opacity = 0.1; // recede unaffected zones so faults stand out
        }
        continue;
      }
      const st = zoneStates[entry.entity_key];
      const styled = applyMetricColor(entity, st, activeMetric);
      if (!styled) styleSpace(entity, entry);
    }
  }, [zoneStates, activeMetric, ready, alertByZone]);

  // --- Technical Systems heatmaps (Electrical %Load / HVAC power) -----------
  // No per-element load is mapped onto the architecture XKT yet, so the tint is
  // a floor-stable estimate (reads as a heatmap by storey); swap in real
  // per-object current/power here once that mapping exists.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;
    const ramps: Record<string, [number, number, number][]> = {
      electrical: [[0.13, 0.77, 0.37], [0.92, 0.7, 0.04], [0.94, 0.27, 0.27]],
      hvac: [[0.73, 0.9, 0.99], [0.22, 0.74, 0.97], [0.11, 0.31, 0.85]],
    };
    (["electrical", "hvac"] as const).forEach((layer) => {
      const on = techHeatmap[layer];
      for (const [id, entry] of Object.entries(objectMapRef.current)) {
        if (entry.layer !== layer) continue;
        const entity = viewer.scene.objects[id];
        if (!entity) continue;
        entity.colorize = on
          ? ramp3(ramps[layer], stableUnit(entry.floor_key || entry.entity_key || id))
          : [1, 1, 1];
      }
    });
  }, [techHeatmap, ready, layers]);

  // --- occupancy dots: one red dot per person, scattered in the zone footprint
  useEffect(() => {
    const viewer = viewerRef.current;
    const xk = xeokitRef.current;
    if (!viewer || !ready || !xk) return;

    occupancyModelRef.current?.destroy?.();
    occupancyModelRef.current = null;
    if (activeMetric !== "occupancy") return;

    const model = new xk.SceneModel(viewer.scene, { id: "occupancy_dots", isModel: true });
    const dotGeo = xk.buildSphereGeometry({ radius: 0.45, heightSegments: 8, widthSegments: 8 });
    model.createGeometry({ id: "dot", primitive: "triangles", positions: dotGeo.positions,
      normals: dotGeo.normals, indices: dotGeo.indices });

    const MAX_DOTS_PER_ZONE = 60;
    let meshCount = 0;
    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      if (entry.layer !== "spaces" || !entry.live) continue;
      const st = zoneStates[entry.entity_key];
      const count = Math.min(st?.occupancy_count || 0, MAX_DOTS_PER_ZONE);
      if (count <= 0) continue;
      const entity = viewer.scene.objects[id];
      const aabb = entity?.aabb;
      if (!aabb) continue;
      const [xmin, ymin, zmin, xmax, , zmax] = aabb;
      // small inset so dots don't spawn flush against walls
      const padX = (xmax - xmin) * 0.08;
      const padZ = (zmax - zmin) * 0.08;
      for (let i = 0; i < count; i++) {
        const rnd = seededRandom(`${entry.entity_key}_${i}`);
        const x = xmin + padX + rnd() * Math.max(0.01, xmax - xmin - 2 * padX);
        const z = zmin + padZ + rnd() * Math.max(0.01, zmax - zmin - 2 * padZ);
        const meshId = `dot_${id}_${i}`;
        model.createMesh({ id: meshId, geometryId: "dot", position: [x, ymin + 0.5, z],
          color: [0.86, 0.15, 0.15] });
        model.createEntity({ id: meshId, meshIds: [meshId], isObject: false, pickable: false });
        meshCount++;
      }
    }
    if (meshCount > 0) model.finalize();
    occupancyModelRef.current = model;
  }, [zoneStates, activeMetric, ready]);

  // --- open alerts -> per-zone severity (powers the Faults overlay) ---------
  useEffect(() => {
    if (!ready) return;
    let stop = false;
    const load = () =>
      api.alerts("open").then((rows) => {
        if (stop) return;
        const m: Record<string, AlertSeverity> = {};
        for (const a of rows) {
          const zk = a.zone_key;
          if (!zk) continue;
          const sev = a.severity as AlertSeverity;
          if (!m[zk] || ALERT_RANK[sev] > ALERT_RANK[m[zk]]) m[zk] = sev;
        }
        setAlertByZone(m);
      }).catch(() => null);
    load();
    const t = setInterval(load, 15000);
    return () => { stop = true; clearInterval(t); };
  }, [ready]);

  // --- alert markers: a severity-colored pin floating above each faulted zone
  useEffect(() => {
    const viewer = viewerRef.current;
    const xk = xeokitRef.current;
    if (!viewer || !ready || !xk) return;

    alertModelRef.current?.destroy?.();
    alertModelRef.current = null;
    if (activeMetric !== "faults") return;

    const model = new xk.SceneModel(viewer.scene, { id: "alert_markers", isModel: true });
    const pin = xk.buildSphereGeometry({ radius: 0.9, heightSegments: 12, widthSegments: 12 });
    model.createGeometry({ id: "pin", primitive: "triangles", positions: pin.positions,
      normals: pin.normals, indices: pin.indices });

    let meshCount = 0;
    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      if (entry.layer !== "spaces") continue;
      const sev = alertByZone[entry.entity_key];
      if (!sev) continue;
      const entity = viewer.scene.objects[id];
      const aabb = entity?.aabb;
      if (!aabb) continue;
      const [xmin, , zmin, xmax, ymax, zmax] = aabb;
      const meshId = `pin_${id}`;
      // hover a little above the zone ceiling so the pin reads as a marker
      model.createMesh({ id: meshId, geometryId: "pin",
        position: [(xmin + xmax) / 2, ymax + 1.4, (zmin + zmax) / 2],
        color: ALERT_COLOR[sev] });
      model.createEntity({ id: meshId, meshIds: [meshId], isObject: false, pickable: false });
      meshCount++;
    }
    if (meshCount > 0) model.finalize();
    alertModelRef.current = model;
  }, [alertByZone, activeMetric, ready]);

  // --- agent viewer updates -------------------------------------------------
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready || !viewerUpdates.length) return;
    for (const u of viewerUpdates) {
      const entity = viewer.scene.objects[u.entity_id];
      if (!entity) continue;
      if (u.style.color) entity.colorize = hexToRgb(u.style.color);
      if (u.style.opacity !== undefined) entity.opacity = u.style.opacity;
      else entity.opacity = 0.6;
    }
  }, [viewerUpdates, ready]);

  // --- selection highlight ---------------------------------------------------
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;
    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      const entity = viewer.scene.objects[id];
      if (entity) entity.highlighted = entry.entity_key === selectedEntityKey
        || (entry.layer === "spaces" && id === selectedEntityKey);
    }
  }, [selectedEntityKey, ready]);

  const resetCamera = () => {
    const viewer = viewerRef.current;
    if (viewer) flyToDefaultBuildingView(viewer, 0.6);
  };

  // Capture the wheel inside the 3D card: zoom the scene, never scroll the page.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => e.preventDefault();
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  return (
    <div ref={wrapRef} className={`relative w-full overflow-hidden rounded-card border border-border bg-gradient-to-b from-slate-50 to-white ${heightClass}`}>
      <canvas ref={canvasRef} className="viewer-canvas" />
      {!ready && !error && (
        <div className="absolute inset-0 grid place-items-center">
          <div className="flex flex-col items-center gap-3 text-text-muted">
            <span className="relative flex h-10 w-10 items-center justify-center">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal/20" />
              <Loader2 className="h-7 w-7 animate-spin text-teal" />
            </span>
            <p className="animate-pulse text-sm">Loading digital twin…</p>
          </div>
        </div>
      )}
      {error && (
        <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-danger">
          3D viewer failed to load: {error}
        </div>
      )}
      <LayerPanel />
      <AnalysisBar />
      <ViewModeToolbar onResetCamera={resetCamera} />
      <MetricLegend />
      {hover && (
        <EntityTooltip
          entry={objectMapRef.current[hover.id]}
          state={zoneStates[objectMapRef.current[hover.id]?.entity_key || ""]}
          x={hover.x}
          y={hover.y}
        />
      )}
    </div>
  );
}

function flyToDefaultBuildingView(viewer: any, duration = 0.8) {
  const ids = viewer.scene.visibleObjectIds;
  const aabb = viewer.scene.getAABB(ids);
  if (!aabb || aabb.some((v: number) => !Number.isFinite(v))) return;

  const [xmin, ymin, zmin, xmax, ymax, zmax] = aabb;
  const dx = Math.max(1, xmax - xmin);
  const dy = Math.max(1, ymax - ymin);
  const dz = Math.max(1, zmax - zmin);
  const cx = (xmin + xmax) / 2;
  const cy = (ymin + ymax) / 2;
  const cz = (zmin + zmax) / 2;
  const diag = Math.hypot(dx, dy, dz);

  viewer.cameraFlight.flyTo({
    eye: [cx + diag * 0.48, cy + dy * 0.62, cz + diag * 0.72],
    look: [cx, cy + dy * 0.08, cz],
    up: [0, 1, 0],
    duration,
  });
}

function applyMetricColor(entity: any, st: any, metric: string): boolean {
  if (!st || metric === "none") return false;
  if (metric === "energy") {
    const v = Math.min(1, (st.total_power_kw || 0) / 10);
    entity.colorize = ramp(v);
    entity.opacity = 0.55;
    return true;
  }
  if (metric === "comfort") {
    const level = st.comfort_risk === "high" ? 1 : st.comfort_risk === "watch" ? 0.55 : 0.12;
    entity.colorize = ramp(level);
    entity.opacity = 0.55;
    return true;
  }
  if (metric === "occupancy") {
    const v = Math.min(1, (st.occupancy_count || 0) / 20);
    entity.colorize = [0.15 + 0.1 * v, 0.35 + 0.35 * v, 0.75 - 0.25 * v];
    entity.opacity = 0.3 + 0.4 * v;
    return true;
  }
  return false;
}

/** green -> amber -> red */
function ramp(v: number): [number, number, number] {
  if (v < 0.5) {
    const t = v / 0.5;
    return [0.09 + t * (0.96 - 0.09), 0.64 + t * (0.62 - 0.64), 0.29 + t * (0.04 - 0.29)];
  }
  const t = (v - 0.5) / 0.5;
  return [0.96 - t * (0.96 - 0.86), 0.62 - t * (0.62 - 0.15), 0.04 + t * (0.15 - 0.04)];
}

/** Stable [0,1] from a string key (so a layer's tint is steady, not random). */
function stableUnit(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}

/** Interpolate a 3-stop colour ramp at t∈[0,1]. */
function ramp3(stops: [number, number, number][], t: number): [number, number, number] {
  const x = Math.max(0, Math.min(1, t)) * 2;
  const i = Math.min(1, Math.floor(x));
  const f = x - i;
  const a = stops[i], b = stops[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

function hexToRgb(hex: string): [number, number, number] {
  const m = hex.replace("#", "");
  return [
    parseInt(m.slice(0, 2), 16) / 255,
    parseInt(m.slice(2, 4), 16) / 255,
    parseInt(m.slice(4, 6), 16) / 255,
  ];
}

/**
 * Deterministic PRNG keyed by a string seed (mulberry32), so each person-dot
 * keeps the same scattered position across re-renders instead of jittering
 * every time zoneStates refreshes.
 */
function seededRandom(seed: string): () => number {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  };
}
