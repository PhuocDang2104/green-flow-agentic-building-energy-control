"use client";

import dynamic from "next/dynamic";

const LandingExperience = dynamic(
  () => import("@/components/landing/LandingExperience"),
  {
    ssr: false,
    loading: () => (
      <div className="grid min-h-screen place-items-center bg-[#f8fbf6] text-[#007a3d]">
        <span className="text-sm font-medium">Loading GreenFlow...</span>
      </div>
    ),
  },
);

export default function Home() {
  return <LandingExperience />;
}
