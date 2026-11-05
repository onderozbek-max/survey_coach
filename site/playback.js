/* One playback clock for the phone preview's "Play as a member", and the reading-time evidence for rewrites. */
(() => {
  'use strict';
  const SC = window.SC;
  SC.uncertainWalkthrough = 'Captured-screen walkthrough; route uncertain.';

  // A single pending timeout. Pausing preserves remaining reading time; hidden tabs never advance.
  SC.createPlayback = ({seconds, advance, changed = () => {}}) => {
    let timer = null, playing = false, remaining = null, started = 0, disposed = false;
    const clear = () => { clearTimeout(timer); timer = null; };
    const pause = () => {
      if (playing) remaining = Math.max(0, remaining - (Date.now() - started));
      clear(); playing = false; changed(false);
    };
    const schedule = () => {
      clear();
      if (!playing || document.hidden || disposed) { pause(); return; }
      remaining ??= Math.max(1, seconds()) * 1000;
      started = Date.now();
      timer = setTimeout(() => {
        timer = null; remaining = null;
        if (!advance()) { playing = false; changed(false); return; }
        schedule();
      }, remaining);
    };
    const hidden = () => { if (document.hidden) pause(); };
    document.addEventListener('visibilitychange', hidden);
    return {
      play() { if (disposed || playing || document.hidden) return; playing = true; changed(true); schedule(); },
      pause,
      reset() { clear(); remaining = null; if (playing) schedule(); },
      get playing() { return playing; },
      dispose() { pause(); disposed = true; document.removeEventListener('visibilitychange', hidden); },
    };
  };

  // Timing owns capture deduplication and the reading rate. Never reconstruct
  // that basis from raw + structured copies here: they overlap, not add up.
  SC.previewReadingDelta = (page, plan) => {
    const basis = page.reading_basis;
    if (!basis || !Number.isFinite(basis.seconds_per_word) || basis.seconds_per_word <= 0
        || !Array.isArray(basis.fields)
        || basis.fields.some(field => !field || typeof field.text !== 'string')) return null;
    const words = text => text.trim().split(/\s+/).filter(Boolean).length;
    const delta = basis.fields.reduce((sum, field) => {
      const changed = SC.applyFixes(field.text, plan, null,
        {page_id:page.id, question_id:field.question_id});
      return sum + words(field.text) - words(changed);
    }, 0);
    return Math.round(delta * basis.seconds_per_word);
  };

  SC.previewReadingEvidence = (page, plan) => {
    const delta = SC.previewReadingDelta(page, plan);
    if (delta === null) return 'Reading-time change unavailable: this saved review has no canonical reading basis. Wording changes are shown below.';
    return `Estimated reading-time change: ${Math.abs(delta)} seconds ${delta < 0 ? 'longer' : 'shorter'}. Layout, typing and unvisited paths are not reassessed.`;
  };
})();
