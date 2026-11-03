/* Evidence-backed effort navigation and a local, non-submitting member walkthrough. */
(() => {
  'use strict';
  const SC = window.SC, {h, clock} = SC;
  const words = text => (text || '').trim().split(/\s+/).filter(Boolean).length;
  SC.renderJourney = (items, survey, selected, plan, navigate) => {
    let previous = 0;
    const timings = items.map((item, i) => {
      const cumulative = survey.timeline[i]?.seconds ?? previous;
      const seconds = Math.max(0, cumulative - previous);
      previous = cumulative;
      return {...item, seconds, cumulative};
    });
    const max = Math.max(1, ...timings.map(item => item.seconds));
    const costly = [...timings].sort((a,b) => b.seconds-a.seconds).slice(0,3);
    return h('section', {class:'journey','aria-label':'Estimated member journey'},
      h('div', {class:'journey-heading'}, h('strong', null, 'The member journey'), h('span', null, `Estimated · ${clock(survey.total_seconds)} observed path`)),
      h('nav', {'aria-label':'Member effort by screen',class:'journey-bars'}, timings.map(item =>
        h('button', {type:'button',class:`journey-stop ${item.worst || 'clear'}${item.index === selected ? ' active':''}`,
          'aria-current':item.index === selected ? 'step':null,
          'aria-label':`${item.name}, estimated ${Math.round(item.seconds)} seconds${item.worst === 'must_fix' ? ', fix before launch':''}`,
          title:`${item.name} · about ${Math.round(item.seconds)}s`, onclick:()=>navigate(item.index)},
          h('i', {style:`height:${Math.max(10, item.seconds/max*42)}px`}), h('span', null, item.name)))),
      h('p', {class:'journey-caption'}, 'Most effort: ', costly.map((item,i) => [i ? ' · ':null,
        h('button', {type:'button',onclick:()=>navigate(item.index)}, `${item.name} (${Math.round(item.seconds)}s)`)])),
      h('p', {class:'journey-limit'}, 'Reading and interaction estimate, not measured completion or drop-off. Unvisited paths are unknown.'));
  };
  SC.previewReadingDelta = (page, plan) => {
    const count = text => words(text) * .3;
    let delta = 0;
    const compare = (text, question_id) => {
      const original = text || '';
      delta += count(original) - count(SC.applyFixes(original, plan, null, {page_id:page.id,question_id}));
    };
    compare(page.intro_text); compare(page.text);
    for (const q of page.questions || []) {
      compare(q.text,q.id); compare(q.help_text,q.id);
      if (!['dropdown','grid_single','grid_multi'].includes(q.kind)) for (const option of q.options || []) compare(option.label,q.id);
    }
    return Math.round(delta);
  };
})();
