"use client";

// Latitude/longitude wireframe wrapping the globe. Faint in light mode, glowing
// cyan in dark mode (energy-network feel).

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

export default function EarthGrid({ themeMix }: { themeMix: number }) {
  const matRef = useRef<THREE.LineBasicMaterial>(null);
  const geom = useMemo(() => {
    const g = new THREE.EdgesGeometry(new THREE.SphereGeometry(1.012, 24, 16));
    return g;
  }, []);
  const day = useMemo(() => new THREE.Color("#cfeede"), []);
  const dark = useMemo(() => new THREE.Color("#27e6c2"), []);
  const ref = useRef<THREE.LineSegments>(null);

  useFrame((_, delta) => {
    // spin in lock-step with the Earth surface
    if (ref.current) ref.current.rotation.y += Math.min(delta, 0.05) * 0.045;
    if (matRef.current) {
      (matRef.current.color as THREE.Color).copy(day).lerp(dark, themeMix);
      // near-invisible in light mode (clean planet), glowing grid in dark mode
      matRef.current.opacity = 0.03 + themeMix * 0.5;
    }
  });

  return (
    <lineSegments ref={ref} geometry={geom}>
      <lineBasicMaterial ref={matRef} transparent opacity={0.15} />
    </lineSegments>
  );
}
