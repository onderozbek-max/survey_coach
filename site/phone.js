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

  /** An annotation in the block's right gutter, never in the member's sentence. The number is the card's number;
   * severity is spoken in the name and drawn in the shape (filled = must-fix), never carried by colour alone. */
  function marker(entry, ctx) {
    const tier = entry.f.severity === 'must_fix' ? 'Must-fix' : 'Worth improving';
    return h("button", {
      type: "button", "data-fk": `pin-${entry.key}`, "data-pin": entry.key,
      class: `phone-marker ${entry.f.severity}${ctx.selected === entry.key ? " on" : ""}`,
      "aria-label": `${tier}: ${entry.f.headline}, pin ${entry.n}`,
      onclick: () => ctx.onPin(entry.key),
    }, h('span', {class:'pin-number', 'aria-hidden':'true'}, String(entry.n)));
  }

  /** The affected field only: tinted and outlined when it carries a pin. The strongest severity sets the outline style. */
  function flaggedBlock(copy, entries, ctx) {
    const worst = entries.some(entry => entry.f.severity === 'must_fix') ? 'must_fix' : entries.length ? 'worth_improving' : null;
    const focused = entries.some(entry => entry.key === ctx.selected);
    return h('div', {class:`phone-marked-block${worst ? ` field-flagged${focused ? ' on' : ''}` : ''}`, 'data-severity':worst},
      h('div', {class:'phone-block-copy'}, copy),
      h('div', {class:'phone-gutter'}, entries.map(entry => marker(entry, ctx))));
  }

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

  /** The ghost answers a screen would add (shown faded; RedJade must still be edited by hand). */
  function ghostChoices(entries, ctx) {
    return entries.filter(e => e.f.edit_kind === 'add_answer' && ctx.plan !== null && ctx.choiceOf(e.key) !== 'original')
      .flatMap(e => SC.chosenChoice(e.f, ctx.choiceOf(e.key) === 'open' ? undefined : ctx.choiceOf(e.key)) || []);
  }

  const suggestedAnswers = (entries, ctx) => ghostChoices(entries, ctx).map(choice => h('li', {class:'suggested-option'},
    h('span', {class:'sr-only'}, 'Suggested answer: '), h('span', null, choice.text)));

  const SHOWS_NO_ANSWER_LIST = ['text_short', 'text_long', 'rating', 'slider', 'grid_single', 'grid_multi'];
  /** How many ghost answers this screen draws, for the preview line (same filter as the list that draws them). */
  SC.ghostAnswerCount = (item, ctx) => (item.page.questions || [])
    .filter(q => q.kind === 'dropdown' || !(SHOWS_NO_ANSWER_LIST.includes(q.kind) || (q.kind === 'unknown' && !(q.options || []).length)))
    .reduce((sum, q) => sum + ghostChoices(item.entries.filter(e => e.f.question_id === q.id), { ...ctx, questionId: q.id }).length, 0);

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
      showsOptional(q) && h("p", { class: "help q-optional" }, "Optional"));
  }

  /** RedJade's own label may already sit in the wording the member reads. */
  const VENDOR_OPTIONAL = /(?:^|[\s(\[])optional\s*[)\]]?\s*[.:]?\s*$/i;
  /** Only a verified `false` says Optional; null and unknown say nothing, and a visible vendor label is never doubled. */
  const showsOptional = (q) => q.required === false
    && ![q.text, q.help_text, ...q.options.map((o) => o.label)].some((text) => VENDOR_OPTIONAL.test((text || "").trim()));

  const includesText = (text, phrase) => !!phrase && text.toLowerCase().includes(phrase.toLowerCase());
  /** A page-level finding whose evidence sits in the concept copy belongs to that copy, not to a floating note. */
  const inStimulus = (entry, page) => includesText(page.stimulus_text || "", entry.f.highlight || entry.f.current_text);

  /** D1: the concept copy a member reads above the question, in body type (not the bold question style). No image is invented. */
  function stimulusBlock(page, own, ctx) {
    if (!page.stimulus_text) return null;
    const mine = own.filter((e) => inStimulus(e, page));
    return h("div", { class: "stimulus" }, flaggedBlock(
      h("p", { class: "stimulus-copy" }, marked(fixedText(page.stimulus_text, ctx, "stimulus"), mine, ctx)), mine, ctx));
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
      return [h("h3", null, "Welcome"), flaggedBlock(h("p", { class: "intro" }, marked(fixedText(SC.cleanCopy(page.intro_text || page.text), ctx, 'page'), own, ctx)), own, ctx), SC.phoneNext("Start")];
    }
    if (page.kind !== "question") return [flaggedBlock(h("div", { class: "survey-copy" },
      h('p', null, marked(fixedText(SC.cleanCopy(page.text || page.intro_text), ctx, 'page'), own, ctx))), own, ctx),
      page.kind === 'info' && SC.phoneNext('Next')];

    return [stimulusBlock(page, own, ctx), page.questions.map((q) => renderQuestion(q, entries, ctx)),
      pageNotes(own.filter((e) => !inStimulus(e, page)), ctx), SC.phoneNext("Next")];
  }

  SC.renderPhone = (item, ctx) => {
    ctx = ctx.plan ? { ...ctx, plan: SC.scopeFixes(ctx.plan, item.page) } : ctx;   // each rewrite gets its one field on this page
    return SC.phoneFrame({ title: `${item.name} · Screen ${item.index + 1} of ${ctx.total}`, device: ctx.device,
      children: [(item.page.media || []).map((m) => mediaBox(m, item.entries, ctx)), renderPage(item, ctx)] });
  };
})();
