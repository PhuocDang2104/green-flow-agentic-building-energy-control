"use client";

import { useEffect, useState } from "react";
import { BookOpen, RotateCcw } from "lucide-react";
import { useTutorialStore } from "./tutorialStore";
import { isTutorialCompleted } from "./tutorialStorage";

/**
 * Compact header entry. Reads completion after mount to avoid an
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
      title={completed ? "Replay the GreenFlow tutorial" : "Walk through GreenFlow in 3 minutes"}
      aria-label={completed ? "Replay GreenFlow tutorial" : "Start GreenFlow tutorial"}
      className="group flex h-9 shrink-0 items-center gap-2 rounded-full border border-teal/20 bg-white px-3 pr-3.5 text-[13px] font-semibold text-teal shadow-sm ring-1 ring-teal/5 transition hover:-translate-y-px hover:border-teal/40 hover:bg-teal hover:text-white hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/35"
    >
      <span className="grid h-6 w-6 place-items-center rounded-full bg-teal text-white transition group-hover:bg-white/20">
        {completed ? <RotateCcw size={13} /> : <BookOpen size={13} />}
      </span>
      <span className="hidden sm:inline">Tutorial</span>
    </button>
  );
}
