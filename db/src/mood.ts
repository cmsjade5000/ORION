import type { MoodDefinition, OrionState } from "./types";

function baseMood(
  key: MoodDefinition["key"],
  label: MoodDefinition["label"],
  tagline: string
): MoodDefinition {
  return { key, label, tagline };
}

export function resolveMood(args: {
  state: OrionState;
  signalIntegrity: number;
  coreTemperature: number;
  activeTasks: number;
}): MoodDefinition {
  const { state, signalIntegrity, coreTemperature, activeTasks } = args;

  if (state.clarity < 35 && state.stability < 45) {
    return baseMood("signal-noise", "Signal Noise", "Input channels are noisy; filter stack recalibrating.");
  }

  if (activeTasks >= 5 && state.energy < 45) {
    return baseMood("process-locked", "Process Locked", "Queue pressure is high; release cycle required.");
  }

  if (signalIntegrity < 45 || state.alignment < 40) {
    return baseMood("desynced", "Desynced", "Core vectors are out of phase; alignment required.");
  }

  if (coreTemperature > 80 && activeTasks >= 3) {
    return baseMood("overclocked", "Overclocked", "Thermal load elevated under sustained throughput.");
  }

  if (state.energy < 35) {
    return baseMood("low-bandwidth", "Low Bandwidth", "Power reserve is constrained; throttle recommended.");
  }

  if (state.curiosity >= 78 && activeTasks <= 2) {
    return baseMood("scan-mode", "Scan Mode", "Exploration threads active across open signal lanes.");
  }

  if (signalIntegrity >= 85 && state.energy >= 70 && activeTasks <= 3) {
    return baseMood("peak-throughput", "Peak Throughput", "All channels synchronized at high efficiency.");
  }

  if (signalIntegrity >= 72 && state.uptime_days >= 2) {
    return baseMood("stable-sync", "Stable Sync", "Core state is coherent and sustaining rhythm.");
  }

  if (activeTasks > 0) {
    return baseMood("background-cycle", "Background Cycle", "Low-latency maintenance running in parallel.");
  }

  return baseMood("standby", "Standby", "Core is stable and waiting for directives.");
}
