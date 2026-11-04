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
  SC.SEVERITY = { must_fix: "Must-fix", worth_improving: "Idea" };
  SC.READINESS = { ready: "No blockers found in what we checked", almost_ready: "Ideas to consider", needs_work: "Needs work" };
})();
