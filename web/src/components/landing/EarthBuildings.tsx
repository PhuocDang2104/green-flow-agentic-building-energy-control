"use client";

// Tiny stylised "smart-city" markers scattered on the globe — small extruded
// boxes pointing outward, sharing one material that brightens in dark mode.

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const COUNT = 110;

export default function EarthBuildings({ themeMix }: { themeMix: number }) {
  const groupRef = useRef<THREE.Group>(null);

  const material = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#0f7a43", roughness: 0.5 }),
    [],
  );
  const day = useMemo(() => new THREE.Color("#0f7a43"), []);
  const dark = useMemo(() => new THREE.Color("#6cf2b0"), []);

  const instances = useMemo(() => {
    const arr: { pos: THREE.Vector3; quat: THREE.Quaternion; h: number }[] = [];
    const up = new THREE.Vector3(0, 1, 0);
    let seed = 7;
    const rand = () => ((seed = (seed * 9301 + 49297) % 233280), seed / 233280);
    for (let i = 0; i < COUNT; i++) {
      const y = 1 - (i / (COUNT - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const phi = i * 2.399963;
      const dir = new THREE.Vector3(Math.cos(phi) * r, y, Math.sin(phi) * r);
      if (rand() > 0.5) continue;
      const quat = new THREE.Quaternion().setFromUnitVectors(up, dir);
      arr.push({ pos: dir.clone(), quat, h: 0.03 + rand() * 0.08 });
    }
    return arr;
  }, []);

  useFrame((_, delta) => {
    if (groupRef.current) groupRef.current.rotation.y += delta * 0.05;
    material.color.copy(day).lerp(dark, themeMix);
    material.emissive.copy(dark);
    material.emissiveIntensity = themeMix * 0.9;
  });

  return (
    <group ref={groupRef}>
      {instances.map((b, i) => (
        <mesh key={i} position={[b.pos.x, b.pos.y, b.pos.z]} quaternion={b.quat}
              material={material}>
          <boxGeometry args={[0.018, b.h, 0.018]} />
        </mesh>
      ))}
    </group>
  );
}
