/* Chapter one is the verdict (brief 4.3): headline, the survey's story, three tiles, one next step.
   Counts and states come from overview.verdict and overview.items; nothing here is computed from findings. */
(() => {
  'use strict';
  const SC = window.SC, {h, mount, $, icon} = SC;
  const types = [['community_pulse', 'Community & fun'], ['non_ihut_product', 'Product test'],
    ['ihut', 'Home-use test'], ['services_concept', 'Concept or services'], ['market_research', 'Market research']];
  const TAB_ORDER = ['must_fix', 'quick_wins', 'more'];
  let detail;
  // Wrapping and the device safe area both affect the fixed bar's real height.
  const actionSize = new ResizeObserver(entries => {
    const height = entries[0]?.target.getBoundingClientRect().height || 0;
    document.documentElement.style.setProperty('--overview-action-height', `${height + 16}px`);
  });
  document.addEventListener('focusin', event => {
    if (!matchMedia('(max-width:759px)').matches || SC.currentChapter() !== 'overview') return;
    const target = event.target, bar = document.querySelector('.overview-actions');
    if (!target.closest('#chapter-overview') || !bar || bar.contains(target)) return;
    const rect = target.getBoundingClientRect(), top = bar.getBoundingClientRect().top;
    if (rect.bottom > top - 12) window.scrollBy({top:rect.bottom - top + 12, behavior:'instant'});
  });
  SC.overviewPhoneContext = (survey, item) => ({data:window.SURVEYCOACH_DEMO, review:survey.review,
    selected:item.entries.find(entry => entry.f.severity === 'must_fix')?.key, device:390, large:false,
    total:survey.screens.length, pageId:item.page.id, plan:null, applied:() => false,
    blocked:() => false, offscreen:() => false, onPin:() => {}});
  const route = options => SC.goChapter('improve', options);

  async function update(payload, announcement) {
    if (!SC.updateSurvey) return;
    try { await SC.updateSurvey(payload); SC.say(announcement); }
    catch (error) { SC.say(error.message); }
  }

  /** Findings of one state that are still open. Curated checks have no Fix card yet (phase 2), so they are not here. */
  const openFindings = state => detail.overview.items
    .filter(item => item.kind === 'finding' && item.state === state && item.open).flatMap(item => item.fingerprints);
  /** Fix opens its tab; Improve and You check open the Fix flow on just their findings. */
  function openTile(key) {
    if (key === 'fix') return route({tab:'must_fix'});
    const state = key === 'improve' ? 'worth_improving' : 'you_check', fingerprints = openFindings(state);
    if (fingerprints.length) return route({fingerprints});
    // Nothing the Fix flow can show: point at the card that lists them.
    const card = detail.overview.signals.find(signal => signal.items.some(item => item.open && item.state === state));
    const node = card && document.querySelector(`#signals [data-signal=${card.id}]`);
    node?.scrollIntoView({block:'center', behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    node?.focus({preventScroll:true});
    SC.say(node ? `Showing ${SC.STATES[state].label.toLowerCase()} in ${card.name}.` : 'Nothing to open.');
  }
  const startOptions = () => {
    const tab = TAB_ORDER.find(name => { const p = SC.progressOf(detail, name); return p.done < p.total; });
    return tab ? {tab} : {};
  };
  const openSignal = signal => route({signal:signal.id, page_id:signal.navigation.pages[0], fingerprints:signal.navigation.fingerprints});

  function typeControl() {
    return h('fieldset', {id:'survey-style', disabled:!SC.updateSurvey}, h('legend', null, 'Survey type'),
      h('p', {class:'meta'}, 'The time target depends on it.'),
      h('div', {class:'survey-style-options'}, types.map(([value, label]) => h('label', null,
        h('input', {type:'radio', name:'survey-style', value, checked:(detail.survey_type || detail.snapshot.survey_type) === value,
          onchange:async event => {
            const fieldset = event.target.closest('fieldset'); fieldset.disabled = true;
            await update({survey_type:value}, 'Survey type saved');
            fieldset.disabled = false;
            if (fieldset.isConnected) SC.renderOverview(detail);
            document.querySelector(`#survey-style input[value="${value}"]`)?.focus({preventScroll:true});
          }}), label))));
  }

  function hero(overview, model) {
    const verdict = overview.verdict, ready = verdict?.kind === 'ready_for_signoff', {state, label} = SC.verdictState(verdict);
    return h('section', {class:'verdict-hero', 'aria-labelledby':'overview-h'},
      SC.stateChip(state, {label, className:'verdict-chip'}),
      h('h2', {id:'overview-h', tabindex:'-1'}, overview.headline),
      overview.subline && h('p', {id:'overview-subline'}, overview.subline),
      verdict && h('p', {id:'verdict-time', class:'verdict-time'}, icon('clock'), verdict.time.summary),
      verdict && SC.renderTiles(verdict.tiles, openTile),
      verdict && h('div', {class:'overview-actions'},
        h('button', {id:'start-improving', type:'button', class:'btn btn-primary',
          onclick:() => ready ? SC.goChapter('share') : route(startOptions())},
          ready ? 'Sign off' : `Start fixing (${SC.openCount(verdict.tiles)})`, icon('arrow-right')),
        h('button', {id:'preview-member', type:'button', class:'btn btn-secondary', disabled:!model.items.length,
          onclick:() => SC.openMemberPreview(detail)}, icon('play'), 'Play it as a member')));
  }

  SC.renderOverview = survey => {
    detail = survey;
    actionSize.disconnect();
    const overview = detail.overview;
    if (!overview) return;
    const active = document.activeElement;
    const restoreHeading = SC.currentChapter() === 'overview' && (active === document.body || active?.id === 'overview-h');
    const model = SC.buildModel(detail);
    mount($('chapter-overview'),
      hero(overview, model),
      h('h3', null, 'Member experience'),
      h('ul', {id:'signals'}, overview.signals.map(signal => SC.renderSignalCard(signal, openSignal))),
      h('h3', null, 'Energy map', SC.energyInfoButton(detail)), h('div', {id:'energy-map'}, SC.renderEnergy(detail, page_id => route({page_id}))),
      overview.strengths.length > 0 && h('section', {class:'overview-strengths'},
        h('h3', null, 'What members will like'), h('ul', {id:'strengths'}, overview.strengths.slice(0, 3).map(text => h('li', null, icon('check'), text)))),
      typeControl());
    const bar = document.querySelector('.overview-actions');
    if (bar) actionSize.observe(bar);
    if (restoreHeading) $('overview-h').focus({preventScroll:true});
  };
})();
