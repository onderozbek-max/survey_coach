(async () => {
  "use strict";
  const SC = window.SC, { h, mount, $, say, plural } = SC;
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
  let comparing = false, playing = false, toolsOpen = false;
  const playback = SC.createPlayback({
    seconds:() => survey().overview.energy.screens[pageItem().index]?.seconds || 1,
    advance:() => {
      if (pageItem().index >= model.items.length - 1) return false;
      goToPage(pageItem().index + 1); return true;
    },
    changed:value => { playing = value; if (model) renderAll(); },
  });
  function stopPlayback() { playback.pause(); }
  /** What a saved decision means for the preview: a picked wording, or nothing (kept, done, open or no longer offered). */
  const choiceFromDecision = (f, d) => (d?.action === 'pick' && !d.stale_pick ? SC.choicesOf(f).find(c => c.text === d.picked_text)?.value || 'open'
    : ['keep', 'original', 'done'].includes(d?.action) ? 'original' : 'open');
  const syncChoices = (detail, scope) => {
    state.choices = {};
    detail.review.findings.forEach(f => { state.choices[`${scope}:${f.fingerprint}`] = choiceFromDecision(f, detail.decisions[f.fingerprint]); });
  };
  if (localDetail) syncChoices(localDetail, 0);
  SC.isSample = !localDetail;

  const survey = () => DATA.surveys[state.survey];
  const current = () => model.order[state.screen];
  const pageItem = () => (current().page ? current() : model.items[0]);
  const draftScope = () => `${survey().id ?? state.survey}:${survey().version}`;
  /** The preview shows only what the user has added to My changes: an accepted wording, never a suggestion nobody took. */
  const acceptedValue = f => { const value = state.choices[`${state.survey}:${f?.fingerprint}`]; return value && value !== 'open' && value !== 'original' ? value : null; };
  const choiceOf = key => acceptedValue(survey().review.findings[key]) ?? 'original';
  const projectionKey = detail => JSON.stringify([detail.id, detail.version, detail.survey_type,
    detail.review.findings.map(f => [f.fingerprint, SC.choicesOf(f)])]);
  /** The version added for a finding, or null. Bundles of answer choices are never previewed. */
  const chosen = (f) => (f.structural ? null : SC.chosenChoice(f, acceptedValue(f) ?? 'original'));

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
      decisionByFp: fp => source.decisions[fp],
      onDecide: (fingerprint, decision) => saveDecision(fingerprint, decision, source.version),
      draftOf: f => SC.drafts.get(f, draftScope()),
      onDraft: (key, value) => { SC.drafts.set(survey().review.findings[key], draftScope(), value); },
      onRestore: (fp, prior, version) => saveDecision(fp, prior || {action:'open'}, version),
      operation:improveOperation, onRender:renderAll,
    };
  }

  /** Any queue item can be decided: a finding, a curated check or the time item. Only findings change the preview. */
  async function saveDecision(fingerprint, decision, version) {
    const detail = survey(), f = detail.review.findings.find(f => f.fingerprint === fingerprint);
    const known = f || detail.queue?.items.some(entry => entry.fingerprints.includes(fingerprint));
    if (!known || detail.version !== version || SC.readOnly) return false;
    const choiceKey = `${state.survey}:${fingerprint}`;
    const priorChoice = state.choices[choiceKey];
    const revision = (decisionRevisions.get(fingerprint) || 0) + 1;
    decisionRevisions.set(fingerprint, revision);
    const payload = {action:decision.action, picked_text:decision.picked_text || null,
      reason:decision.reason || '', manual_done:decision.manual_done || false, client_id:decisionClient, revision};
    if (decision.keep_reason) payload.keep_reason = decision.keep_reason;
    if (f) state.choices[choiceKey] = choiceFromDecision(f, {...payload, action:payload.action});
    renderAll();
    try {
      let saved = payload;
      if (localDetail) {
        const response = await fetch(`/api/surveys/${encodeURIComponent(localId)}/versions/${detail.version}/decisions/${fingerprint}`, {
          method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload),
        });
        if (!response.ok) throw Error('Could not save');
        saved = await response.json();
      }
      if (revision !== decisionRevisions.get(fingerprint)) return false;
      detail.decisions[fingerprint] = saved;
      if (f) SC.drafts.clear(fingerprint);       // the saved decision is authoritative again
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
      if (f && revision === decisionRevisions.get(fingerprint)) { state.choices[choiceKey] = priorChoice; renderAll(); }
      return false;
    }
  }

  /* ---------- verdict line ---------- */
  /** The sample site's bar above the phone: the verdict in the four-state language. Review pages have the header instead. */
  function renderTop() {
    const top = $('topbar');
    if (!top) return;
    const {verdict, headline} = survey().overview, status = SC.verdictState(verdict);
    mount(top, SC.stateChip(status.state, {label: status.label}),
      h('p', {class:'verdict-line'}, h('strong', null, headline), verdict && ` · ${verdict.time.label}`),
      !localDetail && h('label', {class:'pick'}, h('span', null, 'Sample survey'),
        h('select', {'data-fk':'survey-picker', onchange:e => chooseSurvey(Number(e.target.value))},
          DATA.surveys.map((s, i) => h('option', {value:i, selected:i === state.survey}, s.title)))));
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
    $('stage').classList.toggle('comparing', comparing);
    const originalCtx = {...context(),plan:null,applied:()=>false,blocked:()=>false};
    const rewrittenCtx = {...context(),plan:previewPlan(true),applied:e=>SC.hitsOn(item.page,previewPlan(true)).has(e.key)};
    mount($("stage"),
      h("h2", { id: "stage-h", class: "sr-only" }, "Phone preview"),
      SC.phoneTools({open:toolsOpen, onToggle:open => { toolsOpen = open; }, device:state.device, onDevice:size => { state.device = size; renderAll(); },
        changes, comparing, onCompare:() => { comparing = !comparing; renderAll(); }, playing, onPlay:() => playing ? playback.pause() : playback.play(), onRender:renderAll}),
      comparing ? h('div', {class:'comparison-phones'},
        h('section', {'aria-label':'Original wording'},h('h3',null,'Original'),SC.renderPhone(item,originalCtx)),
        h('section', {'aria-label':'Recommended wording'},h('h3',null,'Rewritten'),SC.renderPhone(item,rewrittenCtx))) : SC.renderPhone(item, context()),
      localDetail && SC.previewLine({fixesMode:state.mode === 'fixes', changes, ghosts:SC.ghostAnswerCount(item, context())}),
      comparing && h('p', {class:'comparison-note'}, SC.previewReadingEvidence(item.page, previewPlan(true))),
      SC.workspaceDetail && h('button', {type:'button',class:'mobile-coach-link',onclick:()=>{ $('coach').scrollIntoView({block:'start',behavior:'smooth'}); $('coach-h')?.focus(); }},
        current().entries.length ? `Review ${plural(current().entries.length, 'issue')} on this screen ↓` : 'Read the coach notes ↓'),
      h("div", { class: "pager" },
        h("button", { type: "button", "data-fk": "prev", disabled: item.index === 0, onclick: () => goToPage(item.index - 1) }, "Previous screen"),
        h("button", { type: "button", "data-fk": "next", disabled: item.index === model.items.length - 1, onclick: () => goToPage(item.index + 1) }, "Next screen")),
      SC.phoneTimeline({seconds, total:s.total_seconds, uncertain:!!s.overview?.energy.path_uncertain}));
    const screens = comparing ? [...document.querySelectorAll('.comparison-phones .phone-screen')] : [];
    for (const screen of screens) screen.addEventListener('scroll', () => {
      for (const other of screens) if (other !== screen && Math.abs(other.scrollTop - screen.scrollTop) > 2) other.scrollTop = screen.scrollTop;
    });
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
    if (state.mode === 'fixes' && SC.myChangesOf(survey()).count === 0) state.mode = 'current';   // nothing left to show
    mount($('improve-bar'), queue.renderBar(state.mode, value => { state.mode = value; renderAll(); }));
    mount($('fix-queue'), h('h2', {class:'sr-only'}, 'Fix list'), queue.renderList());
    renderStage();
    mount($("coach"), queue.render(context()));
    mount($('my-changes'), SC.renderTray(survey()));
    if (improveOperation.busy) {
      document.querySelectorAll('#coach button, #coach textarea, #coach input').forEach(control => { control.disabled = true; });
      const status = document.querySelector('#coach .issue-save-status');
      if (status) status.textContent = 'Saving…';
    }
    if (SC.readOnly) {      // an unconfirmed request: decisions are read-only, previews and reading are not
      document.querySelectorAll('#coach .decision-actions button, #coach .keep-reason button, #coach .keep-reason textarea, #coach .fix-handled button, #coach .fix-check input')
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
    queue = SC.createQueue(survey(), target => {
      const found = target?.key != null ? model.order.findIndex(item => item.entries.some(e => e.key === target.key))
        : model.order.findIndex(item => item.page?.id === target?.page_id);
      if (found >= 0) state.screen = found;
      state.selected = target?.key ?? null;
    }, renderAll, {persist:!localDetail});
    SC.renderOverview(survey());
    state.mode = "current";
    const start = model.start;
    state.screen = model.order.indexOf(start);
    state.selected = start.entries.length ? start.entries[0].key : null;
    queue.start();
    if (!localDetail) SC.renderHeader(survey(), {recheck:false});
    say(`Showing the sample survey: ${survey().title}. ${survey().overview.headline}.`);
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
    syncChoices(localDetail, 0);
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
    syncChoices(localDetail, state.survey);
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
