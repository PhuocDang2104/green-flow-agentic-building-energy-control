"use client";

/**
 * Procedural Earth — a real WebGL sphere (no textures needed). A custom shader
 * paints oceans + green landmasses from value noise, with day↔dark blending
 * driven by a uThemeMix uniform that GSAP/lerp animates on theme toggle.
 */

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const vertex = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vPos;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPos = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

// classic 3D simplex-ish value noise (cheap, good enough for stylised land)
const fragment = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vPos;
  uniform float uTime;
  uniform float uThemeMix; // 0 = day, 1 = dark

  float hash(vec3 p){ p = fract(p*0.3183099+0.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
  float noise(vec3 x){
    vec3 i = floor(x); vec3 f = fract(x);
    f = f*f*(3.0-2.0*f);
    return mix(mix(mix(hash(i+vec3(0,0,0)),hash(i+vec3(1,0,0)),f.x),
                   mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),
                   mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
  }
  float fbm(vec3 p){ float v=0.0,a=0.5; for(int i=0;i<5;i++){v+=a*noise(p);p*=2.0;a*=0.5;} return v; }

  void main(){
    vec3 p = normalize(vPos);
    float land = fbm(p*2.4);
    float isLand = smoothstep(0.52, 0.6, land);

    // day palette
    vec3 ocean = vec3(0.05, 0.30, 0.55);
    vec3 oceanShallow = vec3(0.10, 0.52, 0.66);
    vec3 green = vec3(0.18, 0.55, 0.27);
    vec3 greenHi = vec3(0.40, 0.72, 0.36);
    vec3 dayCol = mix(mix(ocean, oceanShallow, smoothstep(0.4,0.55,land)),
                      mix(green, greenHi, smoothstep(0.6,0.8,land)), isLand);

    // dark/digital palette
    vec3 darkBase = vec3(0.02, 0.09, 0.07);
    vec3 grid = vec3(0.06, 0.22, 0.16);
    vec3 cityGlow = vec3(0.30, 0.85, 0.55);
    float city = step(0.78, fbm(p*9.0)) * isLand;
    vec3 darkCol = mix(darkBase, grid, isLand*0.7) + cityGlow * city * 1.4;

    vec3 col = mix(dayCol, darkCol, uThemeMix);

    // simple lambert from a fixed sun + rim
    vec3 lightDir = normalize(vec3(0.6, 0.35, 0.8));
    float diff = max(dot(vNormal, lightDir), 0.0);
    float ambient = mix(0.35, 0.22, uThemeMix);
    float rim = pow(1.0 - max(dot(vNormal, vec3(0.0,0.0,1.0)),0.0), 2.5);
    col = col * (ambient + diff*0.9) + rim * mix(vec3(0.3,0.6,0.9), vec3(0.1,0.7,0.5), uThemeMix) * 0.5;

    gl_FragColor = vec4(col, 1.0);
  }
`;

export default function EarthObject({ themeMix }: { themeMix: number }) {
  const matRef = useRef<THREE.ShaderMaterial>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const uniforms = useMemo(
    () => ({ uTime: { value: 0 }, uThemeMix: { value: 0 } }),
    [],
  );

  useFrame((_, delta) => {
    if (meshRef.current) meshRef.current.rotation.y += delta * 0.05;
    if (matRef.current) {
      matRef.current.uniforms.uTime.value += delta;
      // smoothly approach target theme mix
      const cur = matRef.current.uniforms.uThemeMix.value;
      matRef.current.uniforms.uThemeMix.value += (themeMix - cur) * Math.min(1, delta * 2.2);
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1, 96, 96]} />
      <shaderMaterial
        ref={matRef}
        vertexShader={vertex}
        fragmentShader={fragment}
        uniforms={uniforms}
      />
    </mesh>
  );
}
