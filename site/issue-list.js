/* The All screens drawer navigates canonical labels, never edits decisions. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.renderIssueList = () => []; // Workflow refreshes decisions; drawer reads current detail on open.
  SC.openScreens = detail => {
    document.getElementById('screen-drawer')?.remove();
    const opener = document.activeElement;
    const search = h('input', {type:'search','aria-label':'Search screens',placeholder:'Q label or topic words'});
    const list = h('ul', {class:'screen-list'});
    const dialog = h('dialog', {id:'screen-drawer','aria-labelledby':'screens-heading'},
      h('header', null, h('h2', {id:'screens-heading'}, 'All screens'),
        h('button', {type:'button','aria-label':'Close all screens',onclick:() => dialog.close()},'Close')), search, list);
    const render = () => SC.mount(list, detail.screens.filter(screen =>
      `${screen.name} ${screen.topic}`.toLowerCase().includes(search.value.trim().toLowerCase())).map(screen => {
      const members = detail.plan.must_fix.concat(detail.plan.quick_wins,detail.plan.more).flatMap(item => item.fingerprints);
      const findings = detail.review.findings.filter(f => members.includes(f.fingerprint) &&
        (f.page_id === screen.page_id || screen.questions?.some(q => q.id === f.question_id)));
      const must = findings.some(f => f.severity === 'must_fix');
      return h('li', null, h('button', {type:'button',class:'screen-row',onclick:() => {
        dialog.close(); window.dispatchEvent(new CustomEvent('surveycoach-screen',{detail:screen.page_id}));
        document.querySelector('#coach h3')?.focus({preventScroll:true});
      }}, h('span', {class:`screen-dot ${must ? 'must' : ''}`,'aria-hidden':'true'},SC.icon(findings.length ? 'alert' : 'check')),
        h('strong', null,screen.name), h('span', null,screen.topic),
        h('span', {class:'sr-only'}, `${findings.length} findings${must ? ', includes must-fix' : ''}`)));
    }));
    search.addEventListener('input', render);
    dialog.addEventListener('close', () => opener?.focus({preventScroll:true}));
    document.body.append(dialog); render(); dialog.showModal(); search.focus();
  };
})();
