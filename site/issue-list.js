/* A navigator, never a second decision editor. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.renderIssueList = detail => Object.entries(SC.ISSUE_TIERS).map(([tier, label]) => {
    const findings = detail.review.findings.filter(f => SC.issueTier(f) === tier)
      .sort((a,b) => SC.issueLocation(a, detail.snapshot).screen - SC.issueLocation(b, detail.snapshot).screen);
    const groups = new Map();
    for (const finding of findings) {
      const key = tier === 'polish' ? finding.criterion_id : SC.issueLocation(finding,detail.snapshot).label;
      if (!groups.has(key)) groups.set(key,[]);
      groups.get(key).push(finding);
    }
    const rows = list => list.map(f => {
      const d = SC.issueDecision(f,detail), location = SC.issueLocation(f,detail.snapshot);
      return h('li',null,h('button',{type:'button',class:'issue-jump',onclick:()=>{
        window.dispatchEvent(new CustomEvent('surveycoach-focus-finding',{detail:f.fingerprint}));
        document.getElementById('coach')?.scrollIntoView({block:'start',behavior:'smooth'});
      }},h('span',{class:'issue-place'},location.label),h('strong',null,f.headline),
      h('span',{class:'issue-state'},SC.acceptedRisk(f,detail)?'Kept on purpose · accepted risk':d?.action==='pick'?'Rewrite chosen · check again to verify':'Review in context →')));
    });
    return findings.length && h('section', {class:'issue-list-group'}, h('h3', null, `${label} (${findings.length})`),
      [...groups.values()].map(group => group.length > 1
        ? h('details',{class:'issue-pattern'},h('summary',null,`${tier === 'polish' ? detail.metadata?.criteria?.[group[0].criterion_id]?.title || 'Style pattern' : SC.issueLocation(group[0],detail.snapshot).label} · ${group.length} places to review`),h('ul',null,rows(group)))
        : h('ul',null,rows(group))));
  });
})();
