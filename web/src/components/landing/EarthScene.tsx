"use client";

/**
 * Single shared Earth Canvas for the whole landing deck. The Earth group is
 * positioned/scaled per section so it feels like one continuous globe travelling
 * through the slides. Theme (light/dark) is animated via a lerped themeMix.
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import EarthObject from "./EarthObject";
import AtmosphereGlow from "./AtmosphereGlow";
import EarthGrid from "./EarthGrid";
import EarthBuildings from "./EarthBuildings";

// Per-section Earth placement (world units). x/y in viewport-ish offsets, scale.
const LAYOUT: Record<number, { x: number; y: number; scale: number; vis: number }> = {
  0: { x: 0.0, y: -1.5, scale: 2.5, vis: 1 },     // hero: big, lower
  1: { x: 2.4, y: 0.2, scale: 1.25, vis: 1 },     // global energy: small, right
  2: { x: 3.6, y: 1.6, scale: 1.0, vis: 0 },      // loads: pushed away
  3: { x: -4.0, y: 2.0, scale: 0.9, vis: 0 },
  4: { x: -4.5, y: 2.4, scale: 0.8, vis: 0 },
  5: { x: -4.5, y: 2.4, scale: 0.8, vis: 0 },
  6: { x: 3.8, y: -2.2, scale: 1.1, vis: 0 },     // hint return bottom-right
};

function Rig({ section, themeMix, reduced }: {
  section: number; themeMix: number; reduced: boolean;
}) {
  const group = useRef<THREE.Group>(null);
  const target = useRef(new THREE.Vector3());
  const curScale = useRef(2.5);

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    const l = LAYOUT[section] ?? LAYOUT[6];
    target.current.set(l.x, l.y, 0);
    const k = reduced ? 1 : Math.min(1, delta * 2.2);
    g.position.lerp(target.current, k);
    curScale.current += (l.scale - curScale.current) * k;
    g.scale.setScalar(curScale.current);
    // gentle idle tilt
    g.rotation.z = THREE.MathUtils.lerp(g.rotation.z, -0.12, 0.02);
  });

  return (
    <group ref={group} position={[0, -1.5, 0]}>
      <EarthObject themeMix={themeMix} />
      <AtmosphereGlow themeMix={themeMix} />
      <EarthGrid themeMix={themeMix} />
      <EarthBuildings themeMix={themeMix} />
    </group>
  );
}

function Particles({ themeMix, reduced }: { themeMix: number; reduced: boolean }) {
  const ref = useRef<THREE.Points>(null);
  const geo = useMemo(() => {
    const n = reduced ? 120 : 420;
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

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.012;
  });

  return (
    <points ref={ref} geometry={geo}>
      <pointsMaterial
        size={0.03}
        sizeAttenuation
        color={themeMix > 0.5 ? "#5ef0b0" : "#86d0b0"}
        transparent
        opacity={0.25 + themeMix * 0.45}
        depthWrite={false}
      />
    </points>
  );
}

export default function EarthScene({ section, themeMix, reduced }: {
  section: number; themeMix: number; reduced: boolean;
}) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, 6], fov: 42 }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 3, 5]} intensity={1.3} />
      <pointLight position={[-5, -2, -4]} intensity={0.6} color="#16a6c7" />
      <Rig section={section} themeMix={themeMix} reduced={reduced} />
      <Particles themeMix={themeMix} reduced={reduced} />
    </Canvas>
  );
}
