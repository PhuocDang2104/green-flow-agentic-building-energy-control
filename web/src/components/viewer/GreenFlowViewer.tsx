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
        console.log("[viewer] importing xeokit-sdk…");
        const [{ Viewer, XKTLoaderPlugin, SceneModel }, manifestRes] = await Promise.all([
          import("@xeokit/xeokit-sdk"),
          fetch(MANIFEST_URL),
        ]);
        console.log("[viewer] sdk imported, manifest status", manifestRes.status);
        if (disposed || !canvasRef.current) return;
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
        viewer.camera.eye = [28, 22, 28];
        viewer.camera.look = [8, 2, -7];
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
        console.log("[viewer] init complete");
        setReady(true);
      } catch (err: any) {
        console.error("viewer init failed", err);
        setError(String(err?.message || err));
      }
    })();

    return () => {
      disposed = true;
      viewerRef.current?.destroy?.();
      viewerRef.current = null;
      modelsRef.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function styleDefaults(viewer: any) {
    // zones are translucent volumes; architecture slightly x-rayable
    for (const [id, entry] of Object.entries(objectMapRef.current)) {
      const entity = viewer.scene.objects[id];
      if (!entity) continue;
      if (entry.layer === "spaces") {
        entity.colorize = ZONE_BASE_COLOR;
        entity.opacity = 0.35;
      }
    }
    viewer.scene.highlightMaterial.fillColor = [0.06, 0.46, 0.43];
    viewer.scene.highlightMaterial.fillAlpha = 0.5;
    viewer.scene.highlightMaterial.edgeColor = [0.02, 0.3, 0.28];
  }

  // --- layer visibility ----------------------------------------------------
  useEffect(() => {
    if (!ready) return;
    for (const [layer, model] of Object.entries(modelsRef.current)) {
      if (model) model.visible = layers[layer] !== false;
    }
  }, [layers, ready]);

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
      if (!styled) {
        entity.colorize = ZONE_BASE_COLOR;
        entity.opacity = 0.35;
      }
    }
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
