/* A survey on Home (brief 4.8, first part): its real name, one verdict chip, how much is open, and Continue.
   No score, no coverage, no row of unlabeled icons. */
(() => {
  'use strict';
  const SC = window.SC, {h, icon} = SC;
  const detail = (s, status) => {
    if (status.running) return `Started ${SC.ago(s.created_at)}`;
    if (!s.tiles) return `Added ${SC.ago(s.created_at)}`;
    const open = SC.openCount(s.tiles);
    return `${open ? `${open} open` : 'Nothing open'} · checked ${SC.ago(s.created_at)}`;
  };
  SC.surveyCard = s => {
    const status = SC.surveyStatus(s);
    return h('a', {class: 'survey-card', href: `review.html?id=${encodeURIComponent(s.id)}#overview`},
      h('h3', null, SC.surveyName(s.title)),
      SC.stateChip(status.state, {label: status.label}),
      h('p', {class: 'meta'}, detail(s, status)),
      h('span', {class: 'btn btn-secondary card-action'}, 'Continue', icon('arrow-right')));
  };
})();
