/* "Since last version" (brief 4.6): what the recheck found, from detail.version_delta. Hidden on version 1 (D16).
   Every sentence and count is served; "couldn't compare" is never dropped, and "fixed" only ever means "no longer flagged". */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;

  const where = item => h('span', {class: 'delta-where'}, item.location);
  const row = item => h('li', null, h('strong', null, item.headline), ' ', where(item));

  /** One fixed item: the headline, how we know, and what the question said before and after (when we have it). */
  const fixedItem = item => h('details', {class: 'delta-fixed-item'},
    h('summary', null, h('span', {class: 'delta-head'}, SC.icon('check-circle', {size: 16}), h('strong', null, item.headline), ' ', where(item))),
    h('p', {class: 'meta'}, item.by_rewrite ? 'Fixed with your rewrite.' : item.resolution),
    item.before != null && h('div', {class: 'delta-snippet'}, h('span', {class: 'delta-tag'}, 'Before'), h('blockquote', null, item.before)),
    item.after != null && h('div', {class: 'delta-snippet'}, h('span', {class: 'delta-tag'}, 'After'), h('blockquote', null, item.after)));

  const folded = (id, title, items) => items.length > 0 && h('details', {class: 'delta-more', 'data-bucket': id},
    h('summary', null, title), h('ul', null, items.map(row)));

  SC.renderVersionDelta = detail => {
    const delta = detail.version_delta;
    if (!delta || !(detail.version >= 2)) return null;
    const {counts} = delta;
    return h('section', {id: 'version-delta', class: 'delta-card', 'aria-labelledby': 'delta-h'},
      h('h3', {id: 'delta-h', tabindex: '-1'}, 'Since last version'),
      h('p', {class: 'delta-summary'}, h('strong', null, delta.summary)),
      h('p', {class: 'meta'}, delta.caveat),
      counts.uncertain > 0 && h('div', {class: 'delta-uncertain', role: 'group', 'aria-label': 'Could not compare'},
        h('p', null, SC.icon('eye', {size: 16}), h('strong', null, `${SC.plural(counts.uncertain, 'item')} we couldn't compare`)),
        h('ul', null, delta.uncertain.map(item => h('li', null, h('strong', null, item.headline), ' ', where(item),
          h('span', {class: 'meta'}, ` · ${item.resolution}`))))),
      counts.fixed > 0 && h('div', {class: 'delta-fixed'}, h('h4', null, `Fixed (${counts.fixed})`), delta.fixed.map(fixedItem)),
      folded('still', `Still open (${counts.still})`, delta.still),
      folded('new', `New (${counts.new})`, delta.new));
  };
})();
