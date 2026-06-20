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

// Per-section Earth placement (world units). x/y in viewport-ish offsets, scale.
const LAYOUT: Record<number, { x: number; y: number; scale: number }> = {
  0: { x: 0.1, y: -2.55, scale: 2.25 },  // hero: big globe rising from the bottom
  1: { x: 2.7, y: -0.7, scale: 1.2 },    // global energy: spun down to the right
  2: { x: 0.4, y: 0.0, scale: 3.9 },     // loads: rushes toward viewer (zoom-in)
  3: { x: -4.6, y: 2.4, scale: 0.8 },
  4: { x: -4.6, y: 2.4, scale: 0.8 },
  5: { x: -4.6, y: 2.4, scale: 0.8 },
  6: { x: 4.0, y: -2.4, scale: 1.0 },
};

function Rig({ section, themeMix, reduced }: {
  section: number; themeMix: number; reduced: boolean;
}) {
  const group = useRef<THREE.Group>(null);
  const target = useRef(new THREE.Vector3(0.1, -2.55, 0));
  const curScale = useRef(2.25);
  const prevSection = useRef(section);
  const spinBoost = useRef(0);

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    const d = Math.min(delta, 0.05);

    // kick a strong spin whenever we move to a new section
    if (section !== prevSection.current) {
      spinBoost.current += section > prevSection.current ? 2.4 : 1.4;
      prevSection.current = section;
    }
    spinBoost.current *= 0.94;
    g.rotation.y += spinBoost.current * d;

    const l = LAYOUT[section] ?? LAYOUT[6];
    target.current.set(l.x, l.y, 0);
    // slower drift so the hero->section glide feels deliberate, not a pop
    const k = reduced ? 1 : Math.min(1, d * 1.25);
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

export default function EarthScene({ section, themeMix, reduced }: {
  section: number; themeMix: number; reduced: boolean;
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
        <Rig section={section} themeMix={themeMix} reduced={reduced} />
      </Suspense>
      <Particles themeMix={themeMix} reduced={reduced} />
    </Canvas>
  );
}
