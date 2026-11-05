/* Chapter one is the verdict (brief 4.3): headline, the survey's story, three tiles, one next step.
   Counts and states come from overview.verdict and overview.items; nothing here is computed from findings. */
(() => {
  'use strict';
  const SC = window.SC, {h, mount, $, icon} = SC;
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
  const route = options => SC.goChapter('improve', options);

  /** A tile opens the Fix flow filtered to its state; the fix list now holds the curated You check items too. */
  const TILE_STATE = {fix:'fix_before_launch', improve:'worth_improving', you_check:'you_check'};
  const openTile = key => route({state:TILE_STATE[key]});
  const startOptions = () => {
    const tab = TAB_ORDER.find(name => { const p = SC.progressOf(detail, name); return p.done < p.total; });
    return tab ? {tab} : {};
  };
  const openSignal = signal => route({signal:signal.id, page_id:signal.navigation.pages[0], fingerprints:signal.navigation.fingerprints});

  function hero(overview, model) {
    const verdict = overview.verdict, ready = verdict?.kind === 'ready_for_signoff', {state, label} = SC.verdictState(verdict);
    return h('div', {class:'verdict-hero'},
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
    const model = SC.buildModel(detail), journey = SC.renderJourney(detail, {onSelect:page_id => route({page_id})});
    mount($('chapter-overview'),
      hero(overview, model),
      SC.renderVersionDelta(detail),
      SC.renderSetupCard(detail),
      h('h3', null, 'Member experience'),
      h('ul', {id:'signals'}, overview.signals.map(signal => SC.renderSignalCard(signal, openSignal))),
      journey && h('h3', null, 'Member journey', SC.timeInfoButton(detail)),
      journey && h('div', {id:'journey'}, journey),
      overview.strengths.length > 0 && h('section', {class:'overview-strengths'},
        h('h3', null, 'What members will like'), h('ul', {id:'strengths'}, overview.strengths.slice(0, 3).map(text => h('li', null, icon('check'), text))))
    );
    const bar = document.querySelector('.overview-actions');
    if (bar) actionSize.observe(bar);
    if (restoreHeading) $('overview-h').focus({preventScroll:true});
  };
})();
