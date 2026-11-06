/* My changes: the hand-off into RedJade. A persistent bottom sheet fed by detail.my_changes (the server decides the
   order and writes copy_text and copy_all_text; the browser only copies them). */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  let open = false;

  /** The static sample has no server to build my_changes, so it lists its own accepted picks in the same shape. */
  const sampleChanges = detail => {
    const items = (detail.queue?.items || []).flatMap(entry => entry.fingerprints.map(fp => {
      const f = detail.review.findings.find(x => x.fingerprint === fp), d = detail.decisions?.[fp];
      return f && d?.action === 'pick' && d.picked_text ? {fingerprint:fp, headline:f.headline, screen_label:SC.improveLocation(f, detail),
        field_location:f.field_location || 'RedJade', after:d.picked_text,
        copy_text:`${f.field_location || 'RedJade'}\nBefore: ${f.current_text || '(nothing: this adds a new answer)'}\nAfter: ${d.picked_text}`} : null;
    })).filter(Boolean);
    return {items, count:items.length, copy_all_text:items.map(item => item.copy_text).join('\n\n')};
  };
  SC.myChangesOf = detail => (SC.isSample ? sampleChanges(detail) : detail.my_changes) || {items:[], count:0, copy_all_text:''};

  /** The tray is fixed to the bottom of the window, so the list pads itself by the tray's own height (--tray-h): the last rows
      can always be scrolled clear of it, whether it is closed or open. */
  let trayObserver = null;
  const publishHeight = tray => {
    trayObserver?.disconnect();
    if (!window.ResizeObserver) return;
    trayObserver = new ResizeObserver(() => document.documentElement.style.setProperty('--tray-h', `${Math.ceil(tray.getBoundingClientRect().height)}px`));
    trayObserver.observe(tray);
  };

  SC.renderTray = detail => {
    const changes = SC.myChangesOf(detail);
    const panel = h('div', {id:'tray-panel', class:'tray-panel', hidden:!open},
      changes.count === 0 ? h('p', {class:'tray-empty'}, 'Nothing added yet')
        : [h('div', {class:'tray-actions'}, h('button', {type:'button', id:'tray-copy-all', class:'btn btn-primary', 'data-fk':'tray-copy-all',
            onclick:() => SC.copyWithToast(changes.copy_all_text)}, SC.icon('copy', {size:16}), 'Copy all')),
          h('ol', {class:'tray-items'}, changes.items.map((item, index) => h('li', {class:'tray-item'},
            h('div', {class:'tray-text'}, h('p', {class:'tray-where'}, item.field_location), h('p', {class:'tray-after'}, item.after)),
            h('button', {type:'button', class:'btn tray-copy', 'data-fk':`tray-copy-${index}`, 'aria-label':`Copy change ${index + 1}: ${item.field_location}`,
              onclick:() => SC.copyWithToast(item.copy_text)}, SC.icon('copy', {size:16}), 'Copy'))))]);
    const tray = h('section', {class:`tray${open ? ' is-open' : ''}`, 'aria-label':'My changes'},
      h('button', {type:'button', id:'tray-toggle', class:'tray-bar', 'data-fk':'tray-toggle', 'aria-expanded':String(open), 'aria-controls':'tray-panel', onclick:event => {
        open = !open; panel.hidden = !open;
        event.currentTarget.setAttribute('aria-expanded', String(open));
        event.currentTarget.closest('.tray').classList.toggle('is-open', open);
      }}, `My changes (${changes.count})`, SC.icon('chevron-down', {size:18})), panel);
    publishHeight(tray);
    return tray;
  };
})();
