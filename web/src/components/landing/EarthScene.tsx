"use client";

/**
 * Single shared Earth Canvas for the whole landing deck. The Earth group is
 * positioned/scaled per section so it feels like one continuous globe travelling
 * through the slides — big in the hero, then it spins up and drifts down-right,
 * and finally zooms toward the viewer on the way into section 2 (the building).
 * Theme (light/dark) is animated via a lerped themeMix.
 */

import { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import EarthObject from "./EarthObject";
import AtmosphereGlow from "./AtmosphereGlow";
import EarthGrid from "./EarthGrid";
import EarthBuildings from "./EarthBuildings";

// Per-section Earth keyframes (world units). Interpolated continuously by the
// scroll progress so the globe scales/drifts smoothly as you scroll the page.
const LAYOUT: { x: number; y: number; scale: number }[] = [
  { x: 0.1, y: -2.55, scale: 2.25 }, // hero: big globe rising from the bottom
  { x: 2.15, y: -0.7, scale: 1.2 },  // global energy: shifted a touch left
  { x: 0.4, y: 0.6, scale: 3.2 },    // loads: recedes/zooms as it fades out
  { x: -4.6, y: 2.4, scale: 0.8 },
  { x: -4.6, y: 2.4, scale: 0.8 },
  { x: -4.6, y: 2.4, scale: 0.8 },
  { x: 4.0, y: -2.4, scale: 1.0 },
];

const smooth = (t: number) => t * t * (3 - 2 * t);

function layoutAt(p: number) {
  const i = Math.max(0, Math.min(LAYOUT.length - 1, Math.floor(p)));
  const j = Math.min(LAYOUT.length - 1, i + 1);
  const f = smooth(Math.max(0, Math.min(1, p - i)));
  const a = LAYOUT[i], b = LAYOUT[j];
  return {
    x: a.x + (b.x - a.x) * f,
    y: a.y + (b.y - a.y) * f,
    scale: a.scale + (b.scale - a.scale) * f,
  };
}

function Rig({ progress, themeMix, reduced }: {
  progress: number; themeMix: number; reduced: boolean;
}) {
  const group = useRef<THREE.Group>(null);
  const target = useRef(new THREE.Vector3(0.1, -2.55, 0));
  const curScale = useRef(2.25);
  const prevProgress = useRef(progress);
  const spinBoost = useRef(0);

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    const d = Math.min(delta, 0.05);

    // spin harder the faster you scroll (scroll-velocity driven)
    const dp = progress - prevProgress.current;
    prevProgress.current = progress;
    spinBoost.current += Math.abs(dp) * 7;
    spinBoost.current *= 0.92;
    g.rotation.y += spinBoost.current * d;

    const l = layoutAt(progress);
    target.current.set(l.x, l.y, 0);
    const k = reduced ? 1 : Math.min(1, d * 6);
    g.position.lerp(target.current, k);
    curScale.current += (l.scale - curScale.current) * k;
    g.scale.setScalar(curScale.current);
    g.rotation.z = THREE.MathUtils.lerp(g.rotation.z, -0.18, 0.02);
  });

  return (
    <group ref={group} position={[0.1, -2.55, 0]}>
      <EarthObject themeMix={themeMix} />
      <AtmosphereGlow themeMix={themeMix} />
      <EarthGrid themeMix={themeMix} />
      <EarthBuildings themeMix={themeMix} reduced={reduced} />
    </group>
  );
}

/** Sun + fill lights, dimmed in dark mode so the city lights/emissive take over. */
function LightRig({ themeMix }: { themeMix: number }) {
  const sun = useRef<THREE.DirectionalLight>(null);
  const amb = useRef<THREE.AmbientLight>(null);
  const fill = useRef<THREE.PointLight>(null);
  useFrame(() => {
    if (sun.current) sun.current.intensity = THREE.MathUtils.lerp(2.0, 0.45, themeMix);
    if (amb.current) amb.current.intensity = THREE.MathUtils.lerp(0.45, 0.14, themeMix);
    if (fill.current) fill.current.intensity = THREE.MathUtils.lerp(0.35, 0.8, themeMix);
  });
  return (
    <>
      <ambientLight ref={amb} intensity={0.45} />
      <directionalLight ref={sun} position={[5, 2.2, 4]} intensity={2.0} color="#fff5e8" />
      <pointLight ref={fill} position={[-6, -1.5, -4]} intensity={0.35} color="#1fb6d6" />
    </>
  );
}

function Particles({ themeMix, reduced }: { themeMix: number; reduced: boolean }) {
  const ref = useRef<THREE.Points>(null);
  const matRef = useRef<THREE.PointsMaterial>(null);
  const geo = useMemo(() => {
    const n = reduced ? 120 : 460;
    const pos = new Float32Array(n * 3);
    let seed = 11;
    const rand = () => ((seed = (seed * 9301 + 49297) % 233280), seed / 233280);
    for (let i = 0; i < n; i++) {
      const r = 4 + rand() * 7;
      const t = rand() * Math.PI * 2;
      const p = Math.acos(2 * rand() - 1);
      pos[i * 3] = r * Math.sin(p) * Math.cos(t);
      pos[i * 3 + 1] = r * Math.sin(p) * Math.sin(t) - 1;
      pos[i * 3 + 2] = r * Math.cos(p) - 2;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return g;
  }, [reduced]);

  const day = useMemo(() => new THREE.Color("#9ad9bd"), []);
  const dark = useMemo(() => new THREE.Color("#5ef0b0"), []);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += Math.min(delta, 0.05) * 0.012;
    if (matRef.current) {
      (matRef.current.color as THREE.Color).copy(day).lerp(dark, themeMix);
      matRef.current.opacity = 0.18 + themeMix * 0.5;
    }
  });

  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial ref={matRef} size={0.028} sizeAttenuation transparent
                      opacity={0.2} depthWrite={false} />
    </points>
  );
}

export default function EarthScene({ progress, themeMix, reduced }: {
  progress: number; themeMix: number; reduced: boolean;
}) {
  return (
    <Canvas
      dpr={[1, 2]}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
        toneMapping: THREE.ACESFilmicToneMapping,
        toneMappingExposure: 1.05,
      }}
      camera={{ position: [0, 0, 6], fov: 42 }}
    >
      <LightRig themeMix={themeMix} />
      <Suspense fallback={null}>
        <Rig progress={progress} themeMix={themeMix} reduced={reduced} />
      </Suspense>
      <Particles themeMix={themeMix} reduced={reduced} />
    </Canvas>
  );
}
