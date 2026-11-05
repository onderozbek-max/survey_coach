/* Verdict page parts (brief 4.3): the three tiles and the six category cards.
   Every state, count and sentence is supplied by the server; this file only draws it. */
(() => {
  'use strict';
  const SC = window.SC, {h, icon, plural} = SC;
  const CATEGORY_ICONS = {time: 'clock', clarity: 'bubble', honest: 'scale', energy: 'route', tone: 'smile', phone: 'phone'};
  const TILES = [['fix', 'Fix', 'fix_before_launch'], ['improve', 'Improve', 'worth_improving'], ['you_check', 'You check', 'you_check']];
  const VISIBLE_ITEMS = 3;      // longer lists fold, so the six cards stay about the same height

  /** Fix / Improve / You check. A tile with nothing open is shown but cannot be pressed. */
  SC.renderTiles = (tiles, onOpen) => h('div', {id: 'plan-summary', class: 'verdict-tiles', role: 'group', 'aria-label': 'What is open'},
    TILES.map(([key, label, state]) => h('button', {type: 'button', class: 'verdict-tile', 'data-tile': key, 'data-state': state,
      disabled: tiles[key] === 0, 'aria-label': `${label}: ${tiles[key]} open`, onclick: () => onOpen(key)},
      h('span', {class: 'tile-head'}, SC.stateIcon(state), h('span', {class: 'tile-label'}, label)),
      h('span', {class: 'tile-count num', 'aria-hidden': 'true'}, String(tiles[key])))));

  const itemRow = item => h('li', {'data-open': String(item.open), 'data-state': item.state},
    SC.stateIcon(item.open ? item.state : 'looks_good'),
    h('span', {class: 'sr-only'}, item.open ? `${SC.STATES[item.state]?.label || 'Open'}: ` : 'Done: '),
    h('span', null, item.headline));

  /** One category card: state chip, one plain sentence, then its items (done ones ticked). */
  SC.renderSignalCard = (signal, onOpen) => {
    const items = signal.items || [], more = items.slice(VISIBLE_ITEMS), pages = signal.navigation?.pages || [];
    return h('li', {'data-signal': signal.id, tabindex: '-1'},
      h('div', {class: 'signal-name'}, icon(CATEGORY_ICONS[signal.id] || 'dot'), h('h4', null, signal.name.replace(' & ', ' and '))),
      SC.stateChip(signal.state, {className: 'signal-state', label: signal.label}),
      h('p', {class: 'signal-summary'}, signal.summary),
      items.length > 0 && h('ul', {class: 'signal-items'}, items.slice(0, VISIBLE_ITEMS).map(itemRow)),
      more.length > 0 && h('details', {class: 'signal-more'}, h('summary', null, `Show ${more.length} more`),
        h('ul', {class: 'signal-items'}, more.map(itemRow))),
      signal.navigation?.fingerprints.length > 0 && h('button', {type: 'button', class: 'signal-link btn-text', onclick: () => onOpen(signal)},
        pages.length ? `See ${plural(pages.length, 'screen')}` : 'See related issues'));
  };
})();
