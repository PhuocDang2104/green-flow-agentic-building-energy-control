import { useAppStore } from "@/stores/appStore";
import { useTutorialStore } from "./tutorialStore";
import type { TutorialAction } from "./types";

/** Pick a stable live zone to demo (prefer an office-like zone, else the first). */
function pickDemoZone(): string | null {
  const zoneStates = useAppStore.getState().zoneStates;
  const keys = Object.keys(zoneStates);
  if (!keys.length) return null;
  const office = keys.find((k) => /office|open/i.test(k));
  return office ?? keys[0];
}

// A running layer showcase is cancelled whenever new actions run (step change),
// so its queued timers never fight the next step's layer setup.
let showcaseToken = 0;
function runLayerShowcase() {
  const my = ++showcaseToken;
  const app = useAppStore.getState();
  const base = { architecture: false, spaces: false, fenestration: false };
  const frames: Record<string, boolean>[] = [
    { ...base, structural: true, electrical: false, hvac: false },
    { ...base, structural: true, electrical: true, hvac: false },
    { ...base, structural: true, electrical: true, hvac: true },
    { ...base, structural: false, architecture: true, spaces: true, electrical: false, hvac: false },
    { ...base, structural: true, electrical: true, hvac: true }, // settle: full technical stack
  ];
  frames.forEach((layers, i) => {
    setTimeout(() => {
      if (showcaseToken !== my) return; // superseded
      app.setLayers(layers);
    }, i * 1150);
  });
}

/**
 * Interpret a step's before/after actions. Most reuse existing appStore
 * handlers; camera / validation / agent-preview / electrical-showcase go through
 * the tutorialStore command bridge. `navigate` is router.push from the provider.
 */
export function runTutorialActions(
  actions: TutorialAction[] | undefined,
  navigate: (route: string) => void,
): void {
  // Any step transition cancels an in-flight layer showcase.
  showcaseToken += 1;
  if (!actions?.length) return;
  const app = useAppStore.getState();
  const tut = useTutorialStore.getState();

  for (const action of actions) {
    switch (action.type) {
      case "switchTab":
        navigate(action.route);
        break;
      case "setLayer":
        app.setLayer(action.layer, action.enabled);
        break;
      case "setLayers":
        app.setLayers(action.layers);
        break;
      case "setHeatmap":
        app.setTechHeatmap(action.heatmap, action.enabled);
        break;
      case "setMetric":
        app.setMetric(action.metric);
        break;
      case "selectZone": {
        const zoneId = action.zoneId ?? pickDemoZone();
        if (zoneId) app.selectEntity(zoneId);
        break;
      }
      case "clearZone":
        app.selectEntity(null);
        break;
      case "setCamera":
        tut.setCameraPreset(action.preset);
        break;
      case "showcaseLayers":
        runLayerShowcase();
        break;
      case "openChatbot":
        app.setChatbotOpen(action.open);
        break;
      case "startAgentPreview":
        tut.setAgentPreview(true);
        break;
      case "stopAgentPreview":
        tut.setAgentPreview(false);
        break;
      case "setValidationMetric":
        tut.setValidationMetric(action.metric);
        break;
      case "toggleElNino":
        tut.setElNinoOverride(action.on);
        break;
      case "setElectricalColorMode":
        tut.setElecColorMode(action.mode);
        break;
      case "focusElectricalBoard":
        tut.setElecFocusBoard(action.which);
        break;
      case "setElectricalLinks":
        tut.setElecLinks(action.on);
        break;
      case "setElectricalShowcase":
        tut.setElecShowcase(action.on);
        break;
    }
  }
}
