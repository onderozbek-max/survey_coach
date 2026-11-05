(async () => {
  "use strict";
  const SC = window.SC, { h, mount, $, say, plural, clock } = SC;
  let DATA = window.SURVEYCOACH_DEMO;
  const localParams = new URLSearchParams(location.search), localId = localParams.get("id");
  let localDetail = null;
  const decisionClient = SC.decisionClient, decisionRevisions = SC.decisionRevisions;
  if (localId && !SC.workspaceDetail && location.pathname.endsWith('/index.html')) {
    location.replace(`review.html${location.search}${location.hash}`);
    return;
  }
  if (localId) {
    try {
      const base = `/api/surveys/${encodeURIComponent(localId)}`;
      const path = localParams.get("version") ? `${base}/versions/${Number(localParams.get("version"))}` : base;
      const responses = await Promise.all([fetch("/api/metadata"), SC.workspaceDetail ? Promise.resolve({ok:true,json:async()=>SC.workspaceDetail}) : fetch(path)]);
      if (responses.some((r) => !r.ok)) throw new Error("Review unavailable. Return to My surveys.");
      const [metadata, detail] = await Promise.all(responses.map((r) => r.json()));
      if (!detail.review) throw new Error("Review is not finished. Open My surveys to check its progress.");
      localDetail = detail;
      DATA = { ...metadata, surveys: [detail] };
      // The canonical workspace owns app navigation and version controls.
    } catch (error) {
      mount($("review-status") || $("topbar"), h("span", { role: "alert" }, error.message), h("a", { href: "local.html" }, "My surveys"));
      return;
    }
  }
  const state = { survey: 0, screen: 0, mode: "current", device: 390, large: false, selected: null, choices: {} };
  let model, queue, projectionRevision = 0;
  const improveOperation = {busy:false, recovery:null};
  let comparing = false, playing = false, settingsOpen = false, toolsOpen = false;
  const playback = SC.createPlayback({
    seconds:() => survey().overview.energy.screens[pageItem().index]?.seconds || 1,
    advance:() => {
      if (pageItem().index >= model.items.length - 1) return false;
      goToPage(pageItem().index + 1); return true;
    },
    changed:value => { playing = value; if (model) renderAll(); },
  });
  function stopPlayback() { playback.pause(); }
  if (localDetail) {
    localDetail.review.findings.forEach((f, key) => {
      const decision = localDetail.decisions[f.fingerprint];
      const pick = ["keep", "original"].includes(decision?.action) ? "original" : SC.choicesOf(f).find((c) => c.text === decision?.picked_text)?.value || "open";
      if (pick) state.choices[`0:${f.fingerprint}`] = pick;
    });
  }

  const survey = () => DATA.surveys[state.survey];
  const current = () => model.order[state.screen];
  const pageItem = () => (current().page ? current() : model.items[0]);
  const draftScope = () => `${survey().id ?? state.survey}:${survey().version}`;
  /** The one selected alternative: an unsaved draft pick wins over the saved decision, for coach and phone alike. */
  const choiceOf = (key) => {
    const f = survey().review.findings[key];
    return SC.drafts.get(f, draftScope()) ?? state.choices[`${state.survey}:${f?.fingerprint}`];
  };
  const projectionKey = detail => JSON.stringify([detail.id, detail.version, detail.survey_type,
    detail.review.findings.map(f => [f.fingerprint, SC.choicesOf(f)])]);
  /** The version picked for a finding, or null for "keep my original". Bundles of answer choices are never previewed. */
  const chosen = (f, key) => (f.structural ? null : SC.chosenChoice(f, choiceOf(key) === 'open' ? undefined : choiceOf(key)));

  /** The fixes to show on the phone, in finding order. Where two fixes want the same words, the first one wins. */
  function previewPlan(forComparison = false) {
    if (!forComparison && state.mode !== "fixes") return null;
    return survey().review.findings.flatMap((f, key) => {
      const pick = f.edit_kind !== 'add_answer' && f.current_text && chosen(f, key);
      return pick ? [{ key, from: f.current_text, to: pick.text, page_id: f.page_id, question_id: f.question_id, ai: f.source === "ai" }] : [];
    }).sort((a, b) => a.ai - b.ai);     // code-made fixes are facts (a true time promise), so they go first; the sort is stable
  }

  const questionById = (id) => model.items.flatMap(item => item.page.questions).find(q => q.id === id);
  /** The original as the researcher knows it. A bundle's original includes its answer choices, so the rewrite can be compared. */
  function originalOf(entry) {
    const { f } = entry, single = f.current_text && !f.current_text.includes("\n");   // a multi-line original already has its choices
    const q = f.structural && single && questionById(f.question_id);
    return q && q.options.length ? [f.current_text, ...q.options.map((o) => o.label)].join("\n") : f.current_text;
  }

  async function copy(text, msg) {
    try {
      await navigator.clipboard.writeText(text);
      msg.textContent = "Copied. Paste it into RedJade.";
      return true;
    } catch (_) {
      msg.textContent = "Copy unavailable. Select the suggested text and copy it.";
      return false;
    }
  }

  function scrollPhoneTo(key) {
    const pinEl = document.querySelector(`#stage .phone-screen [data-pin="${key}"]`), screen = document.querySelector("#stage .phone-screen");
    if (!pinEl || !screen) return;
    const s = screen.getBoundingClientRect(), p = pinEl.getBoundingClientRect();
    screen.scrollTop += p.top - s.top - s.height / 3;   // scroll the phone only, never the page
  }

  /** One render's view of the world. "Applied" means the phone really changed: the same function decides both. */
  function context() {
    const source = survey(), sourceProjection = projectionKey(source), sourceRevision = projectionRevision;
    const page = pageItem().page, plan = previewPlan(), hits = plan ? SC.hitsOn(page, plan) : new Set();
    const texts = SC.pageTexts(page);
    const picked = (entry) => state.mode === "fixes" && !!chosen(entry.f, entry.key);
    const onPhone = (f) => texts.some((t) => t.includes(f.current_text));     // the survey title, say, is on no phone screen
    const applied = (entry) => picked(entry) && (entry.f.current_text ? hits.has(entry.key) : true);
    const blocked = (entry) => picked(entry) && !!entry.f.current_text && onPhone(entry.f) && !hits.has(entry.key);
    const offscreen = (entry) => picked(entry) && !!entry.f.current_text && !onPhone(entry.f);
    return {
      data: DATA, review: survey().review, selected: state.selected, device: state.device, large: state.large,
      total: model.items.length, pageId: page.id, plan, applied, blocked, offscreen, choiceOf, originalOf,
      onPin: key => { queue.focus(survey().review.findings[key].fingerprint); document.querySelector('#coach h3')?.focus(); },
      onSelect: key => queue.focus(survey().review.findings[key].fingerprint),
      isCurrent: () => sourceRevision === projectionRevision && sourceProjection === projectionKey(survey()),
      version:source.version,
      onFocusFinding: fp => { queue.focus(fp); renderAll(); },
      decisionOf: key => source.decisions[source.review.findings[key]?.fingerprint],
      onKeep: (key, reason) => context().onChoose(key, 'original', reason),
      onChoose: (key, value, reason) => {
        const f = source.review.findings[key];
        if (!f || sourceProjection !== projectionKey(survey())) return Promise.resolve(false);
        const picked = SC.chosenChoice(f, value);
        return saveDecision(f.fingerprint, {action:picked ? 'pick' : reason ? 'keep' : 'original',
          picked_text:picked?.text || null, reason:reason || '', manual_done:false}, source.version);
      },
      draftOf: f => SC.drafts.get(f, draftScope()),
      onDraft: (key, value) => { SC.drafts.set(survey().review.findings[key], draftScope(), value); redrawStage(); },
      onRestore: (fp, prior, version) => saveDecision(fp, prior || {action:'open'}, version),
      onCopy: copy, operation:improveOperation, onRender:renderAll,
    };
  }

  async function saveDecision(fingerprint, decision, version) {
    const detail = survey(), f = detail.review.findings.find(f => f.fingerprint === fingerprint);
    if (!f || detail.version !== version || SC.readOnly) return false;
    const choiceKey = `${state.survey}:${fingerprint}`;
    const priorChoice = state.choices[choiceKey];
    const revision = (decisionRevisions.get(f.fingerprint) || 0) + 1;
    decisionRevisions.set(f.fingerprint, revision);
    const payload = {action:decision.action, picked_text:decision.picked_text || null,
      reason:decision.reason || '', manual_done:decision.manual_done || false, client_id:decisionClient, revision};
    state.choices[choiceKey] = payload.action === 'pick'
      ? SC.choicesOf(f).find(c => c.text === payload.picked_text)?.value || 'open'
      : payload.action === 'open' ? 'open' : 'original';
    renderAll();
    try {
      let saved = payload;
      if (localDetail) {
        const response = await fetch(`/api/surveys/${encodeURIComponent(localId)}/versions/${detail.version}/decisions/${f.fingerprint}`, {
          method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload),
        });
        if (!response.ok) throw Error('Could not save');
        saved = await response.json();
      }
      if (revision !== decisionRevisions.get(f.fingerprint)) return false;
      detail.decisions[f.fingerprint] = saved;
      SC.drafts.clear(f.fingerprint);       // the saved decision is authoritative again
      if (localDetail && SC.refreshDetail) {
        try { await SC.refreshDetail(detail.version); }
        catch (_) {
          const status = $('review-status');
          if (status) { status.textContent = 'Decision saved, but the overview could not refresh. Reload to retry.'; status.dataset.tone = 'error'; }
          SC.say('Decision saved, but the overview could not refresh. Reload to retry.');
          window.dispatchEvent(new CustomEvent('surveycoach-choice-saved', {detail}));
        }
      } else window.dispatchEvent(new CustomEvent('surveycoach-choice-saved', {detail}));
      renderAll();
      return true;
    } catch (_) {
      if (revision === decisionRevisions.get(f.fingerprint)) { state.choices[choiceKey] = priorChoice; renderAll(); }
      return false;
    }
  }

  /* ---------- header ---------- */
  const stat = (value, label, tone) => h("div", { class: `stat ${tone}` }, h("dd", null, String(value)), h("dt", null, label));

  function headline(review) {
    const { readiness, open_blockers } = review.scorecard;
    const must = review.findings.filter((f) => f.severity === "must_fix").length, worth = review.findings.length - must;
    if (readiness === "needs_work") return `Needs work. Fix ${plural(must || open_blockers.length, "thing")} first.`;
    if (readiness === "ready") return 'No blockers found in what we checked.';
    if (worth) return `${plural(worth, "idea")} to consider.`;
    return review.ai && !Object.keys(review.ai.failed).length ? "Nothing to fix." : "Nothing to fix yet. The AI step still has to run.";
  }

  function renderTop() {
    const { review } = survey(), card = review.scorecard;
    const must = review.findings.filter((f) => f.severity === "must_fix").length, worth = review.findings.filter(f=>f.severity !== 'must_fix' && SC.issueTier?.(f) !== 'polish').length;
    const promised = review.promised_minutes ? `intro promises ${review.promised_minutes}` : "";
    const ai = review.ai, failed = ai ? Object.keys(ai.failed) : [];
    const waiting = !ai
      ? `${card.unchecked_points} points${card.pending_blockers.length ? ` and ${plural(card.pending_blockers.length, "launch check")}` : ""} wait on the AI step`
      : [`AI checked ${ai.checked.length} of ${ai.checked.length + failed.length} parts`,
        failed.length && `could not check ${failed.map((id) => DATA.ai_batches[id]).join(", ")}`,
        card.unchecked_points && `${card.unchecked_points} points still unchecked (${review.unchecked.join(", ")})`].filter(Boolean).join("; ");
    if (localDetail) {
      const kept = f => ['keep','original'].includes(localDetail.decisions[f.fingerprint]?.action) && !!localDetail.decisions[f.fingerprint]?.reason?.trim();
      const remaining = review.findings.filter(f => f.severity === 'must_fix' && !kept(f)).length;
      const acknowledged = review.findings.filter(f => f.severity === 'must_fix' && kept(f)).length;
      const unknown = review.unchecked.length || card.pending_blockers.length;
      mount($('topbar'),
        h('div', {class:'verdict-line'}, h('span', {class:`readiness-dot ${remaining ? 'needs_work':'ready'}`, 'aria-hidden':'true'}),
          h('strong', null, remaining ? `${remaining} must-fix ${remaining === 1 ? 'issue' : 'issues'}` : acknowledged ? 'Remaining risks acknowledged · not verified fixes' : unknown ? 'No blockers found · some checks incomplete' : 'No blockers found in what we checked'),
          h('span', {class:'verdict-limit'}, `${plural(worth,'idea')}${SC.issueCounts ? ` · ${SC.issueCounts(localDetail).polish} nice to have` : ''}`)),
        h('div', {class:'review-metrics'},
          h('span', null, survey().overview.subline), SC.renderQualityCompact(survey().quality)));
      return;
    }
    const aiBrief = !ai ? "AI check pending" : `${failed.length ? "AI partly checked" : "AI checked"}${card.unchecked_points ? `, ${card.unchecked_points} pts unchecked` : ""}`;
    mount($("topbar"),
      h("div", { class: "brand" }, "Survey", h("span", null, "Coach")),
      SC.renderQualityCompact(survey().quality),
      h("div", { class: "head-text" },
        h(SC.workspaceDetail ? "h2" : "h1", null, headline(review)),
        h("p", { class: "sub" }, `${survey().title} \u2022 ${waiting}`),
        h("p", { class: "brief" }, `${must} must-fix \u2022 ${worth} ideas \u2022 ${review.est_minutes} min \u2022 ${aiBrief}`)),
      h("dl", { class: "stats" }, stat(must, "must-fix", "red"), stat(worth, "ideas", "amber"),
        stat(`${review.est_minutes} min`, promised ? `for members, ${promised}` : "for members", "plain")),
      h("label", { class: "pick" }, h("span", null, localDetail ? "Your survey" : "Sample survey"),
        h("select", { "data-fk": "survey-picker", onchange: (e) => chooseSurvey(Number(e.target.value)) },
          DATA.surveys.map((s, i) => h("option", { value: i, selected: i === state.survey }, s.title)))));
  }

  /* ---------- stage ---------- */
  function goToPage(index) {
    state.screen = model.order.indexOf(model.items[index]);
    state.selected = current().entries.length ? current().entries[0].key : null;
    queue.screen(model.items[index].page.id);
  }

  function renderStage() {
    const item = pageItem(), s = survey(), seconds = s.timeline[item.index]?.seconds || 0;
    const changes = SC.hitsOn(item.page, previewPlan(true)).size;
    const comparison = state.mode === 'fixes'
      ? changes ? `${plural(changes, 'text change')} previewed · hypothetical, not accepted or saved.` : 'Hypothetical preview · not accepted or saved. No text replacements; suggested answers still need authoring and behavior checks in RedJade.'
      : changes ? `${plural(changes, 'text change')} available to preview. RedJade is unchanged.` : 'No text changes to preview here. See the coach for other actions.';
    $('stage').classList.toggle('comparing', comparing);
    const originalCtx = {...context(),plan:null,applied:()=>false,blocked:()=>false};
    const rewrittenCtx = {...context(),plan:previewPlan(true),applied:e=>SC.hitsOn(item.page,previewPlan(true)).has(e.key)};
    mount($("stage"),
      h("h2", { id: "stage-h", class: "sr-only" }, "Phone preview"),
      h('div', {class:'phone-controls'}, h('div', {class:'phone-settings-wrap'},
        h('button', {id:'phone-settings', type:'button', 'data-fk':'phone-settings',
          'aria-label':'Phone preview settings', 'aria-controls':'phone-settings-panel', 'aria-expanded':String(settingsOpen),
          onclick:() => { settingsOpen = !settingsOpen; renderAll(); }}, 'Aa'),
        h('div', {id:'phone-settings-panel', class:'preview-settings', hidden:!settingsOpen,
          role:'group', 'aria-label':'Phone preview settings', onkeydown:event => {
            if (event.key === 'Escape') { settingsOpen = false; renderAll(); $('phone-settings').focus(); }
          }},
          h('button', {type:'button', 'aria-pressed':String(state.large), 'data-fk':'large', onclick:() => { state.large = !state.large; renderAll(); }}, 'Large text'),
          h('label', null, 'Device size', h('select', {'aria-label':'Device size', 'data-fk':'device-size',
            onchange:event => { state.device = Number(event.target.value); renderAll(); }},
            [320,390,430].map(size => h('option', {value:size, selected:state.device === size}, `${size}px`)))))),
      h('details', {class:'preview-tools', open:toolsOpen, ontoggle:event => { toolsOpen = event.currentTarget.open; }}, h('summary', null, 'Preview tools'),
        h('button', {type:'button',disabled:!changes && !comparing,onclick:() => { comparing = !comparing; renderAll(); }}, comparing ? 'Close comparison' : 'Compare wording'),
        h('button', {type:'button',onclick:() => playing ? playback.pause() : playback.play()}, playing ? 'Pause walkthrough' : 'Play as a member'))),
      comparing ? h('div', {class:'comparison-phones'},
        h('section', {'aria-label':'Original wording'},h('h3',null,'Original'),SC.renderPhone(item,originalCtx)),
        h('section', {'aria-label':'Recommended wording'},h('h3',null,'Rewritten'),SC.renderPhone(item,rewrittenCtx))) : SC.renderPhone(item, context()),
      localDetail && h('p', {class:'preview-effect',role:'status'}, comparison.replace('See the coach','See the issues')),
      comparing && h('p', {class:'comparison-note'}, SC.previewReadingEvidence(item.page, previewPlan(true))),
      SC.workspaceDetail && h('button', {type:'button',class:'mobile-coach-link',onclick:()=>{ $('coach').scrollIntoView({block:'start',behavior:'smooth'}); $('coach-h')?.focus(); }},
        current().entries.length ? `Review ${plural(current().entries.length, 'issue')} on this screen ↓` : 'Read the coach notes ↓'),
      h("div", { class: "pager" },
        h("button", { type: "button", "data-fk": "prev", disabled: item.index === 0, onclick: () => goToPage(item.index - 1) }, "Previous screen"),
        h("button", { type: "button", "data-fk": "next", disabled: item.index === model.items.length - 1, onclick: () => goToPage(item.index + 1) }, "Next screen")),
      h("div", { class: "timing" },
        h("p", null, s.overview?.energy.path_uncertain ? SC.uncertainWalkthrough
          : `Estimated time to this screen: ${clock(seconds)} of ${clock(s.total_seconds)} on the captured path.`),
        !s.overview?.energy.path_uncertain && h("div", { class: "timebar", "aria-hidden": "true" }, h("i", { style: `left:${(seconds / s.total_seconds) * 100}%` }))));
    const screens = comparing ? [...document.querySelectorAll('.comparison-phones .phone-screen')] : [];
    for (const screen of screens) screen.addEventListener('scroll', () => {
      for (const other of screens) if (other !== screen && Math.abs(other.scrollTop - screen.scrollTop) > 2) other.scrollTop = screen.scrollTop;
    });
  }

  /** Redraw only the phone (a draft alternative changed), keeping its scroll and the coach's focus. */
  function redrawStage() {
    const top = document.querySelector('#stage .phone-screen')?.scrollTop || 0;
    renderStage();
    const screen = document.querySelector('#stage .phone-screen');
    if (screen) screen.scrollTop = top;
  }

  /* ---------- boot ---------- */
  function restoreFocus(key) {
    if (!key) return;
    const target = document.querySelector(`[data-fk="${key}"]`);
    const usable = target && !target.disabled ? target : null;
    if (usable?.closest('[hidden]')) return;
    if (usable) usable.focus({ preventScroll: true });
  }

  let lastPage = null;
  let improveDirty = true;
  function renderAll() {
    improveDirty = true;
    if (SC.currentChapter() !== 'improve') return;
    improveDirty = false;
    const active = document.activeElement, key = active && active.dataset ? active.dataset.fk : null;
    const energyPage = active?.closest('#improve-bar .energy-bar')?.dataset.page;
    const before = document.querySelector("#stage .phone-screen"), keepTop = before ? before.scrollTop : 0;
    const pageKey = `${state.survey}:${pageItem().index}`, samePage = pageKey === lastPage;
    lastPage = pageKey;
    renderTop();
    mount($('improve-bar'), queue.renderBar(state.mode, value => { state.mode = value; renderAll(); }, pageItem().page.id));
    renderStage();
    mount($("coach"), queue.render(context()));
    if (improveOperation.busy) {
      document.querySelectorAll('#coach button, #coach textarea').forEach(control => { control.disabled = true; });
      const status = document.querySelector('#coach .issue-save-status');
      if (status) status.textContent = 'Saving…';
    }
    if (SC.readOnly) {      // an unconfirmed request: decisions are read-only, previews and reading are not
      document.querySelectorAll('#coach .decision-actions button, #coach .keep-reason button, #coach #use-all, #coach textarea')
        .forEach(control => { control.disabled = true; });
      document.querySelectorAll('#coach .issue-save-status').forEach(note => { note.textContent = SC.readOnly.reason; });
    }
    if (samePage) document.querySelector("#stage .phone-screen").scrollTop = keepTop;
    else document.querySelector('#stage .phone-screen').scrollTop = 0;
    restoreFocus(key);
    if (energyPage) [...document.querySelectorAll('#improve-bar .energy-bar')].find(b => b.dataset.page === energyPage)?.focus({preventScroll:true});
  }

  function chooseSurvey(i) {
    stopPlayback(); comparing = false;
    state.survey = i;
    model = SC.buildModel(survey());
    survey().decisions ||= {};
    SC.workspaceDetail = survey();
    queue = SC.createQueue(survey(), entry => {
      if (!entry) return;
      state.screen = Math.max(0, model.order.findIndex(item => item.entries.some(e => e.key === entry.key)));
      state.selected = entry.key;
    }, renderAll);
    SC.renderOverview(survey());
    state.mode = "current";
    const start = model.start;
    state.screen = model.order.indexOf(start);
    state.selected = start.entries.length ? start.entries[0].key : null;
    queue.start();
    say(`Showing the sample survey: ${survey().title}. ${SC.READINESS[survey().review.scorecard.readiness]}.`);
  }

  if (!localDetail && window.SURVEYCOACH_LOCAL) {
    document.body.insertBefore(h("nav", { class: "local-nav", "aria-label": "Private workspace" }, h("a", { href: "local.html" }, "Open My surveys — requires the local SurveyCoach server")), $("workspace"));
  }
  window.addEventListener('surveycoach-focus-finding', event => {
    queue.focus(event.detail);
    SC.goChapter('improve');
    renderAll();
  });
  window.addEventListener('surveycoach-screen', event => {
    const item = model.items.find(item => item.page.id === event.detail);
    if (!item) return;
    state.screen = model.order.indexOf(item);
    queue.screen(event.detail);
  });
  window.addEventListener('surveycoach-decisions', event => {
    if (!localDetail) return;
    localDetail.decisions = event.detail.decisions;
    localDetail.review.findings.forEach((f, key) => {
      const decision = localDetail.decisions[f.fingerprint];
      const value = ['keep','original'].includes(decision?.action) ? 'original' : SC.choicesOf(f).find(c => c.text === decision?.picked_text)?.value || 'open';
      if (value) state.choices[`0:${f.fingerprint}`] = value;
      else delete state.choices[`0:${f.fingerprint}`];
    });
    renderAll();
  });
  if (!DATA?.surveys?.[0]?.snapshot?.pages?.length) {
    mount($('stage'), h('p', {role:'status'}, 'No captured screens. Review the available findings and coverage below.'));
    return;
  }
  window.addEventListener('surveycoach-detail-updated', event => {
    if (projectionKey(event.detail) !== projectionKey(survey())) projectionRevision++;
    localDetail = event.detail;
    DATA.surveys[state.survey] = localDetail;
    model = SC.buildModel(localDetail);
    SC.workspaceDetail = localDetail;
    // Reconcile saved previews by identity, never by yesterday's array position.
    state.choices = {};
    localDetail.review.findings.forEach(f => {
      const d = localDetail.decisions[f.fingerprint];
      state.choices[`${state.survey}:${f.fingerprint}`] = ['keep','original'].includes(d?.action) ? 'original'
        : d?.action === 'pick' && !d.stale_pick ? SC.choicesOf(f).find(c => c.text === d.picked_text)?.value || 'open' : 'open';
    });
    state.screen = Math.min(state.screen, model.order.length - 1);
    queue.update(localDetail);
    renderAll();
  });
  window.addEventListener('surveycoach-chapter', event => {
    if (event.detail.name === 'improve' && Object.keys(event.detail.options || {}).length) {
      const options = event.detail.options;
      SC.improveFilter = options;
      queue.options(options);
      if (options.page_id) {
        const item = model.items.find(item => item.page.id === options.page_id);
        if (item) state.screen = model.order.indexOf(item);
      }
      improveDirty = true;
    }
    if (event.detail.name !== 'improve') {
      if (playing) { stopPlayback(); improveDirty = true; }
      return;
    }
    if (improveDirty) renderAll();
  });
  chooseSurvey(0);
  SC.reviewReady = true;
})();
