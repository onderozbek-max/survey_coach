/* Native modal semantics: focus containment, Escape and return to the trigger. */
(() => {
  'use strict';
  const SC = window.SC, { $, h, mount, icon } = SC;
  const reviewTrigger = $('about-review');
  const content = h('div', {id:'about-content'});
  const close = h('button', {type:'button', class:'btn btn-secondary', autofocus:true}, 'Close');
  const reviewDialog = reviewTrigger && h('dialog', {id:'about-review-dialog', class:'about-sheet',
    'aria-labelledby':'about-review-h'}, close, h('h2', {id:'about-review-h'}, 'About this review'), content);
  if (reviewDialog) document.body.append(reviewDialog);
  const dialog = reviewDialog || $('data-handling-dialog');
  const trigger = reviewTrigger || $('data-handling');
  let latest, openedChapter, routeClosing = false;
  const section = (title, ...children) => h('section', null, h('h3', null, title), ...children);
  const list = items => h('ul', null, items.map(text => h('li', null, text)));
  const stops = {
    definition_captured:'Read the available survey definition.', final_control:'Reached the final survey control.',
    path_end:'Reached the end of the observed path.', screen_out:'Reached a screening exit.',
    unsupported:'Stopped at a control the reader could not safely use.', unmet_requirement:'Could not meet a page requirement.',
    time_limit:'Stopped at the time limit.', page_limit:'Stopped at the screen limit.', loop:'Stopped after a repeated screen.',
    blocked:'A safety restriction stopped the read.', reader_error:'The reader could not finish.',
    external_progression_unverified:'Could not verify progress in the survey.', same_page_change:'The screen changed without confirmed progress.',
    not_started:'The read has not started.'
  };
  function renderReview() {
    const detail = latest || SC.workspaceDetail || {}, review = detail.review || {};
    const scope = detail.presentation?.scope, coverage = detail.coverage;
    const known = scope?.review_available && Number.isInteger(scope.checked_count) && Number.isInteger(scope.total_count);
    mount(content,
      section('What we checked', h('p', null, known
        ? `${scope.checked_count} of ${scope.total_count} checks completed.` : 'Check coverage unavailable.'),
        scope?.summary && h('p', null, scope.summary),
        coverage && h('p', null, `${coverage.pages_captured} captured screens checked. ${stops[coverage.stop_reason] || 'The read stopped before all paths could be verified.'}`)),
      section("What we didn't check", list(scope?.unchecked_paths || ['Unvisited paths remain unverified.']),
        list(scope?.unchecked_checks || review.unchecked || []),
        h('p', null, 'This is not launch approval. Unchecked items remain unverified.')),
      section('Reconstructed preview', h('p', null,
        'Not a live survey. Verify layout and imagery on a phone in RedJade.')),
      section('AI suggestions', h('p', null, 'Suggestions are written by Walmart-approved AI; read before using.'),
        h('p', null, !review.ai ? 'AI wording checks have not run.'
          : Object.keys(review.ai.failed || {}).length ? 'Some AI checks did not finish.' : 'AI advice needs your judgment.'),
        (review.projection?.score_limitations || []).map(text => h('p', null, text))),
      section('Your data', h('p', null, 'Reviews and your choices are saved locally on this computer.'),
        h('p', null, 'Survey wording is sent to Walmart’s approved AI service. Never include member responses or personal information.'),
        h('p', null, 'SurveyCoach never changes RedJade. Apply chosen changes there yourself; copying does not verify a fix.'),
        h('p', null, 'Use an approved test link, not a member invitation. Opening a link may create a test participant; exclude test responses from results.')),
      !new URLSearchParams(location.search).has('id') && h('p', null, 'Sample review · fictional data.'),
      h('details', null, h('summary', null, 'Technical details & source evidence'),
        review.scorecard && h('p', null, `${Math.round(SC.scoreDisplay(review.scorecard).earned)} of ${SC.scoreDisplay(review.scorecard).checked} checked points earned. ${review.scorecard.unchecked_points} points unchecked.`),
        coverage && h('p', null, `Reader stop code: ${coverage.stop_reason}`),
        list(coverage?.warnings || []),
        coverage && detail.id && Array.from({length:coverage.pages_captured}, (_, index) => h('a', {
          href:`/api/surveys/${encodeURIComponent(detail.id)}/versions/${detail.version}/captures/${index}`,
          target:'_blank', rel:'noopener'}, `Captured screen ${index + 1} `))));
  }
  trigger?.addEventListener('click', () => {
    if (reviewDialog) renderReview();
    openedChapter = SC.currentChapter?.();
    routeClosing = false;
    dialog.showModal();
  });
  (reviewDialog ? close : $('close-data-handling'))?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('close', () => {
    if (!routeClosing) trigger.focus();
    routeClosing = false;
  });
  window.addEventListener('surveycoach-chapter', event => {
    if (!dialog?.open || event.detail.name === openedChapter) return;
    routeClosing = true;
    dialog.close(); // Router focuses the destination heading after synchronous listeners.
  });
  window.addEventListener('surveycoach-detail-updated', event => {
    latest = event.detail;
    if (reviewDialog?.open) renderReview();
  });
  dialog?.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('button, summary, a[href], input, select, textarea, [tabindex="0"]')]
      .filter(node => !node.disabled && node.getClientRects().length);
    const edge = event.shiftKey ? controls[0] : controls.at(-1);
    if (document.activeElement === edge) {
      event.preventDefault();
      (event.shiftKey ? controls.at(-1) : controls[0]).focus();
    }
  });
  for (const item of document.querySelectorAll('.narrative [data-icon]')) {
    item.prepend(icon(item.dataset.icon));
  }
})();
