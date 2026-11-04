/* One polite notification; each toast owns its timer and its one-shot Undo. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  let region, active;

  SC.toast = (message, {undo} = {}) => {
    if (!region) {
      region = h('div', {id:'toast-region', role:'status', 'aria-live':'polite'});
      document.body.append(region);
    }
    if (active) active.dismiss();

    const toast = h('div', {id:'toast', class:'toast'}, h('span', null, message));
    const state = {dismiss};
    let timer;
    function dismiss() {
      // A queued old timer or detached button must never dismiss the next toast.
      if (active !== state) return;
      active = null;
      clearTimeout(timer);
      document.removeEventListener('keydown', onKeydown);
      toast.remove();
    }
    function onKeydown(event) {
      if (event.key === 'Escape') dismiss();
    }
    if (typeof undo === 'function') {
      toast.append(h('button', {id:'undo', type:'button', class:'btn btn-text', onclick:() => {
        if (active !== state) return;
        dismiss(); // Invalidate first, including when Undo itself creates a toast.
        undo();
      }}, 'Undo'));
    }
    toast.append(h('button', {type:'button', class:'btn btn-text',
      'aria-label':'Dismiss notification', onclick:dismiss}, 'Dismiss'));
    active = state;
    region.replaceChildren(toast);
    document.addEventListener('keydown', onKeydown);
    timer = setTimeout(dismiss, 6000);
  };
})();
