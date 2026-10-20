// The flap click. Synthesized with WebAudio so there is nothing to license: a short noise
// burst through a band-pass filter, a little different every time so a cascade does not
// sound like a loop. At most one click per animation frame, and never two within 12 ms,
// however many cells step.
// If static/sounds/flap.(mp3|ogg|wav) exists it is decoded once and used instead.
// Nothing plays before a user gesture (autoplay policy): the fullscreen click unlocks it.
//
// Exposes window.Sound = { unlock, click, configure, state }. Plain script, no modules.
(() => {
  "use strict";
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const state = { enabled: true, volume: 0.6, unlocked: false, source: "synth", clicks: 0 };
  let ctx = null;
  let master = null;
  let sample = null; // AudioBuffer from a user-supplied file
  let lastFrame = -1;
  let lastAt = -1;
  let frame = 0;
  const MIN_GAP = 0.012; // seconds between clicks, whatever the display's refresh rate

  function configure(settings) {
    if (!settings) return;
    if (settings.sound_enabled !== undefined) state.enabled = !!settings.sound_enabled;
    if (settings.sound_volume !== undefined) {
      state.volume = Math.max(0, Math.min(1, Number(settings.sound_volume) || 0));
    }
    if (master) master.gain.value = state.volume;
  }

  // Look once for a user-supplied sample; silently fall back to the synth.
  async function loadSample() {
    for (const ext of ["mp3", "ogg", "wav"]) {
      const url = `/static/sounds/flap.${ext}`;
      try {
        const head = await fetch(url, { method: "HEAD" });
        if (!head.ok) continue;
        const data = await (await fetch(url)).arrayBuffer();
        sample = await ctx.decodeAudioData(data);
        state.source = `file:${ext}`;
        return;
      } catch {
        /* try the next one */
      }
    }
  }

  // Called from a user gesture. Creates the context and resumes it.
  async function unlock() {
    if (!AudioCtx) return false;
    if (!ctx) {
      ctx = new AudioCtx();
      master = ctx.createGain();
      master.gain.value = state.volume;
      master.connect(ctx.destination);
      loadSample();
    }
    try {
      if (ctx.state !== "running") await ctx.resume();
    } catch {
      /* stays locked until the next gesture */
    }
    state.unlocked = ctx.state === "running";
    return state.unlocked;
  }

  function synthClick(at) {
    // ~8 ms of noise, band-passed around 2–3 kHz, fast decay; pitch and gain jittered.
    const length = Math.floor(ctx.sampleRate * 0.012);
    const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) {
      const env = Math.exp(-i / (length * 0.18));
      data[i] = (Math.random() * 2 - 1) * env;
    }
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = 2200 + Math.random() * 900;
    filter.Q.value = 1.2;
    const gain = ctx.createGain();
    gain.gain.value = 0.35 + Math.random() * 0.25;
    src.connect(filter);
    filter.connect(gain);
    gain.connect(master);
    src.start(at);
  }

  function sampleClick(at) {
    const src = ctx.createBufferSource();
    src.buffer = sample;
    src.playbackRate.value = 0.94 + Math.random() * 0.12;
    const gain = ctx.createGain();
    gain.gain.value = 0.7 + Math.random() * 0.3;
    src.connect(gain);
    gain.connect(master);
    src.start(at);
  }

  // One click per animation frame at most; `frameId` is the rAF timestamp or counter.
  function click(frameId) {
    if (!state.enabled || !state.unlocked || !ctx) return false;
    const id = frameId === undefined ? frame : frameId;
    if (id === lastFrame) return false;
    const at = ctx.currentTime;
    if (at - lastAt < MIN_GAP) return false;
    lastFrame = id;
    lastAt = at;
    if (sample) sampleClick(at);
    else synthClick(at);
    state.clicks += 1;
    return true;
  }

  // Lets callers without a rAF timestamp still get the per-frame throttle.
  function tick() {
    frame += 1;
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  window.Sound = { unlock, click, configure, state };
})();
