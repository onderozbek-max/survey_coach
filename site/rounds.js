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
  /** Versions only exist once there are two. Version 1 alone has nothing to compare, so it renders nothing (D16). */
  SC.renderRounds = (detail, surveyId) => {
    const changes = detail.round_changes, versions = detail.versions || [{version:detail.version}];
    if (detail.version < 2 && versions.length < 2) return [];
    return [h('h3', null, detail.version > 1 ? `Since version ${detail.version - 1}` : 'Versions'),
      h('nav', {class:'round-timeline', 'aria-label':'Review versions'}, h('ol', null, versions.map(v =>
        h('li', null, h('a', {href:`review.html?id=${encodeURIComponent(surveyId)}&version=${v.version}#share`, 'aria-current':v.version === detail.version ? 'page' : false}, `Version ${v.version}`))))),
      detail.version < 2 ? null : changes ? h('div', {class:'round-comparison'},
        h('p', null, `${list(changes.fixed).length} no longer flagged · ${list(changes.still).length} still flagged · ${list(changes.new).length} new · ${list(changes.uncertain).length} uncertain`),
        h('p', {class:'note'}, 'No longer flagged is not blanket verification: checks, paths or wording may have changed. Review the evidence below.'),
        [['fixed','No longer flagged'], ['still','Still flagged'], ['new','New this version'], ['uncertain','Not comparable / uncertain']].map(([key,label]) =>
          list(changes[key]).length > 0 ? h('details', null, h('summary', null, `${label} (${changes[key].length})`),
            h('ul', null, changes[key].map(item => h('li', null, describe(item, detail),
              (item.resolution || item.reason) && h('p', null, item.resolution || item.reason),
              (item.old_wording || item.before_text) && h('blockquote', null, `Before: ${item.old_wording || item.before_text}`),
              (item.new_wording || item.after_text) && h('blockquote', null, `Now: ${item.new_wording || item.after_text}`))))) : null))
        : h('p', {class:'note'}, 'Detailed version comparison is not available for this review. Nothing is claimed fixed.')];
  };
  /** The change sheet is the server's My changes text: one writer, so the tray, Copy all and this sheet cannot disagree. */
  SC.renderChangeSheet = detail => {
    const text = SC.myChangesOf(detail).copy_all_text;
    return h('details', {class:'change-sheet review-details'}, h('summary', null, 'Change sheet · changes to make in RedJade'),
      h('p', {class:'note'}, 'Apply these in RedJade. Adding a change does not fix it; the next version provides fresh evidence.'),
      text ? h('pre', {tabindex:'0'}, text) : h('p', null, 'Nothing added yet.'));
  };
})();
