"use client";

/**
 * Section-2 hero: the digital-twin building (architecture.glb) rising out of the
 * ground. The IFC-derived GLB is Z-up, so it is rotated to Y-up, recentred with
 * its base on the floor, fitted to a target height, and re-skinned in a clean
 * teal massing material. On mount it grows upward (scale.y 0 -> 1) and turns
 * slowly. Canvas is transparent so the pie/bar charts behind it show through.
 */

import { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";

const GLB = "/assets/buildings/greenflow_archetype/glb/architecture.glb";

function Building({ themeMix }: { themeMix: number }) {
  const { scene } = useGLTF(GLB);
  const grow = useRef<THREE.Group>(null);
  const growVal = useRef(0.0001);

  const skin = useMemo(
    () => new THREE.MeshStandardMaterial({
      color: "#4ea8bd", roughness: 0.38, metalness: 0.28,
      emissive: "#0c3f4a", emissiveIntensity: 0.25,
    }),
    [],
  );

  // clone, recentre base on floor, fit, re-skin (GLB is already glTF Y-up)
  const model = useMemo(() => {
    const root = new THREE.Group();
    const s = scene.clone(true);
    s.updateMatrixWorld(true);
    s.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) { m.material = skin; m.castShadow = true; }
    });
    const box = new THREE.Box3().setFromObject(s);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    // fit by footprint so the wide low-rise reads at a sensible size in frame
    const footprint = Math.max(size.x, size.z) || 1;
    const scale = 2.7 / footprint;
    // base on the floor (y=0), centred in x/z
    s.position.set(-center.x, -box.min.y, -center.z);
    root.add(s);
    root.scale.setScalar(scale);
    return root;
  }, [scene, skin]);

  useFrame((_, delta) => {
    const d = Math.min(delta, 0.05);
    growVal.current += (1 - growVal.current) * Math.min(1, d * 1.5);
    if (grow.current) {
      grow.current.scale.y = growVal.current;
      grow.current.rotation.y += d * 0.18;
    }
    skin.color.setRGB(0.31, 0.66, 0.74).lerp(new THREE.Color(0.18, 0.85, 0.78), themeMix);
    skin.emissiveIntensity = 0.25 + themeMix * 0.9;
  });

  return (
    <group ref={grow} position={[0, -0.42, 0]}>
      <primitive object={model} />
    </group>
  );
}

export default function BuildingStage({ themeMix = 0 }: { themeMix?: number }) {
  return (
    <Canvas
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance",
            toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.1 }}
      camera={{ position: [3.0, 0.62, 3.0], fov: 40 }}
    >
      <ambientLight intensity={0.7} />
      <directionalLight position={[4, 6, 5]} intensity={1.8} color="#ffffff" castShadow />
      <directionalLight position={[-5, 2, -3]} intensity={0.7} color="#3fe0c8" />
      <pointLight position={[0, -2, 3]} intensity={0.4} color="#2ec5d6" />
      <Suspense fallback={null}>
        <Building themeMix={themeMix} />
      </Suspense>
    </Canvas>
  );
}

useGLTF.preload(GLB);
