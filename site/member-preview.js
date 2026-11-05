/* "Play it as a member": a full-screen walk through the phone screens in order, as a member sees them.
   No issue pins, no answer entry. Back and Next step through; the journey strip jumps. Escape closes. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;

  /** The phone's inputs with nothing to flag: a member sees no pins and no rewrites. */
  const phoneContext = (detail, item) => ({data: window.SURVEYCOACH_DEMO, review: detail.review, selected: null, device: 390, large: false,
    total: detail.screens.length, pageId: item.page.id, plan: null, applied: () => false, blocked: () => false, offscreen: () => false, onPin: () => {}});

  /** Seconds in, and seconds on this screen, for every screen: from the journey, else from the saved timing. */
  function timesOf(detail, items) {
    const journey = new Map(SC.journeyOf(detail).map(segment => [segment.page_id, segment]));
    const saved = new Map((detail.overview.energy?.screens || []).map(screen => [screen.page_id, screen.seconds]));
    let running = 0;
    return items.map(item => {
      const segment = journey.get(item.page.id), seconds = segment ? segment.seconds : saved.get(item.page.id) || 0;
      const start = segment ? segment.running : running;
      running += seconds;
      return {start, seconds};
    });
  }

  SC.openMemberPreview = detail => {
    if (document.querySelector('#member-preview')) return;
    const items = SC.buildModel(detail).items;
    if (!items.length) return;
    const opener = document.activeElement, times = timesOf(detail, items), uncertain = Boolean(detail.overview.energy?.path_uncertain);
    const total = detail.overview.verdict?.time?.label;
    let index = 0;
    const phone = h('div', {class: 'member-phone'}), strip = h('div', {class: 'member-strip'}), time = h('p', {class: 'member-time', role: 'status'});
    const back = h('button', {type: 'button', class: 'btn btn-secondary', onclick: () => go(index - 1)}, 'Back');
    const next = h('button', {type: 'button', class: 'btn btn-primary', onclick: () => go(index + 1)}, 'Next');
    const where = h('span', {class: 'member-where num'});
    const close = () => {
      window.removeEventListener('surveycoach-chapter', close);
      dialog.close(); dialog.remove(); opener?.focus({preventScroll: true});
    };
    const dialog = h('dialog', {id: 'member-preview', 'aria-labelledby': 'member-preview-h'},
      h('header', null, h('h2', {id: 'member-preview-h'}, 'Play it as a member', SC.timeInfoButton(detail)),
        h('button', {type: 'button', class: 'btn', onclick: close}, 'Close preview')),
      time, strip, phone, h('nav', {class: 'member-steps', 'aria-label': 'Step through the screens'}, back, where, next));

    function render() {
      const item = items[index], {start, seconds} = times[index];
      const focusedPage = strip.contains(document.activeElement) ? document.activeElement.dataset.page : null;
      SC.mount(phone, SC.renderPhone({...item, entries: []}, phoneContext(detail, item)));
      phone.inert = true;        // a reconstruction: nothing here can be answered or submitted
      time.textContent = uncertain ? `${SC.uncertainWalkthrough} Screen estimate: ${Math.round(seconds)} seconds`
        : `Elapsed estimate: about ${SC.clock(Math.round(start))}${total ? ` of ${total.charAt(0).toLowerCase()}${total.slice(1)}` : ''}`;
      SC.mount(strip, SC.renderJourney(detail, {compact: true, selected: item.page.id, onSelect: pageId => go(items.findIndex(i => i.page.id === pageId))}));
      if (focusedPage) strip.querySelector(`button[data-page="${focusedPage}"]`)?.focus({preventScroll: true});
      where.textContent = `Screen ${index + 1} of ${items.length}`;
      back.disabled = index === 0; next.disabled = index === items.length - 1;
      if (document.activeElement === document.body || document.activeElement?.disabled) (next.disabled ? back : next).focus({preventScroll: true});
    }
    function go(target) {
      if (target < 0 || target >= items.length) return;
      index = target; render();
    }
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const stops = [...dialog.querySelectorAll('button:not(:disabled), [tabindex="0"]')].filter(el => !el.closest('[inert]') && el.tabIndex >= 0);
      const first = stops[0], last = stops.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    window.addEventListener('surveycoach-chapter', close);
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    dialog.addEventListener('close', () => { if (dialog.isConnected) close(); }, {once: true});
    document.body.append(dialog); render(); dialog.showModal(); next.focus({preventScroll: true});
  };
})();
