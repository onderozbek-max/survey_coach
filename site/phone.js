(() => {
  "use strict";
  const SC = window.SC;
  const { h } = SC;
  const KIND = { intro: "Welcome", question: "Question", thank_you: "Thank you", screen_out: "Screen-out" };
  const SCALE_CRITERIA = ["4.4", "6.3"];

  const fixedText = (text, ctx) => (ctx.plan ? SC.applyFixes(text, ctx.plan, null, { page_id: ctx.pageId, question_id: ctx.questionId }) : text);
  const scalePoints = (scale) => Array.from({ length: scale.points }, (_, i) => (scale.points === 11 ? i : i + 1));
  const dimensions = (m) => m.rendered_w > 0 && m.rendered_h > 0
    ? [m.rendered_w, m.rendered_h] : [m.natural_w, m.natural_h];

  /** A numbered pin: the same number is on the coach card, so each problem is findable both ways. */
  function pin(entry, ctx) {
    const done = ctx.applied(entry);
    return h("button", {
      type: "button", "data-fk": `pin-${entry.key}`, "data-pin": entry.key,
      class: `pin ${done ? "done" : entry.f.severity}${ctx.selected === entry.key ? " on" : ""}`,
      "aria-label": `Issue ${entry.n}${done ? ", fixed in preview" : ""}: ${entry.f.headline}`,
      onclick: () => ctx.onPin(entry.key),
    }, String(entry.n));
  }

  /** Text with the faulty phrase marked and its pin beside it; pins with no phrase to mark go at the end. */
  function marked(text, entries, ctx) {
    const parts = [], tail = [];
    let rest = text;
    for (const entry of entries) {
      const phrase = entry.f.highlight;
      const at = phrase && !ctx.applied(entry) ? rest.toLowerCase().indexOf(phrase.toLowerCase()) : -1;
      if (at < 0) { tail.push(entry); continue; }
      parts.push(rest.slice(0, at), h("mark", { class: entry.f.severity }, rest.slice(at, at + phrase.length)), pin(entry, ctx));
      rest = rest.slice(at + phrase.length);
    }
    return [...parts, rest, tail.map((entry) => pin(entry, ctx))];
  }

  function targetOf(entry, q) {
    const f = entry.f;
    const mediaIds = [...q.media, ...q.options.map((o) => o.media)].filter(Boolean).map((m) => m.element_id);
    if (f.element_id && mediaIds.includes(f.element_id)) return "media";
    if (f.highlight && q.options.some((o) => o.label === f.highlight)) return "option";
    if (q.scale && SCALE_CRITERIA.includes(f.criterion_id)) return "scale";
    return "text";
  }

  function mediaBox(m, entries, ctx) {
    const label = m.alt || m.element_id || "Survey image";
    const [width, height] = dimensions(m), known = width > 0 && height > 0;
    const sourceKnown = m.natural_w > 0 && m.natural_h > 0;
    const landscape = sourceKnown ? m.natural_w > m.natural_h : known && width > height;
    const orientation = !known ? "Orientation unknown" : landscape ? "Landscape" : (sourceKnown ? m.natural_w < m.natural_h : width < height) ? "Portrait" : "Square";
    const box = h("div", { class: `media${m.loaded === false ? " broken" : ""}`, role: "img",
      "aria-label": `${label}: ${orientation}, image placeholder${m.loaded === false ? ", failed to load" : ""}`,
      style: known ? `aspect-ratio:${width} / ${height};height:auto;min-height:0` : "min-height:100px" },
      h("span", null, `${orientation} · Image placeholder`, h("br"), m.loaded === false ? "Image failed to load" : label));
    const note = h("p", { class: "image-reminder" },
      h("strong", null, landscape ? "Check on mobile: " : !known ? "Check image size on mobile: " : "Image preview: "),
      landscape ? "This horizontal image may be hard to read on a phone. Review the actual survey on a mobile device for tiny content, cropping or distortion. Orientation alone is not a failure."
        : "Placeholder only—not the actual image. Verify the image in the survey on a mobile device.");
    const mine = entries.filter((e) => e.f.element_id && e.f.element_id === m.element_id);
    // pins sit beside the image, not inside it: an image's children are invisible to screen readers
    return h("div", { class: "media-wrap" }, box, note, mine.map((e) => pin(e, ctx)));
  }

  function optionList(q, by, mine, ctx) {
    const hidden = q.options_below_fold || 0, items = [];
    q.options.forEach((o, i) => {
      if (hidden && i === q.options.length - hidden) items.push(h("li", { class: "fold" }, "Below the fold on a phone"));
      items.push(h("li", null, o.media ? mediaBox(o.media, mine, ctx) : null, h("span", null, fixedText(o.label, ctx)),
        by.option.filter((e) => e.f.highlight === o.label).map((e) => pin(e, ctx))));
    });
    const kinds = [q.kind === "multi_choice" && "multi", q.options.some((o) => o.media) && "grid-opts"].filter(Boolean);
    return h("ul", { class: ["opts", ...kinds].join(" ") }, items);
  }

  function scaleEnds(scale, ctx) {
    const [low, high] = fixedText(`${scale.low_label || "(no label)"}${SC.SPLIT}${scale.high_label || "(no label)"}`, ctx).split(SC.SPLIT);
    return h("div", { class: "ends" }, h("span", null, low), h("span", null, high));
  }

  function questionBody(q, by, mine, ctx) {
    const scale = q.scale, scalePins = by.scale.map((e) => pin(e, ctx));
    switch (q.kind) {
      case "dropdown": return h("div", { class: "dropdown" }, h("span", null, "Select one"), h("span", null, `${q.options.length} choices`));
      case "text_short": case "text_long": return h("div", { class: "textbox" }, "Type your answer here");
      case "rating": case "slider": return [h("div", { class: "scale" }, scalePoints(scale).map((n) => h("span", null, String(n)))), scaleEnds(scale, ctx), scalePins];
      case "grid_single": case "grid_multi": return [h("table", null,
        h("caption", null, `${scale.low_label || ""} to ${scale.high_label || ""}`),
        h("thead", null, h("tr", null, h("td", null), scalePoints(scale).map((n) => h("th", { scope: "col" }, String(n))))),
        h("tbody", null, q.rows.map((r) => h("tr", null, h("th", { scope: "row" }, r), scalePoints(scale).map(() => h("td", null, h("span", { class: "dot" }))))))), scalePins];
      default: return optionList(q, by, mine, ctx);
    }
  }

  function renderQuestion(q, entries, ctx) {
    ctx = { ...ctx, questionId: q.id };
    const mine = entries.filter((e) => e.f.question_id === q.id);
    const by = { text: [], option: [], scale: [], media: [] };
    mine.forEach((e) => by[targetOf(e, q)].push(e));
    const selected = mine.some((e) => e.key === ctx.selected);
    return h("div", { class: `q${mine.length ? " flagged" : ""}${selected ? " selected" : ""}` },
      q.media.map((m) => mediaBox(m, mine, ctx)),
      h("p", { class: "q-text" }, marked(fixedText(q.text, ctx), by.text, ctx)),
      q.help_text && h("p", { class: "help" }, fixedText(q.help_text, ctx)),
      questionBody(q, by, mine, ctx),
      q.required === false && h("p", { class: "help" }, "Optional"));
  }

  /** Page-level issues on a question screen: a suggested new question once fixed, otherwise a labeled pin. */
  function pageNotes(own, ctx) {
    return own.map((e) => (ctx.applied(e) && !e.f.current_text && e.f.suggested_text && e.f.source !== "ai"
      ? h("div", { class: "q added" }, h("p", { class: "tag-new" }, "New question (suggested)"),
        h("p", { class: "q-text" }, e.f.suggested_text), h("div", { class: "textbox" }, "Type your answer here"))
      : h("p", { class: "page-note" }, pin(e, ctx), " ", e.f.headline)));
  }

  function renderPage(item, ctx) {
    const { page, entries } = item, own = entries.filter((e) => !e.f.question_id);
    if (/^please correct the following errors\s*:/i.test((page.text || '').trim())) {
      return h('div', {class:'q'}, h('h3', null, 'Captured validation screen—not a survey question'),
        h('p', null, 'The earlier reader captured an upload or answer-validation error here. This is not evidence of the next survey screen. Run a fresh review to retry with the updated reader; later screens remain unverified.'));
    }
    if (page.kind === "intro") {
      return [h("h3", null, "Welcome"), h("p", { class: "intro" }, marked(fixedText(page.intro_text, ctx), own, ctx)), h("div", { class: "next" }, "Start")];
    }
    if (page.kind !== "question") return h("div", { class: "centered" }, h("p", null, marked(fixedText(page.text || "", ctx), own, ctx)));
    return [page.questions.map((q) => renderQuestion(q, entries, ctx)), pageNotes(own, ctx), h("div", { class: "next" }, "Next")];
  }

  SC.renderPhone = (item, ctx) =>
    h("div", { class: "phone-wrap" },
      h("div", { class: `phone${ctx.large ? " large" : ""}`, style: `--w:${ctx.device}px` },
        h("div", { class: "phone-bar" }, h("span", null, `${item.name} \u2022 screen ${item.index + 1} of ${ctx.total}`), h("span", null, KIND[item.page.kind] || item.page.kind)),
        h("div", { class: "phone-screen", tabindex: "0", role: "region", "aria-label": "Survey screen preview, scrollable" },
          (item.page.media || []).map((m) => mediaBox(m, item.entries, ctx)), renderPage(item, ctx))));
})();
