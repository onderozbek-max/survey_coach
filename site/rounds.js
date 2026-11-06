/* Versions on Sign off (D16). The comparison itself (fixed, still open, new, couldn't compare, and the caveat that
   "fixed" only means "no longer flagged by our checks") lives in ONE place: the Verdict page's "Since last version"
   card (version-delta.js). This step only links to it, and lists the versions so you can switch between them. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;

  /** Jump to the Verdict page's delta card and put the keyboard there. */
  const toDelta = () => addEventListener('hashchange', () => requestAnimationFrame(() => {
    const heading = document.getElementById('delta-h');
    heading?.focus();
    heading?.scrollIntoView({block: 'start'});
  }), {once: true});

  /** Nothing at all for a first version with no other version; the link only when there is a comparison to read. */
  SC.renderRounds = (detail, surveyId) => {
    const versions = detail.versions || [{version: detail.version}];
    if (detail.version < 2 && versions.length < 2) return [];
    const delta = detail.version >= 2 ? detail.version_delta : null;
    return [h('h3', null, 'Versions'),
      delta ? h('p', {class: 'delta-link'}, h('a', {id: 'delta-link', href: '#overview', onclick: toDelta}, `See what changed since v${delta.from_version}`)) : null,
      h('nav', {class: 'round-timeline', 'aria-label': 'Review versions'}, h('ol', null, versions.map(v =>
        h('li', null, h('a', {href: `review.html?id=${encodeURIComponent(surveyId)}&version=${v.version}#share`, 'aria-current': v.version === detail.version ? 'page' : false}, `Version ${v.version}`)))))];
  };
  /** The change sheet is the server's My changes text: one writer, so the tray, Copy all and this sheet cannot disagree. */
  SC.renderChangeSheet = detail => {
    const text = SC.myChangesOf(detail).copy_all_text;
    return h('details', {class:'change-sheet review-details'}, h('summary', null, 'Change sheet · changes to make in RedJade'),
      h('p', {class:'note'}, 'Apply these in RedJade. Adding a change does not fix it; the next version provides fresh evidence.'),
      text ? h('pre', {tabindex:'0'}, text) : h('p', null, 'Nothing added yet.'));
  };
})();
