(() => {
  "use strict";
  const SC = window.SC;
  const { h } = SC;
  const SCALE_CRITERIA = ["4.4", "6.3"];

  /** `field` is the address SC.fixField gave the fix (stem, help, option:N, scale, page): a rewrite lands only there. */
  const fixedText = (text, ctx, field) => (ctx.plan ? SC.applyFixes(text, ctx.plan, null, { page_id: ctx.pageId, question_id: ctx.questionId, field }) : text);
  const scalePoints = (scale) => Array.from({ length: scale.points }, (_, i) => (scale.points === 11 ? i : i + 1));
  const dimensions = (m) => m.rendered_w > 0 && m.rendered_h > 0
    ? [m.rendered_w, m.rendered_h] : [m.natural_w, m.natural_h];

  /** An annotation in the block's right gutter, never in the member's sentence. */
  function marker(entry, ctx) {
    const tier = entry.f.severity === 'must_fix' ? 'Must-fix' : 'Worth improving';
    return h("button", {
      type: "button", "data-fk": `pin-${entry.key}`, "data-pin": entry.key,
      class: `phone-marker ${entry.f.severity}${ctx.selected === entry.key ? " on" : ""}`,
      "aria-label": `${tier}: ${entry.f.headline}`,
      onclick: () => ctx.onPin(entry.key),
    }, h('span', {'aria-hidden':'true'}, '!'));
  }

  const flaggedBlock = (copy, entries, ctx) => h('div', {class:'phone-marked-block'},
    h('div', {class:'phone-block-copy'}, copy),
    h('div', {class:'phone-gutter'}, entries.map(entry => marker(entry, ctx))));

  /** Highlight only the evidence; controls live outside the text flow. */
  function marked(text, entries, ctx) {
    const parts = [];
    let rest = text;
    for (const entry of entries) {
      const phrase = entry.f.highlight;
      const at = phrase && !ctx.applied(entry) ? rest.toLowerCase().indexOf(phrase.toLowerCase()) : -1;
      if (at < 0) continue;
      parts.push(rest.slice(0, at), h("mark", { class: entry.f.severity }, rest.slice(at, at + phrase.length)));
      rest = rest.slice(at + phrase.length);
    }
    return [...parts, rest];
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
    const sourceKnown = m.loaded !== false && m.natural_w > 0 && m.natural_h > 0;
    const landscape = sourceKnown ? m.natural_w > m.natural_h : known && width > height;
    const orientation = m.loaded === false || !known ? "Orientation unknown" : landscape ? "Landscape" : (sourceKnown ? m.natural_w < m.natural_h : width < height) ? "Portrait" : "Square";
    const box = h("div", { class: `media${m.loaded === false ? " broken" : ""}`, role: "img",
      "aria-label": `${label}: ${orientation}, image placeholder${m.loaded === false ? ", loading not verified by reader" : ""}`,
      style: known ? `aspect-ratio:${width} / ${height};height:auto;min-height:0` : "min-height:100px" },
      h("span", null, `${orientation} · Image placeholder`, h("br"), m.loaded === false ? "Reader could not verify image loading" : label));
    const note = h("p", { class: "image-reminder" },
      h("strong", null, landscape ? "Check on mobile: " : !known ? "Check image size on mobile: " : "Image preview: "),
      m.loaded === false ? "Check this screen in the actual survey on a phone. If it also fails there, check the link and re-upload it. If it loads slowly, try a smaller file with readable detail. If it works, report a reader capture issue."
        : landscape ? "This horizontal image may be hard to read on a phone. Review the actual survey on a mobile device for tiny content, cropping or distortion. Orientation alone is not a failure."
        : "Placeholder only—not the actual image. Verify the image in the survey on a mobile device.");
    const mine = entries.filter((e) => e.f.element_id && e.f.element_id === m.element_id);
    // Controls sit outside the image: role=img descendants are not interactive.
    return flaggedBlock(h('div', {class:'media-wrap'}, box, note), mine, ctx);
  }

  function optionList(q, by, mine, ctx) {
    const hidden = q.options_below_fold || 0, items = [];
    q.options.forEach((o, i) => {
      if (hidden && i === q.options.length - hidden) items.push(h("li", { class: "fold" }, "Below the fold on a phone"));
      items.push(h("li", null, flaggedBlock([
        o.media ? mediaBox(o.media, mine, ctx) : null, h("span", null, fixedText(o.label, ctx, `option:${i}`)),
      ], by.option.filter((e) => e.f.highlight === o.label), ctx)));
    });
    items.push(...suggestedAnswers(mine, ctx));
    const kinds = [q.kind === "multi_choice" && "multi", q.options.some((o) => o.media) && "grid-opts"].filter(Boolean);
    return h("ul", { class: ["opts", ...kinds].join(" ") }, items);
  }

  function suggestedAnswers(entries, ctx) {
    return entries.filter(e => e.f.edit_kind === 'add_answer' && ctx.plan !== null
      && ctx.choiceOf(e.key) !== 'original')
      .flatMap(e => {
        const choice = SC.chosenChoice(e.f, ctx.choiceOf(e.key) === 'open' ? undefined : ctx.choiceOf(e.key));
        return choice ? [h('li', {class:'suggested-option'},
          h('span', {class:'sr-only'}, 'Suggested answer: '), h('span', null, choice.text))] : [];
      });
  }

  function scaleEnds(scale, ctx) {
    const [low, high] = fixedText(`${scale.low_label || "(no label)"}${SC.SPLIT}${scale.high_label || "(no label)"}`, ctx, 'scale').split(SC.SPLIT);
    return h("div", { class: "ends" }, h("span", null, low), h("span", null, high));
  }

  function questionBody(q, by, mine, ctx) {
    const scale = q.scale; // Scale markers share the question gutter.
    switch (q.kind) {
      case "dropdown": return [h("div", { class: "dropdown" }, h("span", null, "Select one"), h("span", null, `${q.options.length} choices`)),
        h('ul', {class:'opts'}, suggestedAnswers(mine, ctx))];
      case "text_short": case "text_long": return h("div", { class: "textbox" }, "Type your answer here");
      case "rating": case "slider":
        if (!scale) return h('p', {class:'help'}, 'Rating control not captured. Check the original survey.');
        return [h("div", { class: "scale" }, scalePoints(scale).map((n) => h("span", null, String(n)))), scaleEnds(scale, ctx)];
      case "grid_single": case "grid_multi":
        if (!scale) return h('div', {class:'textbox'}, 'Response grid · layout not captured');
        return [h("table", null,
        h("caption", null, `${scale.low_label || ""} to ${scale.high_label || ""}`),
        h("thead", null, h("tr", null, h("td", null), scalePoints(scale).map((n) => h("th", { scope: "col" }, String(n))))),
        h("tbody", null, q.rows.map((r) => h("tr", null, h("th", { scope: "row" }, r), scalePoints(scale).map(() => h("td", null, h("span", { class: "dot" })))))))];
      default:
        if (!q.options.length && q.kind === 'unknown') return h('div', {class:'unsupported-widget'},
          h('span', {'aria-hidden':'true'}, '＋'), h('strong', null, 'Response control not reconstructed'),
          h('p', null, 'This may include a photo upload or another unsupported control. See the captured screen for the original interaction.'));
        return optionList(q, by, mine, ctx);
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
      flaggedBlock(h("p", { class: "q-text" }, marked(fixedText(q.text, ctx, 'stem'), by.text, ctx)), [...by.text, ...by.scale], ctx),
      q.help_text && h("p", { class: "help" }, fixedText(q.help_text, ctx, 'help')),
      questionBody(q, by, mine, ctx),
      q.required === false && h("p", { class: "help" }, "Optional"));
  }

  /** Page-level issues on a question screen: a suggested new question once fixed, otherwise a labeled pin. */
  function pageNotes(own, ctx) {
    return own.map((e) => (ctx.applied(e) && !e.f.current_text && e.f.suggested_text && e.f.source !== "ai"
      ? h("div", { class: "q added" }, h("p", { class: "tag-new" }, "New question (suggested)"),
        h("p", { class: "q-text" }, e.f.suggested_text), h("div", { class: "textbox" }, "Type your answer here"))
      : flaggedBlock(h("p", { class: "page-note" }, e.f.headline), [e], ctx)));
  }

  function renderPage(item, ctx) {
    const { page, entries } = item, own = entries.filter((e) => !e.f.question_id);
    if (/^please correct the following errors\s*:/i.test((page.text || '').trim())) {
      return h('div', {class:'q'}, h('h3', null, 'Captured validation screen—not a survey question'),
        h('p', null, 'The earlier reader captured an upload or answer-validation error here. This is not evidence of the next survey screen. Run a fresh review to retry with the updated reader; later screens remain unverified.'));
    }
    if (page.kind === "intro") {
      return [h("h3", null, "Welcome"), flaggedBlock(h("p", { class: "intro" }, marked(fixedText(SC.cleanCopy(page.intro_text || page.text), ctx, 'page'), own, ctx)), own, ctx), h("div", { class: "next" }, "Start")];
    }
    if (page.kind !== "question") return [flaggedBlock(h("div", { class: "survey-copy" },
      h('p', null, marked(fixedText(SC.cleanCopy(page.text || page.intro_text), ctx, 'page'), own, ctx))), own, ctx),
      page.kind === 'info' && h('div', {class:'next'}, 'Next')];

    return [page.questions.map((q) => renderQuestion(q, entries, ctx)), pageNotes(own, ctx), h("div", { class: "next" }, "Next")];
  }

  SC.renderPhone = (item, ctx) => {
    ctx = ctx.plan ? { ...ctx, plan: SC.scopeFixes(ctx.plan, item.page) } : ctx;   // each rewrite gets its one field on this page
    return h("div", { class: "phone-wrap" },
      h("div", { class: `phone${ctx.large ? " large" : ""}`, style: `--w:${ctx.device}px` },
        h("div", { class: "phone-bar" }, `${item.name} · Screen ${item.index + 1} of ${ctx.total}`),
        h("div", { class: "phone-screen", tabindex: "0", role: "region", "aria-label": "Survey screen preview, scrollable" },
          (item.page.media || []).map((m) => mediaBox(m, item.entries, ctx)), renderPage(item, ctx))));
  };
})();
