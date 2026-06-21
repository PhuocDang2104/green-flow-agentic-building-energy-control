"use client";

// Latitude/longitude wireframe wrapping the globe. Hidden in light mode, glowing
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
  const dark = useMemo(() => new THREE.Color("#27e6c2"), []);
  const ref = useRef<THREE.LineSegments>(null);

  useFrame((_, delta) => {
    // spin in lock-step with the Earth surface
    if (ref.current) ref.current.rotation.y += Math.min(delta, 0.05) * 0.045;
    if (matRef.current) {
      (matRef.current.color as THREE.Color).copy(dark);
      matRef.current.opacity = themeMix * 0.54;
    }
  });

  return (
    <lineSegments ref={ref} geometry={geom}>
      <lineBasicMaterial ref={matRef} transparent opacity={0} />
    </lineSegments>
  );
}
