(() => {
  "use strict";
  const SC = window.SC;
  const { h, plural } = SC;

  function chips(entry, ctx) {
    const { f, n } = entry, criterion = ctx.data.criteria[f.criterion_id] || {};
    const area = ctx.data.dimensions[criterion.dimension];   // blockers have no area; "Must fix" already says it
    return h("div", { class: "chips" },
      h("span", { class: "badge-n" }, String(n)),
      f.source === "ai" && h("span", { class: "chip ai" }, "AI"),      // who said it comes first: an AI claim is never mistaken for a rule
      h("span", { class: `chip ${f.severity}` }, SC.SEVERITY[f.severity]),
      area && h("span", { class: "chip area" }, area),
      (f.structural || ctx.offscreen(entry)) && h("span", { class: "chip warn" }, "Not previewed"),
      ctx.blocked(entry) && h("span", { class: "chip warn" }, "Not shown in preview"),
      ctx.applied(entry) && h("span", { class: "chip good" }, "Fixed in preview"));
  }

  /** Word-level before/after: only the words that change are marked, so nobody has to compare two sentences. */
  function diffParts(before, after) {
    const a = before.split(" "), b = after.split(" ");
    let head = 0;
    while (head < a.length && head < b.length && a[head] === b[head]) head += 1;
    let tail = 0;
    while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail += 1;
    const join = (words) => words.join(" ");
    return { head: join(a.slice(0, head)), cut: join(a.slice(head, a.length - tail)), add: join(b.slice(head, b.length - tail)), tail: join(a.slice(a.length - tail)) };
  }

  const spaced = (...parts) => parts.filter(Boolean).flatMap((p, i) => (i ? [" ", p] : [p]));

  /** A bundle is the question on its first line and one answer choice per line; show the stem bold and the choices compact. */
  const bundle = (text) => {
    const [stem, ...choices] = text.split("\n");
    return [h("span", { class: "stem" }, stem), choices.length ? h("span", { class: "choices" }, choices.join(" \u00b7 ")) : null];
  };

  /** "Which version is better?": the researcher's pick drives the phone preview and what gets copied. */
  function choiceBlock(entry, ctx) {
    const { f, key, n } = entry, choices = SC.choicesOf(f), picked = ctx.choiceOf(key) || choices[0].value;
    const chosen = SC.chosenChoice(f, picked), msg = h("p", { class: "note", role: "status" });
    const markable = f.current_text && !f.structural;     // a bundle of answer choices is shown whole, not word-diffed
    const radio = (value, label, body) => h("label", { class: `opt${picked === value ? " on" : ""}` },
      h("input", { type: "radio", name: `choice-${key}`, value, checked: picked === value, "data-fk": `opt-${key}-${value}`, onchange: () => ctx.onChoose(key, value) }),
      h("span", { class: "opt-body" }, h("span", { class: "opt-label" }, label), h("span", { class: "opt-text" }, body)));
    const alone = choices.length === 1 && markable ? diffParts(f.current_text, choices[0].text) : null;
    const original = alone ? spaced(alone.head, alone.cut && h("del", null, alone.cut), alone.tail)
      : f.structural && f.current_text ? bundle(ctx.originalOf(entry)) : f.current_text || "Nothing added";
    const version = (c) => {
      if (f.structural) return bundle(c.text);
      if (!markable) return c.text;
      const d = diffParts(f.current_text, c.text);
      return spaced(d.head, d.add && h("ins", null, d.add), d.tail);
    };
    const note = f.structural ? "This changes answer choices, so it is not drawn on the phone. Copy it and paste it into RedJade yourself."
      : ctx.offscreen(entry) ? "This text is not on a phone screen (the survey title, for example), so it cannot be previewed. Copy it into RedJade yourself."
      : picked === "original" ? "Your original stays in the preview."
        : ctx.blocked(entry) ? "Another fix already changes this text in the preview, so this one is not shown."
          : "Shown on the phone under With fixes.";
    return h("fieldset", { class: `choice${f.structural ? " pre" : ""}` },
      h("legend", null, "Which version is better?"),
      f.source === "ai" && h("p", { class: "ai-note" }, "AI-written. Check it before you use it."),
      radio("original", f.current_text ? "Your original" : "Leave as is", original),
      choices.map((c) => radio(c.value, c.label, version(c))),
      h("div", { class: "actions" },
        h("button", { type: "button", class: "btn", disabled: !chosen, "data-fk": `copy-${key}`, "aria-label": `Copy suggested text for issue ${n}`, onclick: () => chosen && ctx.onCopy(chosen.text, msg) }, "Copy suggested text"),
        h("span", { class: "note" }, note)),
      msg);
  }

  function card(entry, ctx) {
    const { f, key } = entry, selected = ctx.selected === key;
    return h("article", { class: `card ${f.severity}${selected ? " selected" : ""}`, id: `card-${key}` },
      chips(entry, ctx),
      h("h3", null, h("button", { type: "button", class: "card-head", "data-fk": `card-${key}`, "aria-pressed": String(selected), onclick: () => ctx.onSelect(key) }, f.headline)),
      h("p", { class: "why" }, f.member_impact),
      h("p", { class: "fix" }, h("strong", null, "How to fix: "), f.explanation),
      SC.choicesOf(f).length ? choiceBlock(entry, ctx) : null);
  }

  function areaRow(id, d, ctx) {
    const unchecked = Object.values(ctx.data.criteria)
      .filter((c) => c.dimension === id && ctx.review.unchecked.includes(c.title)).reduce((sum, c) => sum + c.points, 0);
    const checked = d.possible - unchecked, earned = d.earned - unchecked, pct = (x) => `${(x / d.possible) * 100}%`;
    return h("li", null, h("span", null, d.name),
      h("span", { class: "bar", "aria-hidden": "true" },
        h("i", { class: "got", style: `width:${pct(earned)}` }), h("i", { class: "lost", style: `width:${pct(checked - earned)}` }),
        h("i", { class: "wait", style: `width:${pct(unchecked)}` })),
      h("span", { class: "num" }, checked ? `${earned.toFixed(1)} of ${checked} checked` : "Not checked yet", unchecked && checked ? `, ${unchecked} waiting` : ""));
  }

  /** What the AI step did and did not do, in plain words, so nothing unchecked reads as checked. */
  function aiDetails(ctx) {
    const ai = ctx.review.ai, titles = ctx.data.ai_batches, failed = Object.entries(ai.failed);
    return h("details", null, h("summary", null, "About the AI check"),
      h("ul", { class: "plain" },
        h("li", null, `Judge: ${ai.model}. For these sample surveys its answers were saved and reviewed by a person; this page replays them.`),
        h("li", null, `Checked ${ai.checked.length} of ${ai.checked.length + failed.length} parts: ${ai.checked.map((id) => titles[id]).join(", ") || "none"}.`),
        failed.map(([id, why]) => h("li", null, `Could not check ${titles[id]}: ${why}`)),
        h("li", null, ai.dropped.length ? `Ignored ${plural(ai.dropped.length, "claim")} the survey did not back up. Points are only lost where a finding quotes the survey.` : "Every AI finding quotes the survey word for word. None had to be discarded."),
        ai.merged.length ? h("li", null, `Merged ${plural(ai.merged.length, "overlap")} so each piece of text has one rewrite and each problem appears once.`) : null,
        h("li", null, "AI findings are marked AI. You decide what to change; nothing is edited in RedJade for you.")));
  }

  function report(ctx) {
    const { scorecard, unchecked, ai } = ctx.review;
    return h("section", { class: "report", "aria-labelledby": "report-h" },
      h("h2", { id: "report-h" }, "Report"),
      h("details", null, h("summary", null, "Score by area"),
        h("ul", { class: "areas" }, Object.entries(scorecard.by_dimension).map(([id, d]) => areaRow(id, d, ctx))),
        h("p", { class: "legend" }, h("i", { class: "got" }), " earned ", h("i", { class: "lost" }), " lost ", h("i", { class: "wait" }), " not checked yet")),
      ai ? aiDetails(ctx) : null,
      unchecked.length ? h("details", { open: true }, h("summary", null, ai ? `Not checked yet (${plural(unchecked.length, "check")})` : `Waiting on the AI step (${plural(unchecked.length, "check")})`),
        h("ul", { class: "plain" }, unchecked.map((title) => h("li", null, title)))) : null,
      h("details", null, h("summary", null, "What is working"),
        h("ul", { class: "plain" }, (scorecard.strengths.length ? scorecard.strengths : ["Nothing confirmed yet."]).map((s) => h("li", null, s)))));
  }

  SC.renderCoach = (item, ctx) => {
    const n = item.entries.length;
    const sub = n
      ? `${plural(n, "thing")} to look at ${item.page ? "on this screen" : "across the whole survey"}.`
      : ctx.review.ai ? "Nothing flagged on this screen."
        : "No issues found here. The AI step has not run yet, so tone and leading wording are not checked.";
    return [h("h2", { id: "coach-h" }, "Coach"), h("p", { class: "sub" }, sub), item.entries.map((e) => card(e, ctx)), report(ctx)];
  };
})();
