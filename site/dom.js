(() => {
  "use strict";
  const SC = (window.SC = window.SC || {});

  // DOM is built with textContent only: sample data can never inject markup.
  SC.h = function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [name, value] of Object.entries(attrs || {})) {
      if (value === false || value == null) continue;
      if (name.startsWith("on")) el.addEventListener(name.slice(2), value);
      else el.setAttribute(name, value === true ? "" : value);
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(kid));
    }
    return el;
  };

  // replaceChildren() would print "false" for `cond && element`, so every render goes through here.
  SC.mount = (el, ...kids) => el.replaceChildren(...kids.flat(Infinity).filter(Boolean));
  SC.$ = (id) => document.getElementById(id);
  SC.say = (text) => { SC.$("status").textContent = text; };
  SC.plural = (n, noun) => `${n} ${noun}${n === 1 ? "" : "s"}`;
  SC.clock = (seconds) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
  SC.clip = (text, n) => (text.length <= n ? text : `${text.slice(0, n - 1).trimEnd()}\u2026`);
  /** "3 minutes ago". SQLite timestamps are UTC without a zone marker. */
  SC.ago = (stamp) => {
    const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(stamp || "") ? stamp : String(stamp || "").replace(" ", "T") + "Z");
    if (!stamp || !Number.isFinite(date.getTime())) return "a while ago";
    const minutes = Math.round((Date.now() - date.getTime()) / 60000);
    if (minutes < 1) return "just now";
    const [n, unit] = minutes < 60 ? [minutes, "minute"] : minutes < 1440 ? [Math.round(minutes / 60), "hour"] : [Math.round(minutes / 1440), "day"];
    return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
  };
  /** A survey's name, or a plain placeholder when it is blank or a generic site title. */
  SC.surveyName = (title) => (/^\s*(surveys?|untitled)?\s*$/i.test(title || "") ? "Untitled survey" : title.trim());
  SC.SEVERITY = { must_fix: "Must-fix", worth_improving: "Idea" };
  SC.READINESS = { ready: "No blockers found in what we checked", almost_ready: "Ideas to consider", needs_work: "Needs work" };
})();
