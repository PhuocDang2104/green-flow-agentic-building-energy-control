import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GreenFlow · Agentic Digital Twin",
  description:
    "Simulation-first operations layer for energy-efficient buildings: 3D digital twin, agent orchestration, counterfactual proof.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
