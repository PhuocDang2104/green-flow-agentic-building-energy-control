"use client";

import { useCallback, useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useReducedMotion } from "motion/react";
import { useTutorialStore } from "./tutorialStore";
import { tutorialSteps } from "./tutorialSteps";
import { runTutorialActions } from "./tutorialActions";
import { markTutorialCompleted } from "./tutorialStorage";
import { useTutorialTarget, useSecondaryRects } from "./useTutorialTarget";
import TutorialOverlay from "./TutorialOverlay";
import TutorialPanel from "./TutorialPanel";
import TutorialProgressRail from "./TutorialProgressRail";
import TutorialMedia from "./TutorialMedia";

const STEPS = tutorialSteps;

/**
 * Owns the tutorial run: enforces each step's route, executes before/after
 * actions, tracks the spotlight target, and renders overlay + panel + rail.
 * Mounted once in AppShell. Renders nothing unless a tour is running.
 */
export default function TutorialProvider({ children }: { children: React.ReactNode }) {
  const status = useTutorialStore((s) => s.status);
  const stepIndex = useTutorialStore((s) => s.stepIndex);
  const setStepIndex = useTutorialStore((s) => s.setStepIndex);
  const start = useTutorialStore((s) => s.start);
  const complete = useTutorialStore((s) => s.complete);
  const exit = useTutorialStore((s) => s.exit);

  const router = useRouter();
  const pathname = usePathname();
  const pathRef = useRef(pathname);
  useEffect(() => { pathRef.current = pathname; }, [pathname]);
  // trap Tab focus only for true modals (centered/read-only), not hands-on steps
  const trapFocusRef = useRef(false);

  const reduceMotion = useReducedMotion() ?? false;
  const running = status === "running";
  const step = STEPS[stepIndex];
  const { rect, status: targetStatus } = useTutorialTarget(
    running ? step?.target : undefined,
    step?.id ?? "",
    step?.scrollBlock ?? "center",
  );
  const secondaryRects = useSecondaryRects(
    running ? step?.spotlights : undefined,
    step?.id ?? "",
  );
  const anchored = !!step?.target;
  const found = targetStatus === "found";
  const overlayRects = found && rect ? [rect, ...secondaryRects] : [];
  // while the page/run is still settling, hold on a "preparing" card instead of
  // jumping the spotlight; once the target mounts we bound the box.
  const pending = anchored && targetStatus === "pending";
  // every anchored step is interactive (the region stays usable) unless opted out
  const interactive = anchored && !step?.blockInteraction;
  trapFocusRef.current = !interactive; // only modal/read-only steps trap focus

  const navigate = useCallback((route: string) => {
    if (pathRef.current !== route) router.push(route);
  }, [router]);

  // On entering a step: ensure the right route, then run its `before` actions.
  useEffect(() => {
    if (!running || !step) return;
    if (pathRef.current !== step.route) router.push(step.route);
    runTutorialActions(step.before, navigate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, stepIndex]);

  const restoreFocus = useCallback(() => {
    const btn = document.querySelector<HTMLElement>('[data-tour-id="tutorial-entry"]');
    btn?.focus();
  }, []);

  const goNext = useCallback(() => {
    const cur = STEPS[stepIndex];
    runTutorialActions(cur?.after, navigate); // forward-only side effects
    if (stepIndex < STEPS.length - 1) setStepIndex(stepIndex + 1);
    else { markTutorialCompleted(); complete(); restoreFocus(); }
  }, [stepIndex, navigate, setStepIndex, complete, restoreFocus]);

  const goBack = useCallback(() => {
    if (stepIndex > 0) setStepIndex(stepIndex - 1);
  }, [stepIndex, setStepIndex]);

  // jump straight to a chapter's first step from the progress rail
  const jumpTo = useCallback((i: number) => {
    if (i !== stepIndex) setStepIndex(i);
  }, [stepIndex, setStepIndex]);

  const skip = useCallback(() => { exit(); restoreFocus(); }, [exit, restoreFocus]);
  const finish = useCallback(() => {
    markTutorialCompleted(); complete(); restoreFocus();
  }, [complete, restoreFocus]);
  const replay = useCallback(() => { start(); }, [start]);

  // Esc to exit + a lightweight focus trap inside the panel.
  useEffect(() => {
    if (!running) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); skip(); return; }
      if (e.key === "Tab") {
        if (!trapFocusRef.current) return; // hands-on steps: let Tab reach the page
        const panel = document.querySelector<HTMLElement>("[data-gf-tutorial-panel]");
        if (!panel) return;
        const focusables = panel.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input, [tabindex]:not([tabindex="-1"])',
        );
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement as HTMLElement | null;
        if (!panel.contains(active)) { e.preventDefault(); first.focus(); return; }
        if (e.shiftKey && active === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus(); }
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [running, skip]);

  return (
    <>
      {children}
      {running && step && (
        <>
          <TutorialOverlay
            rects={overlayRects}
            interactive={interactive}
            pulse={interactive}
            reduceMotion={reduceMotion}
          />
          {step.media && step.media.length > 0 && !pending && (
            <TutorialMedia media={step.media} reduceMotion={reduceMotion} />
          )}
          <TutorialPanel
            step={step}
            index={stepIndex}
            total={STEPS.length}
            rect={found ? rect : null}
            pending={pending}
            reduceMotion={reduceMotion}
            onBack={goBack}
            onNext={goNext}
            onSkip={skip}
            onReplay={replay}
            onFinish={finish}
          />
          <TutorialProgressRail steps={STEPS} index={stepIndex} onJump={jumpTo} />
        </>
      )}
    </>
  );
}
