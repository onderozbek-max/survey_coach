/* One disclosure pattern for the header's step menu and overflow menu: aria-expanded, Escape, outside click,
   focus returns to the button. SC.menu adds the arrow-key behaviour a role=menu needs. */
(() => {
  'use strict';
  const SC = window.SC;

  SC.disclosure = (button, panel, {onToggle = () => {}} = {}) => {
    const isOpen = () => button.getAttribute('aria-expanded') === 'true';
    const set = open => {
      button.setAttribute('aria-expanded', String(open));
      panel.dataset.open = String(open);
      onToggle(open);
    };
    button.addEventListener('click', () => set(!isOpen()));
    document.addEventListener('click', event => {
      if (isOpen() && !panel.contains(event.target) && !button.contains(event.target)) set(false);
    });
    document.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || !isOpen()) return;
      const inside = panel.contains(document.activeElement);
      set(false);
      if (inside) button.focus();
    });
    panel.addEventListener('focusout', event => {      // Tabbing past the last item closes it
      if (isOpen() && event.relatedTarget && !panel.contains(event.relatedTarget) && event.relatedTarget !== button) set(false);
    });
    set(false);
    return {open: () => set(true), close: () => set(false), get isOpen() { return isOpen(); }};
  };

  SC.menu = (button, menu) => {
    const items = () => [...menu.querySelectorAll('[role=menuitem]')].filter(item => item.getClientRects().length);
    const move = (offset, absolute = false) => {
      const list = items(), at = list.indexOf(document.activeElement);
      list[absolute ? (offset < 0 ? list.length - 1 : 0) : (at + offset + list.length) % list.length]?.focus();
    };
    const disclosure = SC.disclosure(button, menu, {onToggle: open => { if (open) requestAnimationFrame(() => move(0, true)); }});
    button.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); disclosure.open(); }
    });
    menu.addEventListener('keydown', event => {
      const step = {ArrowDown: () => move(1), ArrowUp: () => move(-1), Home: () => move(0, true), End: () => move(-1, true)}[event.key];
      if (step) { event.preventDefault(); step(); }
    });
    menu.addEventListener('click', event => { if (event.target.closest('[role=menuitem]')) disclosure.close(); });
    return disclosure;
  };
})();
