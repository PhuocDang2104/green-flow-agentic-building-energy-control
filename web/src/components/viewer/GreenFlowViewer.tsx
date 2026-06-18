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
import { MANIFEST_URL } from "@/lib/constants";
import type { ObjectMapEntry, ViewerManifest } from "@/lib/types";
import { useAppStore } from "@/stores/appStore";
import LayerPanel from "./LayerPanel";
import ViewModeToolbar from "./ViewModeToolbar";
import MetricLegend from "./MetricLegend";
import EntityTooltip from "./EntityTooltip";

type XeokitViewer = any;

const ZONE_BASE_COLOR: [number, number, number] = [0.06, 0.46, 0.43];

export default function GreenFlowViewer({ heightClass = "h-[560px]" }: { heightClass?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const viewerRef = useRef<XeokitViewer | null>(null);
  const modelsRef = useRef<Record<string, any>>({});
  const objectMapRef = useRef<Record<string, ObjectMapEntry>>({});
  const xeokitRef = useRef<{ SceneModel: any; buildSphereGeometry: any } | null>(null);
  const occupancyModelRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  const layers = useAppStore((s) => s.layers);
  const activeMetric = useAppStore((s) => s.activeMetric);
  const zoneStates = useAppStore((s) => s.zoneStates);
  const selectedEntityKey = useAppStore((s) => s.selectedEntityKey);
  const viewerUpdates = useAppStore((s) => s.viewerUpdates);
  const selectEntity = useAppStore((s) => s.selectEntity);
  const setLayers = useAppStore((s) => s.setLayers);

  // --- init viewer once ---------------------------------------------------
  useEffect(() => {
    let disposed = false;

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
        // framed precisely by cameraFlight once the first model loads
        viewer.camera.eye = [60, 45, 60];
        viewer.camera.look = [0, 0, 0];
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
            } as any);
            (model as any).visible = asset.default_visible;
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
                viewer.cameraFlight.flyTo({
                  aabb: viewer.scene.getAABB(viewer.scene.visibleObjectIds),
                  duration: 0.8,
                });
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

        viewer.cameraControl.on("picked", (e: any) => {
          const id = e.entity?.id as string | undefined;
          if (!id) return;
          const entry = objectMapRef.current[id];
          // surfaces/windows resolve to their zone for inspection
          const key = entry?.entity_type === "ThermalZone"
            ? entry.entity_key
            : entry?.zone_key || entry?.entity_key || id;
          selectEntity(key);
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
      occupancyModelRef.current = null;
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
      if (entity && entry.layer === "spaces") styleSpace(entity, entry);
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
      if (model) model.visible = layers[layer] !== false;
    }
    // X-ray architecture when a discipline (MEP/structural) or a zone heatmap
    // is active, so what's inside reads clearly (3D doc §7.1).
    const discipline = layers.hvac || layers.electrical || layers.structural;
    const archModel = modelsRef.current["architecture"];
    if (archModel) {
      archModel.xrayed = !!discipline || activeMetric !== "none";
    }
    viewer.scene.xrayMaterial.fillAlpha = 0.06;
    viewer.scene.xrayMaterial.edgeAlpha = 0.22;
  }, [layers, ready, activeMetric]);

  // --- heatmap overlay from live zone state --------------------------------
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;
    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      if (entry.layer !== "spaces") continue;
      const entity = viewer.scene.objects[id];
      if (!entity) continue;
      const st = zoneStates[entry.entity_key];
      const styled = applyMetricColor(entity, st, activeMetric);
      if (!styled) styleSpace(entity, entry);
    }
  }, [zoneStates, activeMetric, ready]);

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
    if (viewer) viewer.cameraFlight.flyTo({ aabb: viewer.scene.getAABB(viewer.scene.visibleObjectIds), duration: 0.6 });
  };

  return (
    <div className={`relative w-full overflow-hidden rounded-card border border-border bg-gradient-to-b from-slate-50 to-white ${heightClass}`}>
      <canvas ref={canvasRef} className="viewer-canvas" />
      {!ready && !error && (
        <div className="absolute inset-0 grid place-items-center text-sm text-text-muted">
          Loading digital twin…
        </div>
      )}
      {error && (
        <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-danger">
          3D viewer failed to load: {error}
        </div>
      )}
      <LayerPanel />
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
