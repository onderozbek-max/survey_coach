/* The fix card. One anatomy for every item: state chip and title, why it matters, the fix (paste, steps or a check),
   three actions, then Details. Decisions are saved only by an explicit action, never by looking. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.improveLocation = (f, detail) => {
    const screen = detail.screens.find(s => s.page_id === f.page_id || s.questions?.some(q => q.id === f.question_id));
    if (!screen) return 'Whole survey';
    const question = screen.questions?.find(q => q.id === f.question_id);
    const captured = detail.snapshot.pages.flatMap(p => p.questions || []).find(q => q.id === f.question_id);
    const topic = question ? captured?.text?.split(/\s+/).slice(0,5).join(' ') : screen.topic;
    const label = question?.label || screen.name;
    return `${label} · Screen ${screen.screen}${topic ? ` · ${topic}` : ''}`;
  };

  /** What the user did, in the words of the three actions. A done item is not verified until Check again. */
  const handledLine = (entry, kind) => `${SC.HANDLED[kind] || 'Done'}${kind === 'keep' && entry.keep_reason ? ` · ${SC.KEEP_REASONS[entry.keep_reason] || ''}` : ''}`;

  SC.renderImproveItem = (view, ctx) => {
    const {entry, rows} = view, queue = ctx.queue, first = rows[0]?.f, open = queue.isOpen(entry);
    const act = SC.improveActions({...ctx, originId:entry.id});
    const saved = rows[0] && ctx.decisionByFp(first.fingerprint), failure = queue.failure?.id === entry.id ? queue.failure : null;
    const paste = entry.action_kind === 'paste' && entry.has_paste && rows.length ? SC.renderPasteFix(view, ctx) : null;
    const checking = entry.action_kind === 'you_check';
    const doneButton = h('button', {type:'button', id:'mark-done', class:`btn${paste ? '' : ' btn-primary'}`, disabled:checking, 'aria-describedby':checking ? 'tick-first' : null,
      onclick:() => act(view, {kind:'done', message:'Marked done. Check again to confirm it.', build:() => ({action:'done'})})}, 'Mark done in RedJade');
    const keepPanel = SC.renderKeepPanel((reason, note) => act(view, {kind:'keep', message:'Kept as is', build:() => ({action:'keep', keep_reason:reason, reason:note})}));
    const body = paste ? paste.node : checking ? SC.renderCheckFix(view, ticked => { doneButton.disabled = !ticked; }) : first ? SC.renderStepsFix(first) : null;
    const next = queue.nextOpen(entry);
    const actions = open ? [h('div', {class:'decision-actions'},
      paste && h('button', {type:'button', id:'use-change', class:'btn btn-primary use-change', onclick:() =>
        act(view, {kind:'use', message:'Added to My changes', build:fp => ({action:'pick', picked_text:paste.textFor(rows.find(r => r.f.fingerprint === fp))})})}, 'Add to my changes'),
      doneButton,
      h('button', {type:'button', id:'keep-as-is', class:'btn keep-as-is', 'aria-expanded':'false', onclick:event => {
        if (ctx.operation.busy) return;
        keepPanel.hidden = !keepPanel.hidden;
        event.currentTarget.setAttribute('aria-expanded', String(!keepPanel.hidden));
        if (!keepPanel.hidden) keepPanel.querySelector('button').focus();
      }}, 'Keep as is…'),
      checking && h('span', {id:'tick-first', class:'sr-only'}, 'Tick I checked first.')), keepPanel]
      : h('div', {class:'fix-handled'}, SC.icon('check-circle', {size:20}),
        h('span', {class:'handled-line'}, handledLine(entry, queue.handledKind(entry)),
          saved?.reason && queue.handledKind(entry) === 'keep' ? ` — ${saved.reason}` : ''),
        h('button', {type:'button', id:'undo-decision', class:'btn-text', onclick:() => act(view, {kind:'open', message:'Back on your list', build:() => ({action:'open'}), advance:false})}, 'Undo'),
        next && h('button', {type:'button', id:'next-item', class:'btn', onclick:() => queue.select(next)}, `Next item: ${next.title} →`));
    return h('article', {class:'card fix-card selected', id:`card-${entry.id}`, 'data-entry':entry.id, 'data-action':entry.action_kind},
      h('div', {class:'fix-card-head'}, SC.stateChip(entry.state),
        rows.some(({f}) => f.source === 'ai') && h('span', {class:'pill ai', title:'Written by AI. Read it before using.'}, SC.icon('sparkle', {size:14}), 'AI suggestion')),
      h('h3', {class:'headline', id:'coach-h', tabindex:'-1'}, entry.title),
      h('p', {class:'location'}, SC.appliesTo(entry)),
      first?.member_impact && h('p', {class:'why'}, first.member_impact),
      saved?.stale_pick && h('p', {class:'stale-pick'}, 'We improved this suggestion since you chose it. Choose again.'),
      body,
      failure && h('div', {class:'fix-error', role:'alert'}, h('span', null, failure.message),
        h('button', {type:'button', id:'retry-save', class:'btn', onclick:failure.retry}, 'Try again')),
      actions,
      h('p', {class:'issue-save-status', role:'status'}),
      SC.renderFixDetails(view, ctx));
  };
})();
