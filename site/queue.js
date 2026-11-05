/* The fix queue. Membership, order, counts and "next item" come from detail.queue (one list, built on the server).
   The browser only remembers where the user is, which state chip is pressed and what they just decided (the overlay)
   until the server confirms it. Decisions never regroup or reorder anything. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const EMPTY = {items:[], first_open_id:null, counts:{done:0, total:0, open:0, unverified:0, by_kind:{use:0, done:0, keep:0}}};
  const TAB_STATE = {must_fix:'fix_before_launch', quick_wins:'worth_improving', more:'you_check'};
  const ALIAS = {fix:'fix_before_launch', improve:'worth_improving'};
  const stateOf = options => {
    const raw = options.state ?? TAB_STATE[options.tab];
    return SC.FIX_STATES.includes(raw) ? raw : ALIAS[raw] || null;
  };

  /** `persist` is true on the static sample, which has no server to confirm a decision: the overlay then is the truth. */
  SC.createQueue = (detail, navigate, redraw, {persist = false} = {}) => {
    let active = null, view = 'card', filter = null, place = null, failure = null;
    const overlay = new Map();               // entry id -> handled kind, or 'open' after an undo
    const queueOf = () => detail.queue || EMPTY;
    const all = () => queueOf().items;
    const byId = id => all().find(entry => entry.id === id) || null;
    const isOpen = entry => (overlay.has(entry.id) ? overlay.get(entry.id) === 'open' : entry.open);
    const handledKind = entry => (overlay.has(entry.id) ? (overlay.get(entry.id) === 'open' ? null : overlay.get(entry.id)) : entry.handled_kind);
    const visible = () => all().filter(entry => !filter || entry.state === filter);
    const firstOpen = list => list.find(isOpen) || null;
    /** The next open item after this one in list order (the server's next_open_id, kept honest by the overlay). */
    const nextOpen = entry => {
      const served = entry && byId(entry.next_open_id);
      if (served && isOpen(served)) return served;
      const rest = entry ? all().slice(all().indexOf(entry) + 1) : all();
      return firstOpen(rest);
    };
    const resolve = entry => ({entry,
      rows:entry.fingerprints.map(fp => {
        const key = detail.review.findings.findIndex(f => f.fingerprint === fp);
        return key < 0 ? null : {f:detail.review.findings[key], key};
      }).filter(Boolean),
      item:(detail.overview?.items || []).find(item => item.id === entry.id) || null});
    const progress = () => {
      let done = queueOf().counts.done;
      for (const [id, value] of overlay) {
        const entry = byId(id);
        if (entry) done += (entry.open && value !== 'open' ? 1 : 0) - (!entry.open && value === 'open' ? 1 : 0);
      }
      return {done, total:queueOf().counts.total};
    };
    const completeNow = () => { active = null; view = progress().total && progress().done >= progress().total ? 'complete' : 'screen-empty'; };

    function show(entry, focus = false) {
      failure = null;
      if (entry) { active = entry.id; place = entry; view = 'card'; navigate({key:resolve(entry).rows[0]?.key ?? null, page_id:entry.page_id}); }
      else completeNow();
      redraw();
      if (focus) {
        document.querySelector('#coach h3')?.focus({preventScroll:true});
        SC.say(entry ? `Next: ${entry.title}` : document.querySelector('#coach h3')?.textContent || 'Section complete');
      }
    }

    const api = {
      update(updated) {
        detail = updated;
        if (active && !byId(active)) { active = null; show(firstOpen(visible())); }
      },
      all, byId, isOpen, handledKind, resolve, progress, nextOpen,
      get filter() { return filter; },
      get view() { return view; },
      get active() { return active ? byId(active) : null; },
      get failure() { return failure; },
      setFilter(state) { filter = state; redraw(); },
      select: entry => show(entry, true),
      start() {
        if (!all().length) { view = 'screen-empty'; redraw(); return; }
        const first = firstOpen(visible());
        if (first) show(first); else { completeNow(); redraw(); }
      },
      focus(fp) {
        const entry = all().find(item => item.fingerprints.includes(fp));
        if (!entry) return false;
        if (filter && entry.state !== filter) filter = null;
        show(entry);
        return true;
      },
      /** Where the Verdict (or the energy map) sends the user: a state (tile), some findings, or a screen. */
      options(options) {
        if ('state' in options || 'tab' in options) filter = stateOf(options);
        const pool = visible(), onPage = e => e.pages.includes(options.page_id);
        const wanted = options.fingerprints ? pool.find(e => e.fingerprints.some(fp => options.fingerprints.includes(fp))) : null;
        const hit = wanted || (options.page_id ? pool.find(e => onPage(e) && isOpen(e)) || pool.find(onPage) : null) || firstOpen(pool) || pool[0];
        if (hit) show(hit); else { completeNow(); redraw(); }
      },
      /** The phone moved to another screen: show that screen's first open item, or the compact "nothing here" row. */
      screen(pageId) {
        const here = all().filter(e => e.pages.includes(pageId)), hit = firstOpen(here) || here[0];
        failure = null;
        if (hit) { active = hit.id; place = hit; view = 'card'; } else { active = null; view = 'screen-empty'; }
        redraw();
      },
      /** After a save: move on, but only if the user is still on the item that started it. */
      advance(origin) {
        if (origin !== undefined && !api.isActive(origin)) return false;
        const next = nextOpen(active ? byId(active) : place) || firstOpen(all());
        if (next && filter && next.state !== filter) filter = null;
        show(next, true);
        return true;
      },
      isActive: origin => origin === active && SC.currentChapter() === 'improve',
      mark(id, kind) { overlay.set(id, kind); },
      /** The server has spoken (or the save failed): the overlay steps aside, except on the sample, where it is the record. */
      settle(id, {force = false} = {}) { if (!persist || force) overlay.delete(id); },
      /** An undo: open again. Server pages just drop the overlay; the sample keeps it as the record. */
      reopen(id) { if (persist) overlay.set(id, 'open'); else overlay.delete(id); },
      fail(id, message, retry) { failure = {id, message, retry}; redraw(); },
      clearFailure() { failure = null; },
      renderBar(mode, changeMode) {
        const {done, total} = progress(), counts = Object.fromEntries(SC.FIX_STATES.map(state =>
          [state, all().filter(entry => entry.state === state && isOpen(entry)).length]));
        const changes = SC.myChangesOf(detail).count;
        return [h('div', {class:'fix-progress'}, SC.progressRing(done, total),
            h('p', {id:'queue-progress', 'aria-live':'polite'}, SC.progressText({done, total}))),
          SC.fixFilters({counts, selected:filter, onPick:api.setFilter}),
          h('div', {class:'queue-tools'},
            h('button', {type:'button', id:'fix-list-open', class:'btn-pill', onclick:() => SC.openFixDrawer(api)}, SC.icon('list', {size:16}), 'Fix list'),
            h('button', {type:'button', id:'all-screens', class:'btn-pill', onclick:() => SC.openScreens(detail, api)}, 'All screens'),
            h('div', {class:'seg', role:'group', 'aria-label':'Preview wording'},
              h('button', {type:'button', 'aria-pressed':String(mode === 'current'), 'data-fk':'queue-mode-current', onclick:() => changeMode('current')}, 'Original'),
              h('button', {type:'button', 'aria-pressed':String(mode === 'fixes'), 'data-fk':'queue-mode-fixes', disabled:changes === 0,
                'aria-describedby':changes === 0 ? 'mode-why' : null, title:changes === 0 ? 'Add a change to see it on the phone.' : null,
                onclick:() => changeMode('fixes')}, `With my changes (${changes})`),
              changes === 0 && h('span', {id:'mode-why', class:'sr-only'}, 'Add a change to see it on the phone.')))];
      },
      renderList(onPicked = () => {}) {
        // Close a drawer first: a modal dialog would swallow the focus the card is about to take.
        return SC.fixList({entries:visible(), active:active || place?.id || null, isOpen, handledKind, onSelect:entry => { onPicked(); api.select(entry); }});
      },
      render(ctx) {
        if (view === 'card' && api.active) return SC.renderImproveItem(resolve(api.active), {...ctx, queue:api, detail, onAdvance:api.advance, isActive:api.isActive});
        const target = view === 'screen-empty' ? nextOpen(place) || firstOpen(all()) : null;
        return view === 'complete' ? SC.renderCompletion(api, ctx) : SC.renderNothingHere(api, target);
      },
    };
    return api;
  };
})();
