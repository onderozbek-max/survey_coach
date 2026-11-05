/* The fix list: one ordered list, one progress ring. Presentation only; membership, order and counts come from detail.queue. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.HANDLED = Object.freeze({use:'Added to My changes', done:'Marked done, not checked yet', keep:'Kept as is'});
  SC.KEEP_REASONS = Object.freeze({intentional:'Intentional', owner_decided:'Owner decided', not_applicable:'Not applicable', other:'Other'});
  const STATE_ORDER = ['fix_before_launch', 'worth_improving', 'you_check'];
  SC.FIX_STATES = STATE_ORDER;

  /** \"Screen 5\", \"Screens 5, 7, 9\" or \"Whole survey\": where the item lives, short enough for a chip. */
  SC.screenChip = entry => {
    const screens = entry.screens || [];
    if (!screens.length) return 'Whole survey';
    if (screens.length === 1) return `Screen ${screens[0]}`;
    return screens.length > 3 ? `Screens ${screens.slice(0, 3).join(', ')} +${screens.length - 3}` : `Screens ${screens.join(', ')}`;
  };

  /** \"2 of 9 done\" with a ring that fills (the ring animates through a registered custom property). */
  SC.progressRing = (done, total) => {
    const percent = total ? Math.round(100 * done / total) : 0;
    return h('span', {class:'progress-ring', style:`--p:${percent}`, 'aria-hidden':'true'}, h('span', {class:'progress-ring-hole'}));
  };

  /** The filter chips: a pressed chip narrows the list to one state; pressing it again shows everything. */
  SC.fixFilters = ({counts, selected, onPick}) => h('div', {class:'fix-filters', role:'group', 'aria-label':'Show only'},
    STATE_ORDER.map(state => h('button', {type:'button', class:'filter-chip', 'data-state':state, 'data-fk':`filter-${state}`,
      'aria-pressed':String(selected === state), onclick:() => onPick(selected === state ? null : state)},
      SC.icon(SC.STATES[state].icon, {size:16}), SC.STATES[state].label, h('span', {class:'filter-count'}, String(counts[state] || 0)))));

  /** One row per item: state icon and words, a screen chip, the short title. A handled row shows a tick and what was done. */
  SC.fixList = ({entries, active, isOpen, handledKind, onSelect}) => {
    if (!entries.length) return h('p', {class:'meta fix-empty'}, 'Nothing in this view.');
    return h('ul', {class:'fix-rows'}, entries.map(entry => {
      const open = isOpen(entry), kind = handledKind(entry);
      const label = open ? SC.STATES[entry.state].label : SC.HANDLED[kind] || 'Done';
      return h('li', null, h('button', {type:'button', class:`fix-row${open ? '' : ' is-done'}`, 'data-fk':`fix-row-${entry.id}`,
        'data-state':open ? entry.state : 'done', 'aria-current':entry.id === active ? 'true' : null, onclick:() => onSelect(entry)},
        h('span', {class:'state-icon', 'data-state':open ? entry.state : 'done'}, SC.icon(open ? SC.STATES[entry.state].icon : 'check-circle', {size:18})),
        h('span', {class:'fix-row-text'},
          h('span', {class:'fix-row-meta'}, h('span', {class:'fix-row-state'}, label), h('span', {class:'screen-chip'}, SC.screenChip(entry))),
          h('span', {class:'fix-row-title'}, entry.title))));
    }));
  };
})();
