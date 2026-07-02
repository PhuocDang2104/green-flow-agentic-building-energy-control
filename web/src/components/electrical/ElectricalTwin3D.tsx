"use client";

/**
 * 3D digital-twin of the electrical distribution (IFC metres, three.js y-up) —
 * LIGHT MODE (white scene).
 *  - distribution boards: boxes sized by peak demand, coloured by overload/feeder,
 *  - thermal zones: REAL ARCH bounding boxes (light, semi-transparent),
 *  - board -> zone supply links terminating exactly at the zone box centre,
 *  - load points: a faint see-through 3D fixture box + a bright centre dot.
 *
 * Filters (floors / zone types / load kinds) come from the page. Clicking a board
 * isolates that board: only its links, its served zones and its loads are shown.
 */

import { useEffect, useLayoutEffect, useMemo, useRef, type RefObject } from "react";
import { Canvas, ThreeEvent, useThree } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import * as THREE from "three";

export type ColorMode = "status" | "feeder" | "load";

const STATUS_COLORS: Record<string, string> = {
  normal: "#16a34a", warning: "#d97706", overload: "#dc2626",
  rating_missing: "#64748b", unmapped: "#475569",
};
const PALETTE = [
  "#0d9488", "#2563eb", "#db2777", "#ca8a04", "#7c3aed", "#ea580c",
  "#059669", "#dc2626", "#0284c7", "#9333ea", "#15803d", "#b45309",
  "#0891b2", "#c026d3", "#4d7c0f", "#e11d48", "#1d4ed8", "#c2410c",
];
const HEAT = ["#1e3a8a", "#0ea5e9", "#22c55e", "#eab308", "#f97316", "#ef4444"];
// saturated dot colours that read on a white background
const LOAD_DOT: Record<string, string> = {
  lighting: "#f59e0b", plug: "#0284c7", alarm: "#e11d48",
};

const feederColor = (i: number) => (i < 0 ? "#94a3b8" : PALETTE[i % PALETTE.length]);
function heatColor(t: number) {
  const x = Math.max(0, Math.min(1, t)) * (HEAT.length - 1);
  const i = Math.floor(x);
  const c = new THREE.Color(HEAT[i]);
  if (i < HEAT.length - 1) c.lerp(new THREE.Color(HEAT[i + 1]), x - i);
  return c;
}
const WHITE = new THREE.Color("#ffffff");
const ZONE_SHELL = new THREE.Color("#ffffff");   // translucent white shell (was grey — too dark)
const ZONE_EDGE = "#22c55e";                     // green bounding box (like the dashboard)
function zoneFillColor(z: any, mode: ColorMode) {
  // frosted-white shell in status/feeder; tinted by load heat (lightened) in load mode
  if (mode === "load") return heatColor(z.intensity ?? 0).lerp(WHITE, 0.35);
  return ZONE_SHELL;
}

/** 12 edges of every zone box merged into one green LineSegments geometry. */
function buildZoneEdges(zones: any[]): THREE.BufferGeometry {
  const EP = [[0, 1], [1, 3], [3, 2], [2, 0], [4, 5], [5, 7], [7, 6], [6, 4],
              [0, 4], [1, 5], [2, 6], [3, 7]];
  const pos = new Float32Array(zones.length * EP.length * 2 * 3);
  let o = 0;
  for (const z of zones) {
    const [sx, sy, sz] = z.size ?? [3.5, 3, 3.5];
    const hx = Math.max(sx, 0.6) / 2, hy = Math.max(sy, 0.6) / 2, hz = Math.max(sz, 0.6) / 2;
    const [cx, cy, cz] = z.pos;
    const corner = (i: number) => [cx + ((i & 1) ? hx : -hx),
      cy + ((i & 2) ? hy : -hy), cz + ((i & 4) ? hz : -hz)];
    for (const [a, b] of EP) {
      const ca = corner(a), cb = corner(b);
      pos[o++] = ca[0]; pos[o++] = ca[1]; pos[o++] = ca[2];
      pos[o++] = cb[0]; pos[o++] = cb[1]; pos[o++] = cb[2];
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  return g;
}

/* ---------------- floors ---------------- */
function Floors({ floors, radius }: { floors: any[]; radius: number }) {
  return (
    <group>
      {floors.map((f: any) => (
        <group key={f.floor_id} position={[0, f.y, 0]}>
          <mesh rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[radius * 1.8, radius * 1.8]} />
            <meshStandardMaterial color="#e8eef6" transparent opacity={0.035}
              side={THREE.DoubleSide} depthWrite={false} />
          </mesh>
          <gridHelper args={[radius * 1.8, 24, "#dbe3ee", "#eef2f8"]}
            material-transparent material-opacity={0.14} />
        </group>
      ))}
    </group>
  );
}

/* --------- architecture ghost: faded envelope of every zone box ---------- */
/* Mirrors how the dashboard x-rays the architecture under ELEC/HVAC: all zone
 * boxes drawn as a faint frosted shell so the building reads even when no zone
 * type is selected. Not pickable, ignores the zone-type filter. */
function ArchitectureGhost({ zones }: { zones: any[] }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion();
    const s = new THREE.Vector3(), p = new THREE.Vector3();
    zones.forEach((z, i) => {
      const [sx, sy, sz] = z.size ?? [3.5, 3, 3.5];
      p.set(z.pos[0], z.pos[1], z.pos[2]);
      s.set(Math.max(sx, 0.6), Math.max(sy, 0.6), Math.max(sz, 0.6));
      m.compose(p, q, s);
      mesh.setMatrixAt(i, m);
    });
    mesh.instanceMatrix.needsUpdate = true;
  }, [zones]);
  const edges = useMemo(() => buildZoneEdges(zones), [zones]);
  return (
    <group>
      <instancedMesh key={zones.length}
        args={[undefined as any, undefined as any, Math.max(zones.length, 1)]} ref={ref}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color="#dbe4f0" transparent opacity={0.05}
          side={THREE.DoubleSide} depthWrite={false} />
      </instancedMesh>
      <lineSegments key={"ag" + zones.length} geometry={edges}>
        <lineBasicMaterial color="#9fb1c6" transparent opacity={0.12} />
      </lineSegments>
    </group>
  );
}

/* ---------------- zones (instanced REAL bounding boxes) ---------------- */
function Zones({ zones, mode, onPick }: { zones: any[]; mode: ColorMode; onPick: (e: any) => void }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion();
    const s = new THREE.Vector3(), p = new THREE.Vector3();
    zones.forEach((z, i) => {
      const [sx, sy, sz] = z.size ?? [3.5, 3, 3.5];
      p.set(z.pos[0], z.pos[1], z.pos[2]);
      s.set(Math.max(sx, 0.6), Math.max(sy, 0.6), Math.max(sz, 0.6));
      m.compose(p, q, s);
      mesh.setMatrixAt(i, m);
      mesh.setColorAt(i, zoneFillColor(z, mode));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [zones, mode]);

  const edges = useMemo(() => buildZoneEdges(zones), [zones]);

  return (
    <group>
      {/* light-grey see-through shell */}
      <instancedMesh key={zones.length} ref={ref}
        args={[undefined as any, undefined as any, Math.max(zones.length, 1)]}
        onPointerDown={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          const z = zones[e.instanceId ?? -1];
          if (z) onPick({ type: "zone", ...z });
        }}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial vertexColors transparent opacity={mode === "load" ? 0.32 : 0.2}
          side={THREE.DoubleSide} depthWrite={false} polygonOffset polygonOffsetFactor={1} />
      </instancedMesh>
      {/* green bounding-box edges (like the dashboard digital twin) */}
      <lineSegments key={"ze" + zones.length} geometry={edges}>
        <lineBasicMaterial color={ZONE_EDGE} transparent opacity={0.55} />
      </lineSegments>
    </group>
  );
}

/* ---------------- boards ---------------- */
function Boards({ boards, mode, onPick, selectedId, dim }: {
  boards: any[]; mode: ColorMode; onPick: (e: any) => void; selectedId?: string | null; dim?: boolean;
}) {
  return (
    <group>
      {boards.map((b: any) => {
        const color = mode === "feeder" ? feederColor(b._idx ?? -1)
          : STATUS_COLORS[b.overload_status] ?? "#64748b";
        const h = 0.7 + (b.intensity ?? 0) * 3.4;
        const sel = selectedId === b.id;
        const faded = dim && !sel;
        return (
          <group key={b.id} position={[b.pos[0], b.pos[1] + h / 2, b.pos[2]]}>
            <mesh onPointerDown={(e: ThreeEvent<PointerEvent>) => { e.stopPropagation(); onPick({ type: "board", ...b }); }}>
              <boxGeometry args={[1.1, h, 1.1]} />
              <meshStandardMaterial color={color} emissive={color}
                emissiveIntensity={sel ? 0.5 : 0.12} roughness={0.5} metalness={0.25}
                transparent opacity={faded ? 0.25 : 1} />
            </mesh>
            {sel && (
              <mesh><boxGeometry args={[1.5, h + 0.4, 1.5]} />
                <meshBasicMaterial color={color} wireframe transparent opacity={0.8} /></mesh>
            )}
            {!faded && (
              <Html center distanceFactor={42} position={[0, h / 2 + 1.2, 0]}>
                <div className="pointer-events-none select-none whitespace-nowrap rounded bg-slate-800/90 px-1.5 py-0.5 text-[10px] font-semibold text-white shadow">
                  {b.tag}
                </div>
              </Html>
            )}
          </group>
        );
      })}
    </group>
  );
}

/* ---------------- supply links (board -> zone box centre) ---------------- */
function SupplyLinks({ links, mode }: { links: any[]; mode: ColorMode }) {
  const geom = useMemo(() => {
    const pos = new Float32Array(links.length * 6);
    const col = new Float32Array(links.length * 6);
    links.forEach((l, i) => {
      pos.set([l.from[0], l.from[1], l.from[2], l.to[0], l.to[1], l.to[2]], i * 6);
      // Load-heat mode: paint each supply line with the colour of the load it
      // feeds (lighting / plug / alarm), so the line reads back to its fixture;
      // feeder mode keeps the per-board colour.
      const c = new THREE.Color(mode === "load"
        ? (LOAD_DOT[l.kind as string] ?? "#0284c7")
        : feederColor(l.color_idx ?? -1));
      col.set([c.r, c.g, c.b, c.r, c.g, c.b], i * 6);
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    return g;
  }, [links, mode]);
  return (
    <lineSegments key={links.length} geometry={geom}>
      <lineBasicMaterial vertexColors transparent opacity={0.6} />
    </lineSegments>
  );
}

/* ---------------- load points: faint fixture box + bright centre dot ---------------- */
function LoadPoints({ loads }: { loads: any[] }) {
  const dots = useMemo(() => {
    const pos = new Float32Array(loads.length * 3);
    const col = new Float32Array(loads.length * 3);
    loads.forEach((l, i) => {
      pos.set(l.pos, i * 3);
      const c = new THREE.Color(LOAD_DOT[l.kind] ?? "#475569");
      col.set([c.r, c.g, c.b], i * 3);
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    return g;
  }, [loads]);

  const meshRef = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion();
    const s = new THREE.Vector3(0.5, 0.5, 0.5), p = new THREE.Vector3();
    loads.forEach((l, i) => {
      p.set(l.pos[0], l.pos[1], l.pos[2]);
      m.compose(p, q, s);
      mesh.setMatrixAt(i, m);
      mesh.setColorAt(i, new THREE.Color(LOAD_DOT[l.kind] ?? "#94a3b8"));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [loads]);

  return (
    <group>
      {/* faint see-through fixture geometry (like the main ELE layer, dimmer) */}
      <instancedMesh key={"m" + loads.length} ref={meshRef}
        args={[undefined as any, undefined as any, Math.max(loads.length, 1)]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial vertexColors transparent opacity={0.18}
          roughness={0.5} metalness={0.05} depthWrite={false} side={THREE.DoubleSide} />
      </instancedMesh>
      {/* bright centre dot marking each load */}
      <points key={"p" + loads.length} geometry={dots}>
        <pointsMaterial size={0.7} sizeAttenuation vertexColors transparent
          opacity={1} depthWrite={false} />
      </points>
    </group>
  );
}

function CameraDirector({
  boards,
  focusBoard,
  radius,
  height,
  controlsRef,
}: {
  boards: any[];
  focusBoard?: string | null;
  radius: number;
  height: number;
  controlsRef: RefObject<any>;
}) {
  const camera = useThree((state) => state.camera);

  useEffect(() => {
    const board = focusBoard ? boards.find((b: any) => b.id === focusBoard) : null;
    const target = board
      ? new THREE.Vector3(board.pos[0], board.pos[1] + 2.2, board.pos[2])
      : new THREE.Vector3(0, height / 2, 0);
    const distance = board ? Math.max(12, radius * 0.42) : radius * 1.7;
    const desired = board
      ? new THREE.Vector3(
        target.x + distance * 0.85,
        target.y + distance * 0.58,
        target.z + distance * 0.72,
      )
      : new THREE.Vector3(distance, distance * 0.8, distance);
    const startPosition = camera.position.clone();
    const startTarget = controlsRef.current?.target?.clone?.() ?? new THREE.Vector3(0, height / 2, 0);
    const start = performance.now();
    const duration = board ? 950 : 720;
    let frame = 0;

    const ease = (t: number) => 1 - Math.pow(1 - t, 3);
    const animate = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const k = ease(t);
      camera.position.lerpVectors(startPosition, desired, k);
      const nextTarget = startTarget.clone().lerp(target, k);
      if (controlsRef.current?.target) {
        controlsRef.current.target.copy(nextTarget);
        controlsRef.current.update?.();
      } else {
        camera.lookAt(nextTarget);
      }
      if (t < 1) frame = requestAnimationFrame(animate);
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [boards, camera, controlsRef, focusBoard, height, radius]);

  return null;
}

export default function ElectricalTwin3D({
  scene, colorMode = "status", show, floors, zoneTypes, loadKinds,
  selectedId, onSelect, focusBoard, className, autoRotate = false,
}: {
  scene: any;
  colorMode?: ColorMode;
  show?: { boards?: boolean; links?: boolean; floors?: boolean };
  floors?: Set<string> | null;
  zoneTypes?: Set<string> | null;
  loadKinds?: Set<string> | null;
  selectedId?: string | null;
  onSelect?: (e: any | null) => void;
  focusBoard?: string | null;   // when set: isolate this board's links/zones/loads
  className?: string;
  autoRotate?: boolean;         // gentle orbit for the tutorial showcase
}) {
  const vis = { boards: true, links: true, floors: true, ...show };
  const controlsRef = useRef<any>(null);

  const prepped = useMemo(() => {
    if (!scene) return null;
    scene.boards.forEach((b: any, i: number) => (b._idx = i));
    return scene;
  }, [scene]);

  // null prop = no filter (show all); an (even empty) Set = show only its members,
  // so ticking "None" genuinely hides everything.
  const okFloor = useMemo(() =>
    (fid?: string) => floors == null ? true : floors.has(fid ?? ""), [floors]);
  const okZoneType = useMemo(() =>
    (rt?: string) => zoneTypes == null ? true : zoneTypes.has(rt || "unknown"), [zoneTypes]);

  const boardFloor = useMemo(() => {
    const m: Record<string, string> = {};
    prepped?.boards.forEach((b: any) => (m[b.id] = b.floor_id));
    return m;
  }, [prepped]);
  const zoneFloor = useMemo(() => {
    const m: Record<string, string> = {};
    prepped?.zones.forEach((z: any) => (m[z.id] = z.floor_id));
    return m;
  }, [prepped]);
  // load kind keyed by its (rounded) position, so a supply line can recover the
  // kind of the fixture it terminates on even if the backend omits link.kind.
  const loadKindByPos = useMemo(() => {
    const m: Record<string, string> = {};
    prepped?.loads.forEach((l: any) => { m[(l.pos as number[]).join(",")] = l.kind; });
    return m;
  }, [prepped]);

  const vBoards = useMemo(() => prepped ? prepped.boards.filter((b: any) => okFloor(b.floor_id)) : [], [prepped, okFloor]);
  const vZones = useMemo(() => prepped ? prepped.zones.filter((z: any) =>
    okFloor(z.floor_id) && okZoneType(z.room_type) && (!focusBoard || z.feeder_board === focusBoard)) : [],
    [prepped, okFloor, okZoneType, focusBoard]);
  // Faded architecture envelope — every zone on the visible floors, independent
  // of the zone-type filter (which starts empty) and of board focus.
  const ghostZones = useMemo(() => prepped
    ? prepped.zones.filter((z: any) => okFloor(z.floor_id) && (!focusBoard || z.feeder_board === focusBoard))
    : [], [prepped, okFloor, focusBoard]);
  const vLoads = useMemo(() => {
    if (!prepped || !loadKinds || loadKinds.size === 0) return [];
    return prepped.loads.filter((l: any) => loadKinds.has(l.kind) && okFloor(l.floor_id)
      && (!focusBoard || l.board_id === focusBoard));
  }, [prepped, loadKinds, okFloor, focusBoard]);
  const vLinks = useMemo(() => prepped ? prepped.supply_links.filter((l: any) =>
    okFloor(boardFloor[l.board_id]) && okFloor(zoneFloor[l.zone_id])
    && (!focusBoard || l.board_id === focusBoard))
    .map((l: any) => ({ ...l, kind: l.kind ?? loadKindByPos[(l.to as number[]).join(",")] })) : [],
    [prepped, okFloor, boardFloor, zoneFloor, focusBoard, loadKindByPos]);
  const vFloors = useMemo(() => prepped ? prepped.floors.filter((f: any) => okFloor(f.floor_id)) : [], [prepped, okFloor]);

  if (!prepped) return null;
  const r = prepped.bounds?.radius ?? 40;
  const cam = r * 1.7;

  return (
    <div className={className ?? "h-full w-full"}>
      <Canvas dpr={[1, 2]} gl={{ antialias: true, powerPreference: "high-performance" }}
        camera={{ position: [cam, cam * 0.8, cam], fov: 40, near: 0.5, far: cam * 12 }}
        onPointerMissed={() => onSelect?.(null)}>
        <color attach="background" args={["#ffffff"]} />
        <fog attach="fog" args={["#ffffff", cam * 2.2, cam * 7]} />
        <hemisphereLight args={["#ffffff", "#c7d2e0", 1.1]} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[cam, cam * 1.5, cam * 0.6]} intensity={1.1} color="#ffffff" />

        {vis.floors && <Floors floors={vFloors} radius={r} />}
        {ghostZones.length > 0 && <ArchitectureGhost zones={ghostZones} />}
        {vZones.length > 0 && <Zones zones={vZones} mode={colorMode} onPick={(e) => onSelect?.(e)} />}
        {vis.links && vLinks.length > 0 && <SupplyLinks links={vLinks} mode={colorMode} />}
        {vLoads.length > 0 && <LoadPoints loads={vLoads} />}
        {vis.boards && <Boards boards={vBoards} mode={colorMode} selectedId={selectedId}
          dim={!!focusBoard} onPick={(e) => onSelect?.(e)} />}
        <CameraDirector
          boards={prepped.boards}
          focusBoard={focusBoard}
          radius={r}
          height={prepped.bounds?.height ?? 16}
          controlsRef={controlsRef}
        />

        <OrbitControls ref={controlsRef} makeDefault enableDamping dampingFactor={0.08}
          autoRotate={autoRotate} autoRotateSpeed={0.55}
          maxPolarAngle={Math.PI / 2.05} minDistance={r * 0.4} maxDistance={cam * 5}
          target={[0, prepped.bounds?.height ? prepped.bounds.height / 2 : 8, 0]} />
      </Canvas>
    </div>
  );
}
