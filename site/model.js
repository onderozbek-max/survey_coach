(() => {
  "use strict";
  const SC = window.SC;
  const RANK = { must_fix: 0, worth_improving: 1 };
  SC.decisionClient = crypto.randomUUID();
  SC.decisionRevisions = new Map();
  SC.scoreDisplay = card => ({earned: card.checked_points == null ? card.score-card.unchecked_points : card.score,
    checked:card.checked_points == null ? 100-card.unchecked_points : card.checked_points});
  SC.SPLIT = " ... ";   // joins a scale's two end labels into one fixable string

  /** Read-time port of snapshot.clean_copy; captured strings and identities stay untouched. */
  SC.cleanCopy = text => {
    let copy = (text || '').replace(/\u00a0/g, ' ').trimEnd();
    while (true) {
      const trimmed = copy.replace(/(?:^|\n)[ \t]*(?:next|continue|back|start|begin|submit|finish|done)[ \t]*$/i, '').trimEnd();
      if (trimmed === copy) break;
      copy = trimmed;
    }
    return copy.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  };

  /** The versions a researcher can pick between: the AI's options, or the single code-made suggestion. */
  SC.choicesOf = (f) => (f.options && f.options.length
    ? f.options.map((o, i) => ({ value: String(i), label: o.label, text: o.text }))
    : f.suggested_text ? [{ value: "suggested", label: "Suggested", text: f.suggested_text }] : []);

  /** null means "keep the original". With no pick yet, the first (recommended) version is chosen. */
  SC.chosenChoice = (f, value) => {
    if (value === "original" || value === "open") return null;
    const list = SC.choicesOf(f);
    return list.find((c) => c.value === value) || list[0] || null;
  };

  /** Apply the chosen fixes to one string, first fix wins. `hits` collects the fixes that really changed something.
   * `fix.field` is an address from SC.fixField: a string pins the fix to that one field (stem, help, option:N, scale, page),
   * null means the target is unclear so it stays manual, and undefined (raw callers) keeps the plain page/question scope. */
  SC.applyFixes = (text, plan, hits, target = {}) => plan.reduce((t, fix) => {
    if (fix.page_id && fix.page_id !== target.page_id) return t;
    if (fix.question_id && fix.question_id !== target.question_id) return t;
    if (fix.field === null || (fix.field && target.field && fix.field !== target.field)) return t;
    if (!fix.from || !t.includes(fix.from)) return t;
    const changed = t.replace(fix.from, fix.to);
    if (hits && changed !== t) hits.add(fix.key);
    return changed;
  }, text);

  const NO_OPTION_LABELS = ["dropdown", "grid_single", "grid_multi", "text_short", "text_long", "rating", "slider"];
  const SCALE_ENDS = ["rating", "slider"];
  const VALIDATION_SCREEN = /^please correct the following errors\s*:/i;

  /** Exactly the replaceable strings the phone shows for a page, in render order (see phone.js). Raw capture text the
   * phone never displays is not here, so it can neither be "fixed" nor counted as a visible change. */
  SC.displayedFields = (page) => {
    if (page.kind !== "question") {
      const text = SC.cleanCopy(page.kind === "intro" ? page.intro_text || page.text : page.text || page.intro_text);
      return text ? [{ id: "page", text }] : [];
    }
    if (VALIDATION_SCREEN.test((page.text || "").trim())) return [];
    return (page.questions || []).flatMap((q) => [
      { id: "stem", question_id: q.id, text: q.text },
      { id: "help", question_id: q.id, text: q.help_text },
      ...(NO_OPTION_LABELS.includes(q.kind) ? [] : (q.options || []).map((o, i) => ({ id: `option:${i}`, question_id: q.id, text: o.label }))),
      ...(q.scale && SCALE_ENDS.includes(q.kind)
        ? [{ id: "scale", question_id: q.id, text: `${q.scale.low_label || "(no label)"}${SC.SPLIT}${q.scale.high_label || "(no label)"}` }] : []),
    ]).filter((field) => field.text);
  };

  /** The one field a fix targets. An exact match beats a partial one; anything not unique (duplicate labels, a word
   * shared by stem and answers) is null: it stays a manual edit instead of rewriting several places. */
  SC.fixField = (fix, page) => {
    if (!fix.from) return null;
    const mine = SC.displayedFields(page).filter((field) => (field.question_id ?? null) === (fix.question_id ?? null));
    const exact = mine.filter((field) => field.text === fix.from);
    const pool = exact.length ? exact : mine.filter((field) => field.text.includes(fix.from));
    return pool.length === 1 ? pool[0].id : null;
  };
  SC.scopeFixes = (plan, page) => plan.map((fix) => (fix.field === undefined ? { ...fix, field: SC.fixField(fix, page) } : fix));

  /** Every string the phone shows through the fixer for this page, so "fixed in preview" can be checked, not assumed. */
  SC.pageTexts = (page) => SC.displayedFields(page).map((field) => field.text);

  SC.hitsOn = (page, plan) => {
    const hits = new Set(), scoped = SC.scopeFixes(plan, page);
    SC.displayedFields(page).forEach((field) => SC.applyFixes(field.text, scoped, hits,
      { page_id: page.id, question_id: field.question_id, field: field.id }));
    return hits;
  };

  /** Which findings belong to which screen, numbered the way the phone pins and the coach cards will show them. */
  SC.buildModel = function buildModel(survey) {
    const { review } = survey;
    // Normalize a view, never the stored capture (exports omit empty lists).
    const snapshot = { ...survey.snapshot, pages: survey.snapshot.pages.map(page => ({
      ...page, questions: (page.questions || []).map(q => ({
        ...q, options: q.options || [], rows: q.rows || [], media: q.media || [],
      })),
    })) };
    const pageIndex = new Map(snapshot.pages.map((page, i) => [page.id, i]));
    const questionPage = new Map();
    snapshot.pages.forEach((page, i) => (page.questions || []).forEach((q) => questionPage.set(q.id, i)));
    const locate = (f) => questionPage.get(f.question_id) ?? pageIndex.get(f.page_id) ?? -1;

    let questionNumber = 0;
    const items = snapshot.pages.map((page, index) => {
      const first = (page.questions || [])[0];
      if (page.kind === "question") questionNumber += 1;
      const name = { intro: "Intro", info: index === 0 ? "Welcome" : `Info ${index + 1}`, thank_you: "Thank you", screen_out: "Screen-out" }[page.kind] || `Q${questionNumber}`;
      const canonical = survey.screens?.find(screen => screen.page_id === page.id);
      return { index, page, name:canonical?.name || name, topic:canonical?.topic ?? (first ? SC.clip(first.text, 34) : ""), entries: [] };
    });
    const whole = { index: -1, page: null, name: "Whole survey", topic: "Applies to every screen", entries: [] };

    review.findings.forEach((f, key) => {
      if (!f.absorbed_by) (items[locate(f)] || whole).entries.push({ f, key });
    });
    for (const item of [...items, whole]) {
      item.entries.sort((a, b) => RANK[a.f.severity] - RANK[b.f.severity] || a.key - b.key);
      item.entries.forEach((entry, i) => { entry.n = i + 1; });
      item.worst = item.entries.length ? item.entries[0].f.severity : null;
    }

    const order = whole.entries.length ? [whole, ...items] : items;
    const start = order.find((it) => it.worst === "must_fix") || order.find((it) => it.entries.length) || order[0];
    return { items, whole, order, start };
  };
})();
