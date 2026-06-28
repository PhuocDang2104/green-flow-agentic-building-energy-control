"use client";

import { useEffect, useState } from "react";
import { Brain, Check, FileSearch, Loader2, Sparkles } from "lucide-react";

// The /chat endpoint isn't streamed, so we surface the pipeline it actually
// runs (reason → RAG/SQL retrieval → synthesis) as a timed, reassuring stepper.
const STAGES = [
  { icon: Brain, label: "Analyzing your question" },
  { icon: FileSearch, label: "Retrieving documents and live data" },
  { icon: Sparkles, label: "Preparing the response" },
];

export default function ThinkingIndicator() {
  const [stage, setStage] = useState(0);
  const [progress, setProgress] = useState(8);

  useEffect(() => {
    const t1 = setTimeout(() => setStage(1), 700);
    const t2 = setTimeout(() => setStage(2), 1900);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  useEffect(() => {
    // ease toward ~92% then hold until the real answer replaces this card
    const id = setInterval(() => {
      setProgress((p) => (p < 92 ? p + Math.max(1, Math.round((92 - p) * 0.08)) : p));
    }, 180);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="rounded-2xl bg-surface-muted px-3.5 py-3">
      <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-black/5">
        <div className="h-full rounded-full bg-teal transition-all duration-200 ease-out"
             style={{ width: `${progress}%` }} />
      </div>
      <ul className="space-y-1.5">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          const done = i < stage;
          const active = i === stage;
          return (
            <li key={i}
                className={`flex items-center gap-2 text-[12px] transition
                  ${done ? "text-text-muted" : active ? "text-text-primary" : "text-text-muted/50"}`}>
              <span className={`grid h-4 w-4 shrink-0 place-items-center rounded-full
                ${done ? "bg-teal text-white" : active ? "text-teal" : "text-text-muted/40"}`}>
                {done ? <Check size={10} strokeWidth={3} />
                  : active ? <Loader2 size={12} className="animate-spin" />
                  : <Icon size={11} />}
              </span>
              <span className={active ? "font-medium" : ""}>{s.label}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
