/* The review summary card and the Slack post (brief 4.7). Everything shown here comes from the server's payload:
   detail.share (the post and the link), detail.overview (verdict, counts, You check list) and detail.signoff. Nothing is
   rebuilt in the browser, and the survey's own address (snapshot.source_url) is never read. */
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

  /** Open counts in plain words: "1 to improve · 8 to check". Zero means nothing is left. */
  SC.openSummary = tiles => {
    const parts = [[tiles?.fix, 'to fix'], [tiles?.improve, 'to improve'], [tiles?.you_check, 'to check']]
      .filter(([count]) => count > 0).map(([count, words]) => `${count} ${words}`);
    return parts.length ? parts.join(' · ') : 'Nothing open';
  };

  const statusText = (item, record) => {
    if (item.status === 'open') return 'Still to check';
    const kept = item.status === 'kept', who = item.who || record?.name;
    const base = kept ? `Kept${item.reason ? `: ${item.reason}` : ''}` : 'Done';
    return `${base}${who ? ` · ${who}` : ''}${item.at ? ` · ${SC.dateLabel(item.at)}` : ''}`;
  };

  /** Rows for the You check list: the signed record when there is one, else the live list. */
  const youCheckRows = detail => {
    const record = detail.signoff?.record;
    if (record?.you_check?.length) return record.you_check;
    const byId = new Map((detail.overview?.items || []).map(item => [item.id, item]));
    return (detail.overview?.you_check || []).map(check => {
      const kind = byId.get(check.fingerprint)?.handled_kind;
      return {id: check.id, title: check.title, where: check.where, status: kind === 'done' ? 'done' : kind === 'keep' ? 'kept' : 'open', reason: byId.get(check.fingerprint)?.keep_reason};
    });
  };

  const row = (label, ...value) => [h('dt', null, label), h('dd', null, value)];

  SC.renderReviewCard = detail => {
    const verdict = detail.overview?.verdict, share = detail.share || {};
    const record = detail.signoff?.record, rows = youCheckRows(detail), progress = verdict?.progress;
    const state = SC.verdictState(verdict);
    const list = rows.length ? h('ul', {class: 'you-check-list', 'aria-label': 'Checked by hand'}, rows.map(item =>
      h('li', {'data-status': item.status}, SC.stateIcon(item.status === 'open' ? 'you_check' : 'looks_good'),
        h('div', null, h('strong', null, item.title), item.where ? h('span', {class: 'where'}, ` · ${item.where}`) : null,
          h('p', {class: 'who-when'}, statusText(item, record)))))) : h('p', {class: 'quiet'}, 'No hand checks on this survey.');
    return h('section', {id: 'review-card', class: 'review-card', 'aria-labelledby': 'review-card-h'},
      h('h3', {id: 'review-card-h'}, 'Review summary'),
      h('dl', {class: 'review-facts'},
        row('Survey', SC.surveyName(detail.title)),
        row('Version', `v${detail.version}`),
        row('Link', share.link ? h('code', {class: 'test-link'}, share.link) : 'No link on file'),
        row('Verdict', SC.stateChip(state.state, {label: state.label}), verdict?.headline ? h('span', {class: 'headline'}, verdict.headline) : null),
        row('Open', SC.openSummary(verdict?.tiles), progress?.total ? ` · ${progress.done} of ${progress.total} handled` : ''),
        row('Time', verdict?.time?.label || 'Not measured'),
        row('Checked', SC.dateLabel(checkedAt(detail)) || 'Date unknown')),
      h('h4', null, `Checked by hand (${plural(rows.length, 'item')})`), list);
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
