(() => {
  "use strict";
  const SC = window.SC;
  const { h } = SC;
  const REMINDER = "RedJade is only changed when you edit it there.";
  const GHOST_NOTE = "Suggested answers must be added in RedJade; shown faded here.";
  const ESTIMATE_NOTE = "Estimated from reading and tapping time. Real members vary.";
  const DEVICE_SIZES = [320, 390, 430];

  /** Plain words, one line, never the vocabulary of the machinery. `changes` = how many wording changes this screen shows. */
  SC.previewLine = ({ fixesMode, changes, ghosts }) => {
    const ghostNote = ghosts > 0 ? GHOST_NOTE : null;
    const text = !fixesMode
      ? (changes ? `${SC.plural(changes, "change")} to preview. ${REMINDER}` : "No wording changes to preview on this screen.")
      : changes ? [`Showing your ${SC.plural(changes, "change")}. ${REMINDER}`, ghostNote].filter(Boolean).join(" ")
        : ghostNote || "No wording changes to preview on this screen.";
    return h("p", { class: "preview-effect", role: "status" }, text);
  };

  /** Text size: a labelled, three-way choice. Real buttons, so Tab, Enter and Space work; focus is restored by data-fk. */
  function textSizeControl(onChange) {
    const current = SC.phoneTextSize.get();
    return h("div", { class: "tool-row" },
      h("span", { id: "text-size-label", class: "tool-label" }, "Text size"),
      h("div", { class: "text-size", role: "group", "aria-labelledby": "text-size-label" },
        SC.TEXT_SIZES.map((size) => h("button", {
          type: "button", "data-fk": `text-size-${size.id}`, "aria-pressed": String(size.id === current),
          onclick: () => { SC.phoneTextSize.set(size.id); onChange(); },
        }, size.label))));
  }

  /**
   * The Preview tools drawer. The caller owns the state (open, device, compare, play) and passes it in:
   * `{open, onToggle, device, onDevice, changes, comparing, onCompare, playing, onPlay, onRender}`.
   */
  SC.phoneTools = (o) => {
    // The details' own toggle event arrives late; every action first reads the real state so a redraw never closes the drawer.
    const drawer = h("details", { class: "preview-tools", open: o.open, ontoggle: () => o.onToggle(drawer.open) });
    const act = (fn) => (...args) => { o.onToggle(drawer.open); return fn(...args); };
    drawer.append(
      h("summary", null, "Preview tools"),
      textSizeControl(act(o.onRender)),
      h("div", { class: "tool-row" }, h("label", null, "Device size",
        h("select", { "aria-label": "Device size", "data-fk": "device-size", onchange: act((event) => o.onDevice(Number(event.target.value))) },
          DEVICE_SIZES.map((size) => h("option", { value: size, selected: o.device === size }, `${size}px`))))),
      h("div", { class: "tool-row" },
        h("button", { type: "button", disabled: !o.changes && !o.comparing, onclick: act(o.onCompare) }, o.comparing ? "Close comparison" : "Compare wording"),
        h("button", { type: "button", onclick: act(o.onPlay) }, o.playing ? "Pause walkthrough" : "Play as a member")));
    return drawer;
  };

  /** Neutral progress, not a danger gauge: the journey strip's one encoding (width = time), a marker at "now", and the plain line.
   *  Screens already reached are filled; the caveat is a tooltip. Without a journey it is a single fill. */
  SC.phoneTimeline = ({ seconds, total, uncertain, journey = [], pageId = null }) => {
    if (uncertain) return h("div", { class: "timing" }, h("p", null, SC.uncertainWalkthrough));
    const share = total > 0 ? Math.min(100, Math.max(0, (seconds / total) * 100)) : 0;
    const here = journey.findIndex((segment) => segment.page_id === pageId);
    const parts = journey.length
      ? journey.map((segment, i) => h("b", { class: i <= here ? "reached" : null, style: `--sec:${segment.seconds}` }))
      : [h("b", { class: "reached", style: `width:${share}%` })];
    return h("div", { class: "timing" },
      h("p", { title: ESTIMATE_NOTE }, `~${SC.clock(seconds)} in · ${Math.max(1, Math.round(total / 60))} min total`),
      h("div", { class: `timebar${journey.length ? " by-screen" : ""}`, "aria-hidden": "true" }, parts, h("i", { style: `left:${share}%` })));
  };
})();
