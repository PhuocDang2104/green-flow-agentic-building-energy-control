"use client";

import dynamic from "next/dynamic";

// The whole landing experience is client-only (React Three Fiber + GSAP
// Observer). SSR is disabled to avoid WebGL/hydration issues.
const LandingExperience = dynamic(
  () => import("@/components/landing/LandingExperience"),
  {
    ssr: false,
    loading: () => (
      <div className="grid min-h-screen place-items-center bg-[#f8fbf6] text-[#007a3d]">
        <span className="text-sm font-medium tracking-wide">Loading GreenFlow…</span>
      </div>
    ),
  },
);

export default function Home() {
  return <LandingExperience />;
}
