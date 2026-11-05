/* Server-calculated methodology, shown only inside the "How we check" dialogs: never on Home, Verdict or Share. */
(() => {
  'use strict';
  const SC = window.SC, {h, mount} = SC;
  let opener, openedChapter, serial = 0, dismissTooltip;
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') dismissTooltip?.();
  });
  const close = h('button', {type:'button', class:'btn btn-secondary', autofocus:true, onclick:() => dialog.close()}, 'Close');
  const heading = h('h2', {id:'quality-dialog-heading'});
  const content = h('div');
  const dialog = h('dialog', {class:'quality-dialog', 'aria-labelledby':'quality-dialog-heading'}, close, heading, content);
  document.body.append(dialog);
  dialog.addEventListener('close', () => {
    if (opener?.isConnected && opener.getClientRects().length && !opener.closest('[hidden]')) opener.focus({preventScroll:true});
    opener = null;
  });
  dialog.addEventListener('keydown', event => {
    // The explanations contain only one control. Native dialog handles Escape.
    if (event.key === 'Tab') { event.preventDefault(); close.focus(); }
  });
  window.addEventListener('surveycoach-chapter', event => {
    dismissTooltip?.();
    if (dialog.open && event.detail.name !== openedChapter) { opener = null; dialog.close(); }
  });
  function open(event, title, children) {
    opener = event.currentTarget;
    openedChapter = SC.currentChapter?.();
    heading.textContent = title;
    mount(content, ...children);
    dialog.showModal();
  }
  const p = text => h('p', null, text);
  SC.qualityMethodButton = (label = 'Quality methodology') => h('button', {
    type:'button', class:'btn-text quality-method', 'aria-haspopup':'dialog',
    onclick:event => open(event, 'Quality methodology', [
      p('Survey Quality is earned assessed applicable points / assessed applicable points × 100. Each criterion uses its existing rubric weight and assessed credit fraction; no new components are added.'),
      p('Coverage is assessed weight / applicable weight. N/A criteria are excluded; missing checks remain unknown, not passes or failures. No assessed weight means no score. Display values are rounded; they do not imply extra precision.'),
      p('The old raw score was earned points out of all 100 rubric points, including unchecked and N/A weight in its denominator. This normalized score describes assessed evidence only; compare it alongside coverage, not the old raw score.'),
      p('Provisional means applicable checks or risk checks are incomplete, or nothing is assessed. Must-fix risks are independent of the score. Even 100/100 is not readiness, launch approval, or a prediction of member outcomes.'),
      p('AI wording and flow judgments may be incomplete or wrong. Changing style refreshes local length and tone checks; it does not rerun saved AI advice. Chosen fixes and kept risks do not improve assessed quality before rechecking.')
    ])}, label);
  SC.qualityText = quality => {
    const q = quality || {}, score = q.score == null ? 'Not assessed' : `${Math.round(q.score)}/100`;
    return `Survey Quality · ${score} · ${q.provisional !== false ? 'Provisional' : 'Assessed'} · ${Math.round(q.coverage_percent || 0)}% coverage`;
  };
  SC.energyInfoButton = detail => {
    const id = `energy-tip-${++serial}`;
    let hovered = false, focused = false, dismissed = false;
    const tooltip = h('span', {id, role:'tooltip', class:'energy-tooltip', hidden:true},
      'Bar height estimates time per captured screen; colour shows cumulative effort. Uncalibrated, not measured fatigue. Activate for assumptions and route limits.');
    const hide = () => { dismissed = true; tooltip.hidden = true; };
    const refresh = () => {
      if (!hovered && !focused && !dialog.open) dismissed = false;
      tooltip.hidden = dialog.open || dismissed || !(hovered || focused);
      if (!tooltip.hidden) dismissTooltip = hide;
    };
    const button = h('button', {type:'button', class:'btn-text energy-info',
    'aria-label':'About the energy map', 'aria-haspopup':'dialog', 'aria-describedby':id,
    onclick:event => {
      hide();
      const c = detail.effort_method;
      const formula = c ? `Reading: words × ${c.seconds_per_word}s. Each screen adds ${c.page_overhead}s; each question image and each answer option with media adds ${c.image_seconds}s and each grid row adds ${c.grid_row_seconds}s.` : 'Detailed timing assumptions are unavailable for this saved review.';
      const zones = c ? `Colour uses cumulative effort: fresh below ${c.fatigue_builds_after_seconds}s and ${c.fatigue_builds_after_questions} questions; getting tiring at ${c.fatigue_builds_after_seconds}s or ${c.fatigue_builds_after_questions} questions; tiring at ${c.high_fatigue_after_seconds}s or ${c.high_fatigue_after_questions} questions.` : '';
      open(event, 'Energy map estimates', [
        p('Bar height estimates time on each captured screen, not measured respondent fatigue. Uncalibrated heuristics, not validated respondent benchmarks.'),
        p(formula), p('Question interaction adds a base plus time per answer option; values depend on question type.'),
        c && h('ul', null, c.kind_base.map(([kind, base, option]) => h('li', null, `${kind.replaceAll('_', ' ')}: ${base}s + ${option}s per option`))),
        zones && p(zones), p('Captured screens may include alternative or conditional pages. Branching can make this sequence different from an actual member route. Timing is an estimate, not observed behavior.')
      ].filter(Boolean));
    }}, 'ⓘ');
    return h('span', {class:'energy-info-wrap',
      onpointerenter:event => { if (event.pointerType === 'touch') return; hovered = true; refresh(); },
      onpointerleave:() => { hovered = false; refresh(); },
      onfocusin:() => { focused = true; refresh(); },
      onfocusout:() => { focused = false; refresh(); }}, button, tooltip);
  };
})();
