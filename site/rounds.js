/* Conservative round reporting: disappearance is not proof of a correction. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const list = value => Array.isArray(value) ? value : [];
  const describe = (item, detail) => {
    const f = item.current_finding || item.prior_finding || item.finding || item.current || item.previous || item;
    const finding = typeof f === 'object' ? f : detail.review.findings.find(x => x.fingerprint === f);
    return finding?.headline ? `${item.screen_label || SC.issueLocation(finding, detail.snapshot).label}: ${finding.headline}`
      : item.headline || item.label || 'Previously flagged issue (location not comparable)';
  };
  SC.renderRounds = (detail, surveyId) => {
    const changes = detail.round_changes;
    return [h('h2', null, detail.version > 1 ? `Since version ${detail.version - 1}` : 'First version'),
      h('nav', {class:'round-timeline', 'aria-label':'Review rounds'}, (detail.versions || [{version:detail.version}]).map(v =>
        h('a', {href:`review.html?id=${encodeURIComponent(surveyId)}&version=${v.version}#share`, 'aria-current':v.version === detail.version ? 'page' : false}, `Round ${v.version}`))),
      changes ? h('div', {class:'round-comparison'},
        h('p', null, `${list(changes.fixed).length} no longer flagged · ${list(changes.still).length} still flagged · ${list(changes.new).length} new · ${list(changes.uncertain).length} uncertain`),
        h('p', {class:'note'}, 'No longer flagged is not blanket verification: checks, paths or wording may have changed. Review the evidence below.'),
        [['fixed','No longer flagged'], ['still','Still flagged'], ['new','New this round'], ['uncertain','Not comparable / uncertain']].map(([key,label]) =>
          list(changes[key]).length && h('details', null, h('summary', null, `${label} (${changes[key].length})`),
            h('ul', null, changes[key].map(item => h('li', null, describe(item, detail),
              (item.resolution || item.reason) && h('p', null, item.resolution || item.reason),
              (item.old_wording || item.before_text) && h('blockquote', null, `Before: ${item.old_wording || item.before_text}`),
              (item.new_wording || item.after_text) && h('blockquote', null, `Now: ${item.new_wording || item.after_text}`)))))))
        : h('p', {class:'note'}, detail.version > 1 ? 'Detailed round comparison is not available for this review. Nothing is claimed fixed.' : 'First round: choose changes, apply them in RedJade, then check again.')];
  };
  SC.changeSheetText = detail => {
    const entries = detail.review.findings.filter(f => {
      const d = SC.issueDecision(f, detail);
      return (d?.action === 'pick' && d.picked_text) || SC.acceptedRisk(f, detail);
    }).sort((a,b) => {
      const x = SC.issueLocation(a, detail.snapshot), y = SC.issueLocation(b, detail.snapshot);
      return x.screen - y.screen || (x.question || 0) - (y.question || 0);
    });
    return entries.map(f => {
      const d = SC.issueDecision(f, detail), place = SC.issueLocation(f, detail.snapshot);
      return `${place.label} · ${place.target}\n${f.headline}\n${d.action === 'pick'
        ? f.edit_kind === 'add_answer' ? `Keep question: ${f.current_text}\nAdd answer option: ${d.picked_text}\n${f.explanation}` : `Find: ${f.current_text || 'No exact source text; locate using the guidance above'}\nReplace with: ${d.picked_text}`
        : `Keep mine: ${d.reason}\nAccepted risk, not a verified fix.`}`;
    }).join('\n\n');
  };
  SC.renderChangeSheet = detail => {
    const text = SC.changeSheetText(detail);
    return h('details', {class:'change-sheet review-details'}, h('summary', null, 'Change sheet · chosen rewrites & kept reasons'),
      h('p', {class:'note'}, 'Apply these in RedJade. Chosen does not mean fixed; the next round provides fresh evidence.'),
      text ? h('pre', {tabindex:'0'}, text) : h('p', null, 'No explicit choices yet. Recommended previews are not included.'));
  };
})();
