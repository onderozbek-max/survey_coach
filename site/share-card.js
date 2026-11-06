/* The review summary card and the Slack post (brief 4.7). Everything shown here comes from the server's payload:
   detail.share (the post, the link and the shared `facts`), detail.overview (the verdict chip) and detail.signoff.
   The facts are the same ones the post and the downloadable summary are written from, so the three cannot disagree;
   nothing is rebuilt in the browser, and the survey's own address (snapshot.source_url) is never read. */
(() => {
  'use strict';
  const SC = window.SC, {h, plural} = SC;

  /** "Nov 5, 2026". SQLite stamps have no zone marker; the server's sign-off stamps end in Z. */
  SC.dateLabel = stamp => {
    const text = String(stamp || '');
    const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(text) ? text : text.replace(' ', 'T') + 'Z');
    return Number.isFinite(date.getTime()) ? date.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'}) : '';
  };

  const checkedAt = detail => detail.created_at || detail.versions?.find(v => v.version === detail.version)?.created_at;

  const row = (label, ...value) => [h('dt', null, label), h('dd', null, value)];

  /** One list of the card: a heading with its count, then the rows (or one quiet line when there are none). */
  const group = (label, rows, empty) => [h('h4', null, `${label} (${plural(rows.length, 'item')})`),
    rows.length ? h('ul', {class: 'you-check-list', 'aria-label': label}, rows) : h('p', {class: 'quiet'}, empty)];

  const item = (icon, title, where, note) => h('li', null, SC.stateIcon(icon),
    h('div', null, h('strong', null, title), where ? h('span', {class: 'where'}, ` · ${where}`) : null, note ? h('p', {class: 'who-when'}, note) : null));

  const doneNote = check => ['Done', check.who, check.at && SC.dateLabel(check.at)].filter(Boolean).join(' · ');

  SC.renderReviewCard = detail => {
    const facts = detail.share?.facts, verdict = detail.overview?.verdict, share = detail.share || {};
    if (!facts) return h('section', {id: 'review-card', class: 'review-card'}, h('h3', null, 'Review summary'),
      h('p', {class: 'quiet'}, 'The review summary is ready once a check has finished.'));
    const state = SC.verdictState(verdict), open = facts.open;
    return h('section', {id: 'review-card', class: 'review-card', 'aria-labelledby': 'review-card-h'},
      h('h3', {id: 'review-card-h'}, 'Review summary'),
      h('dl', {class: 'review-facts'},
        row('Survey', facts.name),
        row('Version', `v${facts.version}`),
        row('Link', share.link ? h('code', {class: 'test-link'}, share.link) : 'No link on file'),
        row('Verdict', SC.stateChip(state.state, {label: state.label}), h('span', {class: 'headline'}, facts.verdict.headline)),
        row('Open', open.text, open.total ? ` · ${open.handled} of ${open.total} handled` : ''),
        row('Time', verdict?.time?.label || 'Not measured'),
        row('Checked', SC.dateLabel(checkedAt(detail)) || 'Date unknown')),
      group('Checked by hand', facts.checked_by_hand.map(c => item('looks_good', c.title, c.where, doneNote(c))), 'Nothing ticked by hand yet.'),
      facts.still_to_check.length ? group('Still to check', facts.still_to_check.map(c => item('you_check', c.title, c.where, 'Still to check'))) : null,
      facts.kept.length ? group('Kept on purpose', facts.kept.map(k => item('looks_good', k.headline, k.where, `Kept${k.reason ? `: ${k.reason}` : ''}`))) : null);
  };

  /** Hero action: one primary button, the exact post below it, Download as the quiet second choice. */
  SC.renderSlackPost = detail => {
    const post = detail.share?.slack_post, url = detail.share?.summary_url;
    const copy = h('button', {id: 'copy-slack', type: 'button', class: 'btn btn-primary', disabled: !post,
      onclick: () => SC.copyWithToast(post)}, SC.icon('copy'), 'Copy Slack post');
    const download = h('a', {id: 'download-summary', class: 'btn btn-secondary',
      href: url || `/api/surveys/${encodeURIComponent(detail.id)}/versions/${detail.version}/summary?download=1`}, SC.icon('download'), 'Download summary');
    return h('section', {id: 'slack-section', class: 'slack-section', 'aria-labelledby': 'slack-h'},
      h('h3', {id: 'slack-h'}, 'Share with your team'),
      h('div', {class: 'share-actions'}, copy, download),
      post ? h('pre', {id: 'slack-post', class: 'slack-post', tabindex: '0', role: 'region', 'aria-label': 'Slack post preview, read only'}, post)
        : h('p', {class: 'quiet'}, 'The Slack post is ready once a check has finished.'));
  };
})();
