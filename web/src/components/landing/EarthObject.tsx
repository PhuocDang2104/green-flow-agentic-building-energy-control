"use client";

/**
 * Realistic textured Earth. High-res NASA Blue Marble day map (8k) + normal +
 * specular ocean mask + a separate cloud shell, plus a night-lights emissive
 * map that only ignites in dark mode. Day mode = natural, bright, cloudy planet.
 * Dark mode = the surface dims and city lights glow (the energy-grid overlay is
 * drawn by EarthBuildings). Theme is driven by the lerped `themeMix` (0..1).
 */

import { useMemo, useRef } from "react";
import { useFrame, useLoader, useThree } from "@react-three/fiber";
import * as THREE from "three";

const TEX = "/assets/landing/earth/";

export default function EarthObject({ themeMix }: { themeMix: number }) {
  const earthRef = useRef<THREE.Mesh>(null);
  const cloudRef = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshPhongMaterial>(null);
  const cloudMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const { gl } = useThree();

  const [dayMap, normalMap, specularMap, nightMap, cloudMap] = useLoader(
    THREE.TextureLoader,
    [
      `${TEX}earth_day_8k.jpg`,
      `${TEX}earth_normal_2048.jpg`,
      `${TEX}earth_specular_2048.jpg`,
      `${TEX}earth_lights_2048.png`,
      `${TEX}earth_clouds_1024.png`,
    ],
  );

  // colour space + crisp filtering (anisotropy keeps the surface sharp at grazing angles)
  useMemo(() => {
    const maxAniso = gl.capabilities.getMaxAnisotropy();
    dayMap.colorSpace = THREE.SRGBColorSpace;
    nightMap.colorSpace = THREE.SRGBColorSpace;
    cloudMap.colorSpace = THREE.SRGBColorSpace;
    // normal + specular are data, keep them linear
    for (const t of [dayMap, normalMap, specularMap, nightMap, cloudMap]) {
      t.anisotropy = maxAniso;
      t.minFilter = THREE.LinearMipmapLinearFilter;
      t.magFilter = THREE.LinearFilter;
      t.generateMipmaps = true;
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      t.needsUpdate = true;
    }
    return null;
  }, [gl, dayMap, normalMap, specularMap, nightMap, cloudMap]);

  // reusable colours for theme lerp
  const c = useMemo(
    () => ({
      dayTint: new THREE.Color(1, 1, 1),
      darkTint: new THREE.Color(0.10, 0.20, 0.17),
      daySpec: new THREE.Color(0.35, 0.45, 0.55),
      darkSpec: new THREE.Color(0.05, 0.18, 0.16),
      emissive: new THREE.Color("#7df5c0"),
      tmpTint: new THREE.Color(),
      tmpSpec: new THREE.Color(),
    }),
    [],
  );

  useFrame((_, delta) => {
    const d = Math.min(delta, 0.05);
    if (earthRef.current) earthRef.current.rotation.y += d * 0.045;
    if (cloudRef.current) cloudRef.current.rotation.y += d * 0.062;

    const m = matRef.current;
    if (m) {
      c.tmpTint.copy(c.dayTint).lerp(c.darkTint, themeMix);
      m.color.copy(c.tmpTint);
      c.tmpSpec.copy(c.daySpec).lerp(c.darkSpec, themeMix);
      m.specular.copy(c.tmpSpec);
      m.emissive.copy(c.emissive);
      m.emissiveIntensity = themeMix * 1.5;
      m.shininess = THREE.MathUtils.lerp(16, 8, themeMix);
    }
    if (cloudMatRef.current) {
      cloudMatRef.current.opacity = THREE.MathUtils.lerp(0.85, 0.16, themeMix);
    }
  });

  return (
    <group>
      <mesh ref={earthRef}>
        <sphereGeometry args={[1, 128, 128]} />
        <meshPhongMaterial
          ref={matRef}
          map={dayMap}
          normalMap={normalMap}
          normalScale={new THREE.Vector2(0.6, 0.6)}
          specularMap={specularMap}
          emissiveMap={nightMap}
          emissive={"#7df5c0"}
          emissiveIntensity={0}
          shininess={16}
          specular={"#5a7385"}
        />
      </mesh>

      <mesh ref={cloudRef} scale={1.012}>
        <sphereGeometry args={[1, 96, 96]} />
        <meshStandardMaterial
          ref={cloudMatRef}
          alphaMap={cloudMap}
          map={cloudMap}
          transparent
          opacity={0.85}
          depthWrite={false}
          roughness={1}
          metalness={0}
          color={"#ffffff"}
        />
      </mesh>
    </group>
  );
}
