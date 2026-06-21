"use client";

/**
 * Smart-city + energy-network layer. Buildings are placed only on real city
 * coordinates (so they sit on land), grouped into a handful of sparse clusters.
 * Each building is a little architecture model (wide base, tower with window
 * glow, rooftop cap). In dark mode the buildings ignite and thin curved energy
 * arcs pulse between the clusters — a digital-twin grid activating across the
 * planet. The whole layer spins in lock-step with the Earth texture so the
 * cities stay glued to their continents.
 */

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const BASE_SPIN = 0.045; // must match EarthObject's earth-mesh spin

// Real cities -> guaranteed land. [lat, lon, weight(#buildings)]
const CITIES: [number, number, number][] = [
  [40.7, -74.0, 6],   // New York
  [34.0, -118.2, 5],  // Los Angeles
  [51.5, -0.1, 5],    // London
  [48.85, 2.35, 3],   // Paris
  [35.7, 139.7, 6],   // Tokyo
  [31.2, 121.5, 5],   // Shanghai
  [1.35, 103.8, 4],   // Singapore
  [25.2, 55.3, 5],    // Dubai
  [19.1, 72.9, 4],    // Mumbai
  [21.0, 105.85, 4],  // Ha Noi
  [-23.5, -46.6, 4],  // Sao Paulo
  [-33.9, 151.2, 4],  // Sydney
  [6.5, 3.4, 3],      // Lagos
];

// inverse of three.js SphereGeometry UV mapping (texture centred at lon 0)
function latLonToVec3(lat: number, lon: number, r = 1) {
  const polar = ((90 - lat) * Math.PI) / 180;
  const a = ((lon + 180) * Math.PI) / 180;
  const sp = Math.sin(polar);
  return new THREE.Vector3(-Math.cos(a) * sp, Math.cos(polar), Math.sin(a) * sp).multiplyScalar(r);
}

interface B { pos: THREE.Vector3; quat: THREE.Quaternion; base: number; tower: number; w: number; }

export default function EarthBuildings({ themeMix, reduced }: { themeMix: number; reduced: boolean }) {
  const spin = useRef<THREE.Group>(null);

  // ---- shared materials (one instance each, updated per frame) ----
  const bodyMat = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#1f7d57", roughness: 0.55, metalness: 0.1, emissive: "#34f5c4", emissiveIntensity: 0 }),
    [],
  );
  const winMat = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#7fe9c2", roughness: 0.3, metalness: 0.2, emissive: "#34f5c4", emissiveIntensity: 0.25 }),
    [],
  );

  // ---- cluster + building geometry data (once) ----
  const { buildings, clusterDirs } = useMemo(() => {
    let seed = 24;
    const rand = () => ((seed = (seed * 9301 + 49297) % 233280), seed / 233280);
    const up = new THREE.Vector3(0, 1, 0);
    const buildings: B[] = [];
    const clusterDirs: THREE.Vector3[] = [];

    for (const [lat, lon, n] of CITIES) {
      const dir = latLonToVec3(lat, lon, 1).normalize();
      clusterDirs.push(dir.clone());
      const ref = Math.abs(dir.y) > 0.9 ? new THREE.Vector3(1, 0, 0) : up;
      const tx = new THREE.Vector3().crossVectors(ref, dir).normalize();
      const ty = new THREE.Vector3().crossVectors(dir, tx).normalize();
      const count = reduced ? Math.max(2, Math.round(n * 0.5)) : n;
      for (let i = 0; i < count; i++) {
        const spread = 0.05;
        const ox = (rand() - 0.5) * spread;
        const oy = (rand() - 0.5) * spread;
        const d = dir.clone().addScaledVector(tx, ox).addScaledVector(ty, oy).normalize();
        const quat = new THREE.Quaternion().setFromUnitVectors(up, d);
        buildings.push({
          pos: d, quat,
          base: 0.012 + rand() * 0.01,
          tower: 0.03 + rand() * 0.08,
          w: 0.011 + rand() * 0.008,
        });
      }
    }
    return { buildings, clusterDirs };
  }, [reduced]);

  // ---- energy arcs between clusters (ring + chords) ----
  const arcs = useMemo(() => {
    const list: { geo: THREE.TubeGeometry; phase: number }[] = [];
    const n = clusterDirs.length;
    const seen = new Set<string>();
    const addArc = (a: number, b: number) => {
      if (a === b) return;
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      if (seen.has(key)) return;
      seen.add(key);
      const va = clusterDirs[a], vb = clusterDirs[b];
      const ang = va.angleTo(vb);
      const mid = va.clone().add(vb).normalize().multiplyScalar(1 + ang * 0.45);
      const curve = new THREE.QuadraticBezierCurve3(
        va.clone().multiplyScalar(1.012), mid, vb.clone().multiplyScalar(1.012),
      );
      list.push({ geo: new THREE.TubeGeometry(curve, 48, 0.0035, 6, false), phase: ((a * 7 + b * 13) % 10) / 10 });
    };
    for (let i = 0; i < n; i++) { addArc(i, (i + 1) % n); addArc(i, (i + 4) % n); }
    return list;
  }, [clusterDirs]);

  const arcUniforms = useMemo(
    () => arcs.map((a) => ({ uTime: { value: 0 }, uMix: { value: 0 }, uPhase: { value: a.phase } })),
    [arcs],
  );

  // ---- glowing city dots ----
  const dotsGeo = useMemo(() => {
    const pos = new Float32Array(clusterDirs.length * 3);
    clusterDirs.forEach((d, i) => {
      const p = d.clone().multiplyScalar(1.02);
      pos[i * 3] = p.x; pos[i * 3 + 1] = p.y; pos[i * 3 + 2] = p.z;
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return g;
  }, [clusterDirs]);
  const dotsMat = useRef<THREE.PointsMaterial>(null);

  const col = useMemo(() => ({
    bodyDay: new THREE.Color("#1f7d57"), bodyDark: new THREE.Color("#2bd9a6"),
    winDay: new THREE.Color("#7fe9c2"), winDark: new THREE.Color("#9bffe0"),
  }), []);

  useFrame((_, delta) => {
    const d = Math.min(delta, 0.05);
    if (spin.current) spin.current.rotation.y += d * BASE_SPIN;

    bodyMat.color.copy(col.bodyDay).lerp(col.bodyDark, themeMix);
    bodyMat.emissiveIntensity = themeMix * 0.9;
    winMat.color.copy(col.winDay).lerp(col.winDark, themeMix);
    winMat.emissiveIntensity = 0.25 + themeMix * 1.7;

    if (dotsMat.current) {
      dotsMat.current.opacity = themeMix * (0.7 + Math.sin(performance.now() * 0.004) * 0.25);
    }
    for (const u of arcUniforms) { u.uTime.value += d; u.uMix.value = themeMix; }
  });

  return (
    <group ref={spin}>
      {buildings.map((b, i) => (
        <group key={i} position={[b.pos.x, b.pos.y, b.pos.z]} quaternion={b.quat}>
          <mesh position={[0, b.base / 2, 0]} material={bodyMat}>
            <boxGeometry args={[b.w * 1.7, b.base, b.w * 1.7]} />
          </mesh>
          <mesh position={[0, b.base + b.tower / 2, 0]} material={winMat}>
            <boxGeometry args={[b.w, b.tower, b.w]} />
          </mesh>
        </group>
      ))}

      {arcs.map((a, i) => (
        <mesh key={`arc-${i}`} geometry={a.geo}>
          <shaderMaterial
            transparent depthWrite={false} blending={THREE.AdditiveBlending}
            uniforms={arcUniforms[i]} vertexShader={ARC_VERT} fragmentShader={ARC_FRAG}
          />
        </mesh>
      ))}

      <points geometry={dotsGeo}>
        <pointsMaterial ref={dotsMat} color="#7dffd9" size={0.05} sizeAttenuation
          transparent opacity={0} depthWrite={false} blending={THREE.AdditiveBlending} />
      </points>
    </group>
  );
}

const ARC_VERT = /* glsl */ `
  varying vec2 vUv;
  void main(){
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const ARC_FRAG = /* glsl */ `
  varying vec2 vUv;
  uniform float uTime;
  uniform float uMix;
  uniform float uPhase;
  void main(){
    float t = fract(vUv.x - uTime * 0.22 + uPhase);
    float pulse = smoothstep(0.0, 0.05, t) * (1.0 - smoothstep(0.05, 0.22, t));
    vec3 cyan = vec3(0.18, 0.95, 0.85);
    vec3 green = vec3(0.30, 1.0, 0.55);
    vec3 col = mix(cyan, green, vUv.x) * (0.55 + pulse * 1.6);
    float a = (0.12 + pulse * 0.9) * uMix;
    gl_FragColor = vec4(col, a);
  }
`;
