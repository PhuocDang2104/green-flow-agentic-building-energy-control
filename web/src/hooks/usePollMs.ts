"use client";

import { useAppStore } from "@/stores/appStore";

/** Poll faster while streaming so the dashboard visibly "runs". */
export function usePollMs(base: number, live = 4000): number {
  return useAppStore((s) => s.streaming) ? live : base;
}
