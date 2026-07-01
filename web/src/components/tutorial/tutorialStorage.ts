// Persist tutorial completion so the header button can offer "Replay" and we
// avoid nagging returning users. Version-gated so future content can re-prompt.

export const TUTORIAL_VERSION = "2026-07-greenflow-v1";

const KEY_DONE = "greenflow.tutorial.completed";
const KEY_AT = "greenflow.tutorial.completedAt";
const KEY_VER = "greenflow.tutorial.version";

export function markTutorialCompleted(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY_DONE, "true");
    window.localStorage.setItem(KEY_AT, new Date().toISOString());
    window.localStorage.setItem(KEY_VER, TUTORIAL_VERSION);
  } catch {
    /* storage unavailable (private mode) — non-fatal */
  }
}

/** true once the user has finished the current tutorial version. */
export function isTutorialCompleted(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(KEY_DONE) === "true"
      && window.localStorage.getItem(KEY_VER) === TUTORIAL_VERSION;
  } catch {
    return false;
  }
}
