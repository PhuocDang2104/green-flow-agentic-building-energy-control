import { useAppStore } from "@/stores/appStore";
import { useTutorialStore } from "./tutorialStore";
import type { CameraPreset, TutorialAction } from "./types";

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
  const tut = useTutorialStore.getState();
  const frames: Array<{ layers: Record<string, boolean>; camera: CameraPreset }> = [
    {
      // Start by removing the structural shell, then rebuild the mental model
      // through visible discipline layers. This keeps the showcase from looking
      // like a static structural view with boxes ticking on top.
      layers: { architecture: true, spaces: false, fenestration: true, structural: false, electrical: false, hvac: false },
      camera: "layer-architecture",
    },
    {
      layers: { architecture: true, spaces: false, fenestration: true, structural: false, electrical: true, hvac: false },
      camera: "layer-electrical",
    },
    {
      layers: { architecture: true, spaces: false, fenestration: true, structural: false, electrical: false, hvac: true },
      camera: "layer-hvac",
    },
    {
      layers: { architecture: false, spaces: true, fenestration: false, structural: false, electrical: false, hvac: false },
      camera: "layer-spaces",
    },
    {
      layers: { architecture: true, spaces: true, fenestration: true, structural: false, electrical: true, hvac: true },
      camera: "technical-stack",
    },
  ];
  app.setTechHeatmap("electrical", false);
  app.setTechHeatmap("hvac", false);
  app.setMetric("none");
  frames.forEach((frame, i) => {
    setTimeout(() => {
      if (showcaseToken !== my) return; // superseded
      app.setLayers(frame.layers);
      tut.setCameraPreset(frame.camera);
    }, i * 1250);
  });
}

function runSystemHeatmapShowcase() {
  const my = ++showcaseToken;
  const app = useAppStore.getState();
  const tut = useTutorialStore.getState();
  const baseLayers = {
    architecture: true,
    spaces: false,
    fenestration: true,
    structural: false,
    hvac: true,
    electrical: true,
  };
  const frames: Array<{
    delay: number;
    layers: Record<string, boolean>;
    electricalHeat: boolean;
    hvacHeat: boolean;
    camera: CameraPreset;
  }> = [
    {
      delay: 0,
      layers: { ...baseLayers, electrical: false, hvac: true },
      electricalHeat: false,
      hvacHeat: true,
      camera: "technical-close-hvac",
    },
    {
      delay: 680,
      layers: { ...baseLayers, electrical: true, hvac: false },
      electricalHeat: true,
      hvacHeat: false,
      camera: "technical-close-electrical",
    },
    {
      delay: 1360,
      layers: baseLayers,
      electricalHeat: true,
      hvacHeat: true,
      camera: "layer-electrical",
    },
    {
      delay: 2040,
      layers: baseLayers,
      electricalHeat: true,
      hvacHeat: true,
      camera: "layer-hvac",
    },
    {
      delay: 2720,
      layers: baseLayers,
      electricalHeat: true,
      hvacHeat: true,
      camera: "technical-stack",
    },
  ];

  app.setMetric("none");
  tut.setViewerSpin(false);
  frames.forEach((frame) => {
    setTimeout(() => {
      if (showcaseToken !== my) return;
      app.setLayers(frame.layers);
      app.setTechHeatmap("electrical", frame.electricalHeat);
      app.setTechHeatmap("hvac", frame.hvacHeat);
      tut.setCameraPreset(frame.camera);
    }, frame.delay);
  });
}

// Auto-cycle the selected zone (drives the 3D highlight + the zone-table row) on
// a loop; cancelled on any step transition like the layer showcase.
let zoneToken = 0;
function runZoneCycle() {
  const my = ++zoneToken;
  let i = 0;
  const tick = () => {
    if (zoneToken !== my) return;
    const app = useAppStore.getState();
    const keys = Object.keys(app.zoneStates ?? {});
    if (keys.length) {
      app.selectEntity(keys[i % keys.length]);
      i += 1;
    }
    setTimeout(tick, 1700);
  };
  tick();
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
  // Any step transition cancels in-flight showcase/zone loops.
  showcaseToken += 1;
  zoneToken += 1;
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
      case "showcaseSystemHeatmaps":
        runSystemHeatmapShowcase();
        break;
      case "setViewerSpin":
        tut.setViewerSpin(action.on);
        break;
      case "cycleZones":
        runZoneCycle();
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
