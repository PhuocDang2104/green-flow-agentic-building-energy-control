"use client";

import { useEffect, useState } from "react";
import { PlayCircle, RotateCcw } from "lucide-react";
import { useTutorialStore } from "./tutorialStore";
import { isTutorialCompleted } from "./tutorialStorage";

/**
 * Compact header entry: "Tutorial Mode" for first-timers, "Replay tour" once the
 * current version has been completed. Reads completion after mount to avoid an
 * SSR/hydration mismatch.
 */
export default function TutorialEntryButton() {
  const start = useTutorialStore((s) => s.start);
  const status = useTutorialStore((s) => s.status);
  const [completed, setCompleted] = useState(false);
  useEffect(() => { setCompleted(isTutorialCompleted()); }, [status]);

  return (
    <button
      data-tour-id="tutorial-entry"
      onClick={start}
      title="Walk through GreenFlow in 3 minutes"
      aria-label={completed ? "Replay GreenFlow tutorial" : "Start GreenFlow tutorial"}
      className="flex shrink-0 items-center gap-1.5 rounded-button border border-teal/30 bg-teal-soft px-2.5 py-1.5 text-[12.5px] font-semibold text-teal transition hover:bg-teal hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/30"
    >
      {completed ? <RotateCcw size={14} /> : <PlayCircle size={14} />}
      <span className="hidden md:inline">{completed ? "Replay tour" : "Tutorial Mode"}</span>
    </button>
  );
}
