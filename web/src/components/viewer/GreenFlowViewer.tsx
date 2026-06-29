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
import { usePollMs } from "@/hooks/usePollMs";
import LayerPanel from "./LayerPanel";
import AnalysisBar from "./AnalysisBar";
import ViewModeToolbar from "./ViewModeToolbar";
import MetricLegend from "./MetricLegend";
import EntityTooltip from "./EntityTooltip";

type XeokitViewer = any;
type AlertSeverity = "critical" | "warning" | "info";

const ZONE_BASE_COLOR: [number, number, number] = [0.06, 0.46, 0.43];
const STRUCTURE_COMPANION_LAYERS = ["architecture", "fenestration"] as const;

// Fault overlay palette (matches FaultsPanel / MetricLegend severity colors).
const ALERT_COLOR: Record<AlertSeverity, [number, number, number]> = {
  critical: [0.86, 0.13, 0.13],
  warning: [0.96, 0.6, 0.04],
  info: [0.58, 0.64, 0.7],
};
const ALERT_RANK: Record<AlertSeverity, number> = { info: 0, warning: 1, critical: 2 };

const LAYER_RENDER_ORDER: Record<string, number> = {
  architecture: 4,
  structure_context: -5,
  structural: 2,
  fenestration: 12,
  spaces: 18,
  electrical: 90,
  hvac: 100,
};

const STRUCTURAL_DEFAULT_LAYERS: Record<string, boolean> = {
  architecture: false,
  spaces: false,
  fenestration: false,
  structural: true,
  hvac: false,
  electrical: false,
};

const STRUCTURE_SITE_YAW_RAD = -0.43;

type SiteRect = [number, number, number, number];
type SiteFrame = { cx: number; cz: number; cos: number; sin: number };

const STRUCTURE_LOADER_DEFAULTS = {
  IfcWall: { colorize: [0.72, 0.72, 0.68], opacity: 1 },
  IfcWallStandardCase: { colorize: [0.72, 0.72, 0.68], opacity: 1 },
  IfcSlab: { colorize: [0.78, 0.78, 0.72], opacity: 1 },
  IfcBuildingElementProxy: { colorize: [0.76, 0.72, 0.65], opacity: 1 },
  IfcRoof: { colorize: [0.12, 0.19, 0.11], opacity: 1 },
  IfcCovering: { colorize: [0.46, 0.26, 0.16], opacity: 1 },
  IfcCurtainWall: { colorize: [0.46, 0.78, 0.84], opacity: 0.5 },
  IfcWindow: { colorize: [0.5, 0.83, 0.9], opacity: 0.5 },
  IfcBeam: { colorize: [0.18, 0.18, 0.17], opacity: 0.28 },
  IfcColumn: { colorize: [0.16, 0.16, 0.15], opacity: 0.26 },
};

export default function GreenFlowViewer({ heightClass = "h-[560px]" }: { heightClass?: string }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const viewerRef = useRef<XeokitViewer | null>(null);
  const modelsRef = useRef<Record<string, any>>({});
  const objectMapRef = useRef<Record<string, ObjectMapEntry>>({});
  const metaTypeByObjectRef = useRef<Record<string, string>>({});
  const xeokitRef = useRef<{ SceneModel: any; buildSphereGeometry: any } | null>(null);
  const occupancyModelRef = useRef<any>(null);
  const alertModelRef = useRef<any>(null);
  const structureContextModelRef = useRef<any>(null);
  const structureContextUsedFallbackRef = useRef(false);
  const wasStructuralOnRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [geometryVersion, setGeometryVersion] = useState(0);
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
  const pollMs = usePollMs(15000);

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
        metaTypeByObjectRef.current = await loadMetaTypes(manifest.assets);

        const viewer = new Viewer({
          canvasElement: canvasRef.current,
          transparent: true,
          antialias: true,
          colorTextureEnabled: true,
          pbrEnabled: true,
        } as any);
        viewer.scene.gammaOutput = true;
        viewer.scene.colorTextureEnabled = true;
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
            const layerKey = normalizeLayer(asset.layer);
            const model = loader.load({
              id: asset.model_id,
              src: asset.src,
              metaModelSrc: asset.metadata_src,
              saoEnabled: false,
              edges: true,
              renderOrder: LAYER_RENDER_ORDER[layerKey] ?? 0,
              objectDefaults: ["architecture", "structural", "fenestration"].includes(layerKey)
                ? STRUCTURE_LOADER_DEFAULTS
                : undefined,
            } as any);
            (model as any).visible = asset.default_visible;
            (model as any).renderOrder = LAYER_RENDER_ORDER[layerKey] ?? 0;
            // Only spaces are pickable so clicks fall through the shell to the
            // zone behind; other layers are visual context.
            (model as any).pickable = asset.pickable === true;
            modelsRef.current[layerKey] = model;
            initialLayers[layerKey] = asset.default_visible;
            // style/refit progressively; never block the UI on load events
            model.on("loaded", () => {
              styleDefaults(viewer);
              setGeometryVersion((v) => v + 1);
              window.setTimeout(() => {
                if (useAppStore.getState().layers.structural) {
                  forceStructureShellVisible(modelsRef.current, useAppStore.getState().layers.architecture);
                  flyToStructurePresentationView(viewer, objectMapRef.current, modelsRef.current, 0.35);
                }
              }, 250);
              if (!firstLoaded) {
                firstLoaded = true;
                flyToStructurePresentationView(viewer, objectMapRef.current, modelsRef.current, 0.8);
              }
            });
            model.on("error", (e: any) =>
              console.error(`XKT load failed for ${layerKey}:`, e));
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
        setLayers({ ...initialLayers, ...STRUCTURAL_DEFAULT_LAYERS });
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
      structureContextModelRef.current?.destroy?.();
      structureContextModelRef.current = null;
      structureContextUsedFallbackRef.current = false;
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
    const structuralOn = !!layers.structural;
    const architectureOn = !!layers.architecture;
    for (const [layer, model] of Object.entries(modelsRef.current)) {
      if (model) {
        const companionVisible =
          structuralOn &&
          STRUCTURE_COMPANION_LAYERS.includes(layer as typeof STRUCTURE_COMPANION_LAYERS[number]) &&
          (!architectureOn || layer === "fenestration");
        model.visible = companionVisible || layers[layer] !== false;
        model.renderOrder = LAYER_RENDER_ORDER[layer] ?? 0;
        if (companionVisible) model.pickable = false;
      }
    }
    if (structuralOn) {
      let contextCreated = false;
      if (structureContextModelRef.current && structureContextUsedFallbackRef.current && geometryVersion > 1) {
        structureContextModelRef.current.destroy?.();
        structureContextModelRef.current = null;
        structureContextUsedFallbackRef.current = false;
      }
      if (!structureContextModelRef.current) {
        try {
          structureContextModelRef.current = createStructureContextModel(
            viewer,
            xeokitRef.current?.SceneModel,
            xeokitRef.current?.buildSphereGeometry,
            objectMapRef.current,
            modelsRef.current,
          );
          structureContextUsedFallbackRef.current = !!structureContextModelRef.current?.__greenflowFallbackAABB;
        } catch (err) {
          console.warn("Structure site context failed; keeping building geometry visible.", err);
          structureContextModelRef.current = null;
          structureContextUsedFallbackRef.current = false;
        }
        contextCreated = !!structureContextModelRef.current;
      }
      if (structureContextModelRef.current) structureContextModelRef.current.visible = true;
      try {
        applyStructurePresentationStyle(viewer, objectMapRef.current, metaTypeByObjectRef.current);
        enablePresentationRendering(viewer);
      } catch (err) {
        console.warn("Structure presentation styling failed; using raw model visibility.", err);
      }
      forceStructureShellVisible(modelsRef.current, architectureOn);
      if (!wasStructuralOnRef.current || contextCreated) {
        flyToStructurePresentationView(viewer, objectMapRef.current, modelsRef.current, 0.7);
      }
    } else {
      if (structureContextModelRef.current) structureContextModelRef.current.visible = false;
      resetStructurePresentationStyle(viewer, objectMapRef.current);
      resetStructureModelStyle(modelsRef.current);
    }
    wasStructuralOnRef.current = structuralOn;

    // Electrical & HVAC must always read FULLY even when stacked under other
    // layers: when either MEP layer is on, x-ray the opaque shell and spaces so
    // MEP stays visually above architecture / zones. MEP itself is never x-rayed.
    const mep = !!(layers.hvac || layers.electrical);
    const xrayShell = mep || activeMetric !== "none";
    for (const shell of ["architecture", "structural", "fenestration"]) {
      const m = modelsRef.current[shell];
      if (m) m.xrayed = structuralOn ? false : xrayShell;
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
  }, [layers, ready, activeMetric, geometryVersion]);

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
    const t = setInterval(load, pollMs);
    return () => { stop = true; clearInterval(t); };
  }, [ready, pollMs]);

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
    if (!viewer) return;
    if (layers.structural) {
      flyToStructurePresentationView(viewer, objectMapRef.current, modelsRef.current, 0.6);
    } else {
      flyToDefaultBuildingView(viewer, 0.6);
    }
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

function flyToStructurePresentationView(
  viewer: any,
  objectMap: Record<string, ObjectMapEntry>,
  models: Record<string, any>,
  duration = 0.8,
) {
  const aabb = getBuildingAABB(viewer, objectMap, models);
  if (!aabb) return;

  const [xmin, ymin, zmin, xmax, ymax, zmax] = aabb;
  const dx = Math.max(1, xmax - xmin);
  const dy = Math.max(1, ymax - ymin);
  const dz = Math.max(1, zmax - zmin);
  const cx = (xmin + xmax) / 2;
  const cy = (ymin + ymax) / 2;
  const cz = (zmin + zmax) / 2;
  const diag = Math.hypot(dx, dy, dz);

  viewer.cameraFlight.flyTo({
    eye: [cx + diag * 0.52, cy + Math.max(34, dy * 1.12), cz + diag * 0.72],
    look: [cx + dx * 0.03, cy + dy * 0.1, cz],
    up: [0, 1, 0],
    duration,
  });
}

function forceStructureShellVisible(models: Record<string, any>, architectureOn: boolean) {
  if (models.structural) {
    models.structural.visible = true;
    models.structural.xrayed = false;
    models.structural.colorize = [0.28, 0.28, 0.26];
    models.structural.opacity = 0.08;
    models.structural.renderOrder = LAYER_RENDER_ORDER.structural;
  }
  if (models.fenestration) {
    models.fenestration.visible = true;
    models.fenestration.xrayed = false;
    models.fenestration.colorize = [0.48, 0.82, 0.9];
    models.fenestration.opacity = 0.58;
    models.fenestration.renderOrder = LAYER_RENDER_ORDER.fenestration;
    styleModelEntityList(models.fenestration, "fenestration");
  }
  if (!architectureOn && models.architecture) {
    models.architecture.visible = true;
    models.architecture.pickable = false;
    models.architecture.colorize = null;
    models.architecture.opacity = 1;
    models.architecture.renderOrder = LAYER_RENDER_ORDER.architecture;
    styleModelEntityList(models.architecture, "architecture");
  }
}

function resetStructureModelStyle(models: Record<string, any>) {
  for (const key of ["architecture", "structural", "fenestration"]) {
    const model = models[key];
    if (!model) continue;
    model.colorize = null;
    model.opacity = 1;
    model.xrayed = false;
    for (const entity of model?.entityList || model?._entityList || []) {
      entity.visible = true;
      entity.colorize = null;
      entity.opacity = 1;
      entity.xrayed = false;
    }
  }
}

function styleModelEntityList(model: any, layer: "architecture" | "fenestration") {
  const entities = model?.entityList || model?._entityList || [];
  for (const entity of entities) {
    const key = `${entity?.id || ""} ${entity?.name || ""}`.toLowerCase();
    entity.xrayed = false;
    if (layer === "fenestration") {
      entity.colorize = [0.5, 0.84, 0.9];
      entity.opacity = 0.58;
      continue;
    }
    if (key.includes("roof") || key.includes("vesikatto")) {
      entity.colorize = [0.12, 0.2, 0.1];
      entity.opacity = 1;
    } else if (key.includes("level_05") || key.includes("level_04")) {
      entity.colorize = [0.44, 0.25, 0.15];
      entity.opacity = 1;
    } else if (key.includes("basement") || key.includes("parking")) {
      entity.colorize = [0.14, 0.15, 0.14];
      entity.opacity = 0.05;
    } else if (key.includes("level_01")) {
      entity.colorize = [0.58, 0.58, 0.53];
      entity.opacity = 1;
    } else {
      entity.colorize = [0.72, 0.72, 0.68];
      entity.opacity = 1;
    }
    entity.edges = layer === "architecture";
  }
}

function normalizeLayer(layer: string) {
  return layer === "thermal_zones" ? "spaces" : layer;
}

async function loadMetaTypes(assets: Array<{ metadata_src?: string }>) {
  const metaTypes: Record<string, string> = {};
  await Promise.all(assets.map(async (asset) => {
    if (!asset.metadata_src) return;
    try {
      const data = await (await fetch(asset.metadata_src)).json();
      for (const obj of data?.metaObjects || []) {
        if (obj?.id && obj?.type) metaTypes[obj.id] = obj.type;
      }
    } catch {
      // Presentation styling falls back to object-map layer defaults.
    }
  }));
  return metaTypes;
}

const STRUCTURE_STYLE_MAP: Record<string, { color?: [number, number, number]; opacity?: number; visible?: boolean }> = {
  IfcSite: { color: [0.42, 0.43, 0.39], opacity: 1.0 },
  IfcBuildingElementProxy: { color: [0.7, 0.69, 0.63], opacity: 1.0 },
  IfcSlab: { color: [0.76, 0.76, 0.7], opacity: 1.0 },
  IfcWall: { color: [0.72, 0.72, 0.68], opacity: 1.0 },
  IfcWallStandardCase: { color: [0.72, 0.72, 0.68], opacity: 1.0 },
  IfcCurtainWall: { color: [0.45, 0.77, 0.84], opacity: 0.52 },
  IfcWindow: { color: [0.5, 0.84, 0.9], opacity: 0.56 },
  IfcDoor: { color: [0.1, 0.1, 0.09], opacity: 1.0 },
  IfcRoof: { color: [0.12, 0.2, 0.1], opacity: 1.0 },
  IfcCovering: { color: [0.44, 0.25, 0.15], opacity: 1.0 },
  IfcBeam: { color: [0.18, 0.18, 0.17], opacity: 0.28 },
  IfcColumn: { color: [0.16, 0.16, 0.15], opacity: 0.24 },
  IfcPlate: { color: [0.62, 0.64, 0.61], opacity: 1.0 },
  IfcRailing: { color: [0.09, 0.09, 0.08], opacity: 1.0 },
  IfcStair: { color: [0.62, 0.62, 0.58], opacity: 1.0 },
  IfcSpace: { visible: false },
  IfcDuctSegment: { visible: false },
  IfcPipeSegment: { visible: false },
  IfcCableCarrierSegment: { visible: false },
  IfcLightFixture: { visible: false },
};

function styleForPresentation(entry: ObjectMapEntry, ifcType?: string) {
  if (!["architecture", "structural", "fenestration"].includes(entry.layer)) return null;
  if (entry.layer === "fenestration") return STRUCTURE_STYLE_MAP.IfcWindow;
  if (entry.layer === "structural") return STRUCTURE_STYLE_MAP.IfcColumn;
  if (entry.layer === "architecture") {
    const floor = String(entry.floor_key || entry.name || "").toLowerCase();
    if (floor.includes("roof") || floor.includes("vesikatto")) return STRUCTURE_STYLE_MAP.IfcRoof;
    if (floor.includes("level_05") || floor.includes("level_04")) return STRUCTURE_STYLE_MAP.IfcCovering;
    if (floor.includes("basement") || floor.includes("parking")) return { color: [0.14, 0.15, 0.14] as [number, number, number], opacity: 0.05 };
    if (floor.includes("level_01")) return { color: [0.58, 0.58, 0.53] as [number, number, number], opacity: 1 };
    return STRUCTURE_STYLE_MAP.IfcWall;
  }
  if (ifcType && STRUCTURE_STYLE_MAP[ifcType]) return STRUCTURE_STYLE_MAP[ifcType];
  return null;
}

function applyStructurePresentationStyle(
  viewer: any,
  objectMap: Record<string, ObjectMapEntry>,
  metaTypes: Record<string, string>,
) {
  for (const [id, entry] of Object.entries(objectMap)) {
    const entity = viewer.scene.objects[id];
    if (!entity) continue;
    const ifcType = metaTypes[id];
    const style = styleForPresentation(entry, ifcType);
    if (!style) continue;
    if (style.visible === false) {
      entity.visible = false;
      continue;
    }
    if (style.color) entity.colorize = style.color;
    if (style.opacity != null) entity.opacity = style.opacity;
    entity.xrayed = false;
    entity.edges = entry.layer === "architecture";
    entity.pickable = entry.layer === "spaces" ? !!entry.live : false;
  }
}

function resetStructurePresentationStyle(viewer: any, objectMap: Record<string, ObjectMapEntry>) {
  for (const [id, entry] of Object.entries(objectMap)) {
    if (!["architecture", "structural", "fenestration"].includes(entry.layer)) continue;
    const entity = viewer.scene.objects[id];
    if (!entity) continue;
    entity.colorize = null;
    entity.opacity = 1;
    entity.xrayed = false;
    entity.edges = entry.layer !== "fenestration";
  }
}

function enablePresentationRendering(viewer: any) {
  if (viewer.scene?.sao) {
    viewer.scene.sao.enabled = true;
    viewer.scene.sao.intensity = 0.13;
    viewer.scene.sao.bias = 0.38;
    viewer.scene.sao.scale = 420;
  }
  if (viewer.scene?.edgeMaterial) {
    viewer.scene.edgeMaterial.edgeAlpha = 0.1;
    viewer.scene.edgeMaterial.edgeColor = [0.24, 0.28, 0.3];
  }
}

function createStructureContextModel(
  viewer: any,
  SceneModel: any,
  buildSphereGeometry: any,
  objectMap: Record<string, ObjectMapEntry>,
  models: Record<string, any>,
) {
  if (!SceneModel) return null;
  const aabb = getBuildingAABB(viewer, objectMap, models);
  if (!aabb || aabb.some((v: number) => !Number.isFinite(v))) return null;

  const [xmin, ymin, zmin, xmax, ymax, zmax] = aabb;
  const dx = Math.max(20, xmax - xmin);
  const dz = Math.max(20, zmax - zmin);
  const cx = (xmin + xmax) / 2;
  const cz = (zmin + zmax) / 2;
  const isFallbackAABB = isStructureFallbackAABB(aabb);
  const estimatedGradeY = isFallbackAABB ? 0 : estimateGradeY(viewer, objectMap, ymin);
  const gradeY = isFallbackAABB ? 0 : chooseStructureGradeY(ymin, ymaxFromAABB(aabb), estimatedGradeY);
  const groundY = Math.abs(gradeY) > 1000 ? 0.02 : gradeY + 0.018;
  const pad = Math.max(dx, dz) * 1.12;
  const siteFrame = createSiteFrame(cx, cz, STRUCTURE_SITE_YAW_RAD);
  viewer.scene.models?.structure_site_context?.destroy?.();
  const model = new SceneModel(viewer.scene, {
    id: "structure_site_context",
    isModel: true,
    visible: true,
  });

  try {
    const textures = createSiteTextureSets(model);
    const treeGeometry = createTreeGeometry(model, buildSphereGeometry);
    const outer: SiteRect = [
      -dx / 2 - pad * 1.35,
      -dz / 2 - pad * 0.95,
      dx / 2 + pad * 1.35,
      dz / 2 + pad * 0.95,
    ];
    const plaza: SiteRect = [
      -dx / 2 - Math.max(13, dx * 0.18),
      -dz / 2 - Math.max(12, dz * 0.22),
      dx / 2 + Math.max(17, dx * 0.24),
      dz / 2 + Math.max(14, dz * 0.25),
    ];
    const footprint: SiteRect = [
      -dx / 2 + Math.max(0.45, dx * 0.012),
      -dz / 2 + Math.max(0.45, dz * 0.012),
      dx / 2 - Math.max(0.45, dx * 0.012),
      dz / 2 - Math.max(0.45, dz * 0.012),
    ];

    // Base slabs are deliberately solid-color boxes. They are the reliability
    // layer: even if texture UVs/images fail on a deployment, Structure mode
    // still shows a complete site/context instead of reverting to white.
    createOrientedBox(model, "structure_context_grass_base", outer,
      groundY - 0.05, groundY + 0.002, [0.28, 0.43, 0.27], 1, 0.94, siteFrame);
    createOrientedRingSlab(model, "structure_context_concrete_plaza_base", plaza, footprint,
      groundY + 0.004, groundY + 0.03, [0.68, 0.68, 0.63], 1, siteFrame);
    createOrientedBox(model, "structure_context_road_main_base",
      [outer[0], dz / 2 + pad * 0.36, outer[2], dz / 2 + pad * 0.53],
      groundY + 0.006, groundY + 0.04,
      [0.22, 0.24, 0.25], 1, 0.95, siteFrame);
    createOrientedBox(model, "structure_context_road_side_base",
      [-dx / 2 - pad * 0.94, outer[1], -dx / 2 - pad * 0.76, outer[3]],
      groundY + 0.007, groundY + 0.041,
      [0.23, 0.24, 0.25], 1, 0.95, siteFrame);

    createOrientedTexturedPlane(model, "structure_context_grass", outer,
      groundY + 0.008, [0.25, 0.4, 0.25], textures.grass, 7, siteFrame);
    createOrientedRingSurface(model, "structure_context_concrete_plaza", plaza, footprint,
      groundY + 0.034, [0.67, 0.67, 0.62], textures.concrete, 4, siteFrame);
    createOrientedContextTexturePatches(model, outer, plaza, groundY + 0.04, siteFrame);

    createOrientedTexturedPlane(model, "structure_context_road_main",
      [outer[0], dz / 2 + pad * 0.36, outer[2], dz / 2 + pad * 0.53],
      groundY + 0.045, [0.2, 0.22, 0.23], textures.asphalt, 3.5, siteFrame);
    createOrientedTexturedPlane(model, "structure_context_road_side",
      [-dx / 2 - pad * 0.94, outer[1], -dx / 2 - pad * 0.76, outer[3]],
      groundY + 0.046, [0.21, 0.22, 0.23], textures.asphalt, 3.5, siteFrame);
    createOrientedTexturedPlane(model, "structure_context_walkway",
      [plaza[0] - 8, -dz / 2 - Math.max(10, dz * 0.26), plaza[2] + 10, -dz / 2 - Math.max(6, dz * 0.14)],
      groundY + 0.058, [0.72, 0.72, 0.66], textures.concrete, 3, siteFrame);

    createSiteDetails(model, siteFrame, outer, plaza, dx, dz, pad, groundY);

    const blocks = [
      [-dx * 0.78, -dz * 0.74, 0.16, 0.16],
      [dx * 0.76, -dz * 0.64, 0.18, 0.15],
      [-dx * 0.68, dz * 0.72, 0.14, 0.16],
      [dx * 0.66, dz * 0.68, 0.13, 0.14],
    ];
    blocks.forEach(([bu, bv, sx, sz], i) => {
      createOrientedBox(model, `structure_context_block_${i}`,
        [bu - dx * sx, bv - dz * sz, bu + dx * sx, bv + dz * sz],
        groundY, groundY + 2.2 + i * 0.55, [0.64, 0.64, 0.58], 0.38, 0.9, siteFrame);
    });

    createDistributedTrees(model, siteFrame, outer, plaza, groundY, treeGeometry);
  } catch (err) {
    model.destroy?.();
    throw err;
  }

  model.finalize();
  model.pickable = false;
  model.renderOrder = LAYER_RENDER_ORDER.structure_context;
  model.__greenflowFallbackAABB = isFallbackAABB;
  console.info("Structure site context ready", {
    aabb: aabb.map((v: number) => Number(v.toFixed(2))),
    groundY: Number(groundY.toFixed(2)),
    dx: Number(dx.toFixed(2)),
    dz: Number(dz.toFixed(2)),
    fallback: isFallbackAABB,
  });
  return model;
}

function getBuildingAABB(
  viewer: any,
  objectMap: Record<string, ObjectMapEntry>,
  models: Record<string, any>,
) {
  const modelAABBs = ["architecture", "structural", "fenestration"]
    .map((key) => models[key]?.aabb)
    .map(normalizeAABB)
    .filter(Boolean) as number[][];
  if (modelAABBs.length) return unionAABBs(modelAABBs);

  const ids = Object.entries(objectMap)
    .filter(([, entry]) => ["architecture", "structural", "fenestration"].includes(entry.layer))
    .map(([id]) => id)
    .filter((id) => viewer.scene.objects[id]);
  const visible = (viewer.scene.visibleObjectIds || [])
    .filter((id: string) => !id.startsWith("structure_context_"));
  const aabb = normalizeAABB(viewer.scene.getAABB(ids.length ? ids : visible));
  if (aabb) return aabb;

  // Conservative fallback: matches the default camera extents closely enough
  // to keep the site visible even before all XKT metadata resolves.
  return [-65, 0, -48, 85, 30, 58];
}

function isStructureFallbackAABB(aabb: number[]) {
  return aabb[0] === -65 && aabb[1] === 0 && aabb[2] === -48
    && aabb[3] === 85 && aabb[4] === 30 && aabb[5] === 58;
}

function normalizeAABB(aabb: any): number[] | null {
  if (!aabb || aabb.length < 6) return null;
  const values = Array.from(aabb as ArrayLike<number>).slice(0, 6);
  if (values.some((v) => !Number.isFinite(v))) return null;
  const [xmin, ymin, zmin, xmax, ymax, zmax] = values;
  const dx = xmax - xmin;
  const dy = ymax - ymin;
  const dz = zmax - zmin;
  if (dx <= 0 || dy <= 0 || dz <= 0) return null;
  // xeokit returns +/- Number.MAX_SAFE_INTEGER sentinels before some model AABBs
  // are initialized. Treat any absurd range as invalid and fall back.
  if (Math.max(Math.abs(xmin), Math.abs(ymin), Math.abs(zmin), Math.abs(xmax), Math.abs(ymax), Math.abs(zmax)) > 1_000_000) {
    return null;
  }
  if (Math.max(dx, dy, dz) > 10_000) return null;
  return values;
}

function unionAABBs(aabbs: number[][]) {
  return aabbs.reduce((acc, aabb) => [
    Math.min(acc[0], aabb[0]),
    Math.min(acc[1], aabb[1]),
    Math.min(acc[2], aabb[2]),
    Math.max(acc[3], aabb[3]),
    Math.max(acc[4], aabb[4]),
    Math.max(acc[5], aabb[5]),
  ], [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]);
}

function estimateGradeY(viewer: any, objectMap: Record<string, ObjectMapEntry>, fallbackY: number) {
  const preferred: number[] = [];
  const basementTops: number[] = [];
  const nonBasement: number[] = [];
  const all: number[] = [];
  for (const [id, entry] of Object.entries(objectMap)) {
    if (!["architecture", "structural", "fenestration", "spaces"].includes(entry.layer)) continue;
    const entity = viewer.scene.objects[id];
    const aabb = normalizeAABB(entity?.aabb);
    if (!aabb) continue;
    const floor = `${entry.floor_key || ""} ${entry.name || ""}`.toLowerCase();
    all.push(aabb[1]);
    const isBasement = floor.includes("basement") || floor.includes("kellari");
    if (isBasement && Number.isFinite(aabb[4])) basementTops.push(aabb[4]);
    if (floor.includes("level_01") || floor.includes("01_kerros")) preferred.push(aabb[1]);
    if (!isBasement && !floor.includes("roof")) nonBasement.push(aabb[1]);
  }
  if (basementTops.length) {
    const basementTop = Math.max(...basementTops);
    if (preferred.length) return Math.max(basementTop, Math.min(...preferred));
    return basementTop;
  }
  if (preferred.length) return Math.min(...preferred);
  if (nonBasement.length) return Math.min(...nonBasement);
  const unique = Array.from(new Set(all.map((v) => Number(v.toFixed(2))))).sort((a, b) => a - b);
  return unique[1] ?? unique[0] ?? fallbackY;
}

function ymaxFromAABB(aabb: number[]) {
  return aabb[4] ?? aabb[1];
}

function chooseStructureGradeY(ymin: number, ymax: number, candidate: number) {
  const dy = Math.max(1, ymax - ymin);
  // The dark basement/plinth band belongs below exterior grade. The landscape
  // should cut at the top of that band, not at the raw model ymin. XKT floor
  // AABBs are not always reliable, so use a conservative low-height datum.
  const plinthTop = Math.max(ymin, (ymin < -0.5 ? 0 : ymin) + Math.min(5.2, Math.max(3.6, dy * 0.155)));
  if (!Number.isFinite(candidate)) return plinthTop;
  // Per-object AABBs in some generated XKT metadata report floor objects near
  // roof height. Reject those; grade must live close to the lower quarter of the
  // building, never near the roof.
  if (candidate < ymin - 0.25 || candidate > ymin + Math.max(3, dy * 0.25)) {
    return plinthTop;
  }
  if (candidate < plinthTop - 0.35) return plinthTop;
  return candidate;
}

function createSiteFrame(cx: number, cz: number, yaw: number): SiteFrame {
  return { cx, cz, cos: Math.cos(yaw), sin: Math.sin(yaw) };
}

function sitePoint(frame: SiteFrame, u: number, v: number): [number, number] {
  return [
    frame.cx + u * frame.cos - v * frame.sin,
    frame.cz + u * frame.sin + v * frame.cos,
  ];
}

function createOrientedRingSlab(
  model: any,
  id: string,
  outer: SiteRect,
  inner: SiteRect,
  y0: number,
  y1: number,
  color: [number, number, number],
  opacity: number,
  frame: SiteFrame,
) {
  const [ox0, ov0, ox1, ov1] = outer;
  const [ix0, iv0, ix1, iv1] = inner;
  createOrientedBox(model, `${id}_north`, [ox0, ov0, ox1, iv0], y0, y1, color, opacity, 0.9, frame);
  createOrientedBox(model, `${id}_south`, [ox0, iv1, ox1, ov1], y0, y1, color, opacity, 0.9, frame);
  createOrientedBox(model, `${id}_west`, [ox0, iv0, ix0, iv1], y0, y1, color, opacity, 0.9, frame);
  createOrientedBox(model, `${id}_east`, [ix1, iv0, ox1, iv1], y0, y1, color, opacity, 0.9, frame);
}

function createOrientedBox(
  model: any,
  id: string,
  rect: SiteRect,
  y0: number,
  y1: number,
  color: [number, number, number],
  opacity = 1,
  roughness = 0.84,
  frame: SiteFrame,
) {
  const [u0, v0, u1, v1] = rect;
  const p00 = sitePoint(frame, u0, v0);
  const p10 = sitePoint(frame, u1, v0);
  const p11 = sitePoint(frame, u1, v1);
  const p01 = sitePoint(frame, u0, v1);
  const positions = [
    p00[0], y0, p00[1], p10[0], y0, p10[1], p10[0], y1, p10[1], p00[0], y1, p00[1],
    p01[0], y0, p01[1], p11[0], y0, p11[1], p11[0], y1, p11[1], p01[0], y1, p01[1],
  ];
  const indices = [
    0, 1, 2, 0, 2, 3,
    4, 6, 5, 4, 7, 6,
    0, 4, 5, 0, 5, 1,
    3, 2, 6, 3, 6, 7,
    1, 5, 6, 1, 6, 2,
    0, 3, 7, 0, 7, 4,
  ];
  const meshId = `${id}_mesh`;
  model.createMesh({ id: meshId, primitive: "triangles", positions, indices, color, opacity, metallic: 0, roughness } as any);
  model.createEntity({ id, meshIds: [meshId], isObject: false, pickable: false });
}

function createOrientedRingSurface(
  model: any,
  id: string,
  outer: SiteRect,
  inner: SiteRect,
  y: number,
  color: [number, number, number],
  textureSetId: string | undefined,
  repeatScale: number,
  frame: SiteFrame,
) {
  const [ox0, ov0, ox1, ov1] = outer;
  const [ix0, iv0, ix1, iv1] = inner;
  createOrientedTexturedPlane(model, `${id}_north`, [ox0, ov0, ox1, iv0], y, color, textureSetId, repeatScale, frame);
  createOrientedTexturedPlane(model, `${id}_south`, [ox0, iv1, ox1, ov1], y, color, textureSetId, repeatScale, frame);
  createOrientedTexturedPlane(model, `${id}_west`, [ox0, iv0, ix0, iv1], y, color, textureSetId, repeatScale, frame);
  createOrientedTexturedPlane(model, `${id}_east`, [ix1, iv0, ox1, iv1], y, color, textureSetId, repeatScale, frame);
}

function createOrientedTexturedPlane(
  model: any,
  id: string,
  rect: SiteRect,
  y: number,
  color: [number, number, number],
  textureSetId: string | undefined,
  repeatScale: number,
  frame: SiteFrame,
) {
  const [u0, v0, u1, v1] = rect;
  const p00 = sitePoint(frame, u0, v0);
  const p10 = sitePoint(frame, u1, v0);
  const p11 = sitePoint(frame, u1, v1);
  const p01 = sitePoint(frame, u0, v1);
  const width = Math.max(1, Math.abs(u1 - u0));
  const depth = Math.max(1, Math.abs(v1 - v0));
  const repeatX = Math.max(1, width / repeatScale);
  const repeatZ = Math.max(1, depth / repeatScale);
  const meshId = `${id}_mesh`;
  model.createMesh({
    id: meshId,
    primitive: "triangles",
    positions: [p00[0], y, p00[1], p10[0], y, p10[1], p11[0], y, p11[1], p01[0], y, p01[1]],
    normals: [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
    uv: [0, 0, repeatX, 0, repeatX, repeatZ, 0, repeatZ],
    indices: [0, 2, 1, 0, 3, 2],
    color,
    textureSetId,
    opacity: 1,
    metallic: 0,
    roughness: 0.9,
  } as any);
  model.createEntity({ id, meshIds: [meshId], isObject: false, pickable: false });
}

function createOrientedContextTexturePatches(
  model: any,
  outer: SiteRect,
  hole: SiteRect,
  y: number,
  frame: SiteFrame,
) {
  const [ou0, ov0, ou1, ov1] = outer;
  const [hu0, hv0, hu1, hv1] = hole;
  for (let i = 0; i < 36; i++) {
    const rnd = seededRandom(`oriented_context_patch_${i}`);
    let u = ou0 + rnd() * (ou1 - ou0);
    let v = ov0 + rnd() * (ov1 - ov0);
    if (u > hu0 && u < hu1 && v > hv0 && v < hv1) {
      u = u < (hu0 + hu1) / 2 ? hu0 - 8 - rnd() * 14 : hu1 + 8 + rnd() * 14;
    }
    const su = 3 + rnd() * 7;
    const sv = 2 + rnd() * 6;
    const green = 0.3 + rnd() * 0.09;
    createOrientedTexturedPlane(model, `structure_context_grass_patch_${i}`,
      [u - su, v - sv, u + su, v + sv], y + i * 0.0004, [0.2, green, 0.19], undefined, 3, frame);
  }
}

function createTreeGeometry(model: any, buildSphereGeometry: any) {
  if (!buildSphereGeometry) return null;
  try {
    const geo = buildSphereGeometry({ radius: 1, heightSegments: 18, widthSegments: 18 });
    model.createGeometry({ id: "structure_tree_leaf_sphere", primitive: "triangles", positions: geo.positions,
      normals: geo.normals, indices: geo.indices });
    return "structure_tree_leaf_sphere";
  } catch {
    return null;
  }
}

function createSiteDetails(
  model: any,
  frame: SiteFrame,
  outer: SiteRect,
  plaza: SiteRect,
  dx: number,
  dz: number,
  pad: number,
  groundY: number,
) {
  for (let i = 0; i < 8; i++) {
    const u = -dx * 0.43 + i * dx * 0.12;
    const v = dz / 2 + pad * 0.23;
    const carColor: [number, number, number] = i % 3 === 0 ? [0.18, 0.22, 0.26] : i % 3 === 1 ? [0.72, 0.72, 0.68] : [0.36, 0.42, 0.45];
    createCar(model, frame, `structure_context_car_${i}`, u, v, groundY + 0.05, carColor);
  }
  for (let i = 0; i < 12; i++) {
    const u = plaza[0] + 10 + i * Math.max(7, dx / 8);
    createLampPost(model, frame, `structure_context_lamp_front_${i}`, u, plaza[1] + 4, groundY);
    if (i % 2 === 0) createBench(model, frame, `structure_context_bench_${i}`, u + 2.5, plaza[1] + 9, groundY);
  }
  for (let i = 0; i < 10; i++) {
    const u = outer[0] + 16 + i * ((outer[2] - outer[0] - 32) / 9);
    createLampPost(model, frame, `structure_context_lamp_back_${i}`, u, dz / 2 + pad * 0.31, groundY);
  }
}

function createDistributedTrees(
  model: any,
  frame: SiteFrame,
  outer: SiteRect,
  plaza: SiteRect,
  groundY: number,
  treeGeometryId: string | null,
) {
  const points: Array<[number, number, number]> = [];
  const add = (u: number, v: number, scale: number) => {
    if (insideRect(plaza, u, v, 7)) return;
    points.push([u, v, scale]);
  };
  for (let i = 0; i < 18; i++) {
    const t = i / 17;
    add(outer[0] + (outer[2] - outer[0]) * t, outer[1] + 9 + (i % 3) * 3, 1.1 + (i % 4) * 0.12);
    add(outer[0] + (outer[2] - outer[0]) * t, outer[3] - 9 - (i % 2) * 3, 1.15 + (i % 5) * 0.1);
  }
  for (let i = 0; i < 10; i++) {
    const t = i / 9;
    add(outer[0] + 9 + (i % 2) * 3, outer[1] + (outer[3] - outer[1]) * t, 1.05 + (i % 3) * 0.16);
    add(outer[2] - 10 - (i % 2) * 4, outer[1] + (outer[3] - outer[1]) * t, 1.05 + (i % 4) * 0.12);
  }
  for (let i = 0; i < 12; i++) {
    const t = i / 11;
    const u = plaza[0] + 8 + (plaza[2] - plaza[0] - 16) * t;
    add(u, plaza[1] - 12 - (i % 2) * 4, 1.24 + (i % 3) * 0.14);
    if (i % 2 === 0) add(u + 3, plaza[3] + 12 + (i % 3) * 3, 1.16 + (i % 4) * 0.12);
  }
  for (let i = 0; i < 18; i++) {
    const rnd = seededRandom(`tree_cluster_${i}`);
    add(outer[0] + 18 + rnd() * (outer[2] - outer[0] - 36),
      outer[1] + 18 + rnd() * (outer[3] - outer[1] - 36),
      0.9 + rnd() * 0.55);
  }
  points.forEach(([u, v, scale], i) => {
    const [x, z] = sitePoint(frame, u, v);
    createTree(model, `structure_context_tree_${i}`, x, groundY, z, scale, treeGeometryId);
  });
}

function insideRect(rect: SiteRect, u: number, v: number, pad = 0) {
  return u > rect[0] - pad && u < rect[2] + pad && v > rect[1] - pad && v < rect[3] + pad;
}

function createCar(model: any, frame: SiteFrame, id: string, u: number, v: number, y: number, color: [number, number, number]) {
  createOrientedBox(model, `${id}_body`, [u - 1.7, v - 0.78, u + 1.7, v + 0.78], y, y + 0.58, color, 0.96, 0.55, frame);
  createOrientedBox(model, `${id}_roof`, [u - 0.82, v - 0.55, u + 0.82, v + 0.55], y + 0.58, y + 1.02, [0.12, 0.16, 0.18], 0.72, 0.35, frame);
}

function createBench(model: any, frame: SiteFrame, id: string, u: number, v: number, groundY: number) {
  createOrientedBox(model, `${id}_seat`, [u - 1.4, v - 0.22, u + 1.4, v + 0.22], groundY + 0.42, groundY + 0.56, [0.38, 0.25, 0.16], 1, 0.7, frame);
  createOrientedBox(model, `${id}_back`, [u - 1.4, v + 0.24, u + 1.4, v + 0.34], groundY + 0.6, groundY + 1.15, [0.34, 0.23, 0.15], 1, 0.7, frame);
}

function createLampPost(model: any, frame: SiteFrame, id: string, u: number, v: number, groundY: number) {
  const [x, z] = sitePoint(frame, u, v);
  createBox(model, `${id}_pole`, [x - 0.07, groundY, z - 0.07], [x + 0.07, groundY + 3.1, z + 0.07], [0.16, 0.16, 0.15], 1, 0.45);
  createBox(model, `${id}_head`, [x - 0.32, groundY + 3.0, z - 0.18], [x + 0.32, groundY + 3.22, z + 0.18], [0.95, 0.85, 0.55], 0.72, 0.35);
}

function createRingSlab(
  model: any,
  id: string,
  outer: [number, number, number, number],
  inner: [number, number, number, number],
  y0: number,
  y1: number,
  color: [number, number, number],
  opacity = 1,
) {
  const [ox0, oz0, ox1, oz1] = outer;
  const [ix0, iz0, ix1, iz1] = inner;
  createBox(model, `${id}_north`, [ox0, y0, oz0], [ox1, y1, iz0], color, opacity, 0.9);
  createBox(model, `${id}_south`, [ox0, y0, iz1], [ox1, y1, oz1], color, opacity, 0.9);
  createBox(model, `${id}_west`, [ox0, y0, iz0], [ix0, y1, iz1], color, opacity, 0.9);
  createBox(model, `${id}_east`, [ix1, y0, iz0], [ox1, y1, iz1], color, opacity, 0.9);
}

function createSiteTextureSets(model: any) {
  const make = (id: string, src: string) => {
    try {
      model.createTexture({ id: `${id}_texture`, src, flipY: false });
      model.createTextureSet({ id, colorTextureId: `${id}_texture` });
      return id;
    } catch {
      return undefined;
    }
  };
  return {
    grass: make("structure_site_grass", "/textures/site/grass.png"),
    asphalt: make("structure_site_asphalt", "/textures/site/asphalt.png"),
    concrete: make("structure_site_concrete", "/textures/site/concrete.png"),
  };
}

function createRingSurface(
  model: any,
  id: string,
  outer: [number, number, number, number],
  inner: [number, number, number, number],
  y: number,
  color: [number, number, number],
  textureSetId: string | undefined,
  repeatScale = 5,
) {
  const [ox0, oz0, ox1, oz1] = outer;
  const [ix0, iz0, ix1, iz1] = inner;
  createTexturedPlane(model, `${id}_north`, [ox0, oz0, ox1, iz0], y, color, textureSetId, repeatScale);
  createTexturedPlane(model, `${id}_south`, [ox0, iz1, ox1, oz1], y, color, textureSetId, repeatScale);
  createTexturedPlane(model, `${id}_west`, [ox0, iz0, ix0, iz1], y, color, textureSetId, repeatScale);
  createTexturedPlane(model, `${id}_east`, [ix1, iz0, ox1, iz1], y, color, textureSetId, repeatScale);
}

function createTexturedPlane(
  model: any,
  id: string,
  rect: [number, number, number, number],
  y: number,
  color: [number, number, number],
  textureSetId?: string,
  repeatScale = 5,
) {
  const [x0, z0, x1, z1] = rect;
  const width = Math.max(1, Math.abs(x1 - x0));
  const depth = Math.max(1, Math.abs(z1 - z0));
  const repeatX = Math.max(1, width / repeatScale);
  const repeatZ = Math.max(1, depth / repeatScale);
  const positions = [x0, y, z0, x1, y, z0, x1, y, z1, x0, y, z1];
  const normals = [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0];
  const uv = [0, 0, repeatX, 0, repeatX, repeatZ, 0, repeatZ];
  // Winding is intentionally counter-clockwise when viewed from +Y. The
  // previous order pointed normals downward, so the site planes disappeared
  // from the default top/isometric camera on WebGL backface culling.
  const indices = [0, 2, 1, 0, 3, 2];
  const meshId = `${id}_mesh`;
  model.createMesh({
    id: meshId,
    primitive: "triangles",
    positions,
    normals,
    uv,
    indices,
    color,
    textureSetId,
    opacity: 1,
    metallic: 0,
    roughness: 0.88,
  } as any);
  model.createEntity({ id, meshIds: [meshId], isObject: false, pickable: false });
}

function createContextTexturePatches(
  model: any,
  outer: [number, number, number, number],
  hole: [number, number, number, number],
  y: number,
) {
  const [ox0, oz0, ox1, oz1] = outer;
  const [hx0, hz0, hx1, hz1] = hole;
  for (let i = 0; i < 28; i++) {
    const rnd = seededRandom(`context_patch_${i}`);
    let x = ox0 + rnd() * (ox1 - ox0);
    let z = oz0 + rnd() * (oz1 - oz0);
    if (x > hx0 && x < hx1 && z > hz0 && z < hz1) {
      x = x < (hx0 + hx1) / 2 ? hx0 - 4 - rnd() * 10 : hx1 + 4 + rnd() * 10;
    }
    const sx = 2.5 + rnd() * 6;
    const sz = 1.5 + rnd() * 5;
    const green = 0.32 + rnd() * 0.08;
    createTexturedPlane(model, `structure_context_grass_patch_${i}`, [x - sx, z - sz, x + sx, z + sz], y + i * 0.0004,
      [0.22, green, 0.2], undefined, 3);
  }
}

function createTree(model: any, id: string, x: number, groundY: number, z: number, scale: number, treeGeometryId?: string | null) {
  const trunk = 0.22 * scale;
  const h = 1.8 * scale;
  createBox(model, `${id}_trunk`, [x - trunk, groundY, z - trunk],
    [x + trunk, groundY + h, z + trunk], [0.34, 0.22, 0.13], 1, 0.72);
  const colors: [number, number, number][] = [
    [0.13, 0.34, 0.17],
    [0.18, 0.45, 0.22],
    [0.1, 0.29, 0.15],
  ];
  const canopy = 1.35 * scale;
  if (treeGeometryId) {
    const blobs = [
      [0, h * 1.24, 0, canopy * 1.0, colors[0], 0.9],
      [-canopy * 0.42, h * 1.08, canopy * 0.22, canopy * 0.78, colors[1], 0.82],
      [canopy * 0.45, h * 1.16, -canopy * 0.16, canopy * 0.72, colors[2], 0.82],
    ] as Array<[number, number, number, number, [number, number, number], number]>;
    blobs.forEach(([ox, oy, oz, radius, color, opacity], i) => {
      const meshId = `${id}_leaf_${i}`;
      model.createMesh({
        id: meshId,
        geometryId: treeGeometryId,
        position: [x + ox, groundY + oy, z + oz],
        scale: [radius, radius * 0.74, radius],
        color,
        opacity,
        metallic: 0,
        roughness: 0.96,
      } as any);
      model.createEntity({ id: meshId, meshIds: [meshId], isObject: false, pickable: false });
    });
    return;
  }
  createBox(model, `${id}_canopy_a`, [x - canopy, groundY + h * 0.72, z - canopy],
    [x + canopy, groundY + h * 1.5, z + canopy], colors[0], 0.88, 0.95);
  createBox(model, `${id}_canopy_b`, [x - canopy * 0.75, groundY + h * 1.05, z - canopy * 1.18],
    [x + canopy * 0.75, groundY + h * 1.75, z + canopy * 0.36], colors[1], 0.82, 0.95);
  createBox(model, `${id}_canopy_c`, [x - canopy * 0.44, groundY + h * 1.35, z - canopy * 0.62],
    [x + canopy * 1.0, groundY + h * 1.92, z + canopy * 0.9], colors[2], 0.78, 0.95);
}

function createBox(
  model: any,
  id: string,
  min: [number, number, number],
  max: [number, number, number],
  color: [number, number, number],
  opacity = 1,
  roughness = 0.84,
) {
  const [x0, y0, z0] = min;
  const [x1, y1, z1] = max;
  const positions = [
    x0, y0, z0, x1, y0, z0, x1, y1, z0, x0, y1, z0,
    x0, y0, z1, x1, y0, z1, x1, y1, z1, x0, y1, z1,
  ];
  const indices = [
    0, 1, 2, 0, 2, 3,
    4, 6, 5, 4, 7, 6,
    0, 4, 5, 0, 5, 1,
    3, 2, 6, 3, 6, 7,
    1, 5, 6, 1, 6, 2,
    0, 3, 7, 0, 7, 4,
  ];
  const meshId = `${id}_mesh`;
  model.createMesh({ id: meshId, primitive: "triangles", positions, indices, color, opacity, metallic: 0, roughness } as any);
  model.createEntity({ id, meshIds: [meshId], isObject: false, pickable: false });
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
