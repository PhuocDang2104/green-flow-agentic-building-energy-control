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
    float f = pow(1.0 - max(dot(vNormal, vec3(0.0,0.0,1.0)), 0.0), 2.2);
    gl_FragColor = vec4(uColor, f * uIntensity);
  }
`;

export default function AtmosphereGlow({ themeMix }: { themeMix: number }) {
  const matRef = useRef<THREE.ShaderMaterial>(null);
  const uniforms = useMemo(
    () => ({
      uColor: { value: new THREE.Color("#7fc6ff") },
      uIntensity: { value: 0.9 },
    }),
    [],
  );
  const day = useMemo(() => new THREE.Color("#7fc6ff"), []);
  const dark = useMemo(() => new THREE.Color("#3ef0a6"), []);

  useFrame(() => {
    if (!matRef.current) return;
    const c = matRef.current.uniforms.uColor.value as THREE.Color;
    c.copy(day).lerp(dark, themeMix);
    matRef.current.uniforms.uIntensity.value = 0.85 + themeMix * 0.6;
  });

  return (
    <mesh scale={1.18}>
      <sphereGeometry args={[1, 48, 48]} />
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
