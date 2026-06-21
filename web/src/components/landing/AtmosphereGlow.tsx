"use client";

// Fresnel rim glow rendered on a slightly larger back-side sphere.

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const vertex = /* glsl */ `
  varying vec3 vNormal;
  void main(){
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const fragment = /* glsl */ `
  varying vec3 vNormal;
  uniform vec3 uColor;
  uniform float uIntensity;
  void main(){
    // soft, thin, transparent rim halo (low intensity)
    float f = pow(1.0 - max(dot(vNormal, vec3(0.0,0.0,1.0)), 0.0), 3.4);
    gl_FragColor = vec4(uColor, f * uIntensity);
  }
`;

export default function AtmosphereGlow({ themeMix }: { themeMix: number }) {
  const matRef = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({
      uColor: { value: new THREE.Color("#a9d8ff") },
      uIntensity: { value: 0.42 },
    }),
    [],
  );
  const day = useMemo(() => new THREE.Color("#a9d8ff"), []);
  const dark = useMemo(() => new THREE.Color("#46f0b4"), []);

  useFrame(() => {
    if (!matRef.current) return;
    const c = matRef.current.uniforms.uColor.value as THREE.Color;
    c.copy(day).lerp(dark, themeMix);
    // low-intensity glow in light mode, a touch stronger in dark
    matRef.current.uniforms.uIntensity.value = 0.4 + themeMix * 0.5;
  });

  return (
    <mesh scale={1.14}>
      <sphereGeometry args={[1, 64, 64]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={vertex}
        fragmentShader={fragment}
        uniforms={uniforms}
        transparent
        blending={THREE.AdditiveBlending}
        side={THREE.BackSide}
        depthWrite={false}
      />
    </mesh>
  );
}
