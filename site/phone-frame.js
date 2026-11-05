(() => {
  "use strict";
  const SC = window.SC;
  const { h } = SC;

  /* ---------- text size: one place decides, one key persists it for the session ---------- */
  const TEXT_SIZES = [{ id: "small", label: "Small" }, { id: "default", label: "Default" }, { id: "large", label: "Large" }];
  const STORAGE_KEY = "surveycoach.phoneTextSize";
  SC.TEXT_SIZES = TEXT_SIZES;
  SC.phoneTextSize = {
    get() {
      let saved = null;
      try { saved = sessionStorage.getItem(STORAGE_KEY); } catch (_) { /* storage blocked: stay on the default */ }
      return TEXT_SIZES.some((size) => size.id === saved) ? saved : "default";
    },
    set(id) {
      if (!TEXT_SIZES.some((size) => size.id === id)) return;
      try { sessionStorage.setItem(STORAGE_KEY, id); } catch (_) { /* session-only nicety */ }
    },
  };

  /** True while content hides below the fold of the scroll region. */
  const hasMoreBelow = (screen) => screen.scrollHeight - screen.clientHeight > 2
    && screen.scrollTop + screen.clientHeight < screen.scrollHeight - 2;

  /** Keeps the "More below" cue honest: on scroll, on resize of the region or its content, and after first layout. */
  function watchOverflow(viewport, screen, content) {
    const sync = () => { viewport.dataset.more = String(hasMoreBelow(screen)); };
    screen.addEventListener("scroll", sync, { passive: true });
    if (window.ResizeObserver) {
      const observer = new ResizeObserver(sync);
      observer.observe(screen);
      observer.observe(content);
    }
    requestAnimationFrame(sync);
  }

  const statusBar = () => h("div", { class: "phone-status", "aria-hidden": "true" },
    h("span", { class: "status-time" }, "9:41"),
    h("span", { class: "status-icons" }, h("i", { class: "status-signal" }), h("i", { class: "status-battery" })));

  /**
   * The device: status bar, rounded screen, a scroll region the keyboard can reach, and a cue when content is clipped.
   * `children` go inside the scroller; the Next bar sticks to its bottom (see phone-frame.css).
   */
  SC.phoneFrame = ({ title, device, children }) => {
    const content = h("div", { class: "phone-content" }, children);
    const screen = h("div", { class: "phone-screen", tabindex: "0", role: "region", "aria-label": "Survey screen preview, scrollable" }, content);
    const cue = h("button", {
      type: "button", class: "phone-scroll-cue", tabindex: "-1",
      onclick: () => screen.scrollBy({ top: screen.clientHeight * 0.8, behavior: "smooth" }),
    }, "More below ↓");
    const viewport = h("div", { class: "phone-viewport", "data-more": "false" }, screen, cue);
    watchOverflow(viewport, screen, content);
    return h("div", { class: "phone-wrap" },
      h("div", { class: `phone size-${SC.phoneTextSize.get()}`, style: `--w:${device}px` },
        statusBar(), h("div", { class: "phone-bar" }, title), viewport,
        h("div", { class: "phone-home", "aria-hidden": "true" })));
  };

  /** The pinned Next button. Its own wrapper keeps a solid backing so scrolled answers never show through. */
  SC.phoneNext = (label) => h("div", { class: "phone-nextbar" }, h("div", { class: "next" }, label));
})();
