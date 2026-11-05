/* The two drawers: All screens (jump to a screen) and Fix list (the list, below 1024px). Native modal dialogs give both
   a focus trap and Escape. Flags come from the same queue items as the list, the tiles and the progress ring. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.renderIssueList = () => []; // Workflow refreshes decisions; the drawers read the queue when they open.

  /** A modal drawer with a real icon Close button. `build(close)` returns the body; call close(false) to skip returning focus. */
  const drawer = (id, title, build) => {
    document.getElementById(id)?.remove();
    const opener = document.activeElement;
    let restore = true;
    const dialog = h('dialog', {id, class:'side-drawer', 'aria-labelledby':`${id}-h`});
    const close = (returnFocus = true) => { restore = returnFocus; dialog.close(); };
    SC.mount(dialog, h('header', null, h('h2', {id:`${id}-h`}, title),
      h('button', {type:'button', class:'icon-btn', 'aria-label':`Close ${title.toLowerCase()}`, onclick:() => close()}, SC.icon('close', {size:20}))), build(close));
    dialog.addEventListener('close', () => { if (restore) opener?.focus({preventScroll:true}); });
    document.body.append(dialog);
    dialog.showModal();
    return dialog;
  };

  /** Icon and words for one screen, from the queue items that touch it. Never colour alone. */
  const flag = (queue, pageId) => {
    const here = queue.all().filter(entry => entry.pages.includes(pageId)), open = here.filter(queue.isOpen);
    if (open.length) {
      const worst = SC.FIX_STATES.find(state => open.some(entry => entry.state === state));
      return SC.stateChip(worst, {label:`${SC.STATES[worst].label}${open.length > 1 ? ` · ${open.length}` : ''}`});
    }
    return SC.stateChip('looks_good', {label:here.length ? 'Done' : 'Nothing to fix'});
  };

  SC.openScreens = (detail, queue) => {
    const search = h('input', {type:'search', id:'screen-search', autocomplete:'off'});
    const list = h('ul', {class:'screen-list'});
    const dialog = drawer('screen-drawer', 'All screens', close => {
      const render = () => SC.mount(list, detail.screens.filter(screen =>
        `${screen.name} ${screen.topic}`.toLowerCase().includes(search.value.trim().toLowerCase())).map(screen =>
        h('li', null, h('button', {type:'button', class:'screen-row', onclick:() => {
          close(false); window.dispatchEvent(new CustomEvent('surveycoach-screen', {detail:screen.page_id}));
          document.querySelector('#coach h3')?.focus({preventScroll:true});
        }}, h('strong', null, screen.name), h('span', {class:'screen-topic'}, screen.topic), flag(queue, screen.page_id)))));
      search.addEventListener('input', render);
      render();
      return [h('label', {for:'screen-search', class:'drawer-label'}, 'Search screens'), search, list];
    });
    search.focus();
    return dialog;
  };

  SC.openFixDrawer = queue => drawer('fix-drawer', 'Fix list', close => {
    const box = h('div', {class:'fix-drawer-body'});
    const draw = () => {
      const key = document.activeElement?.dataset?.fk;
      SC.mount(box, queue.renderList(() => close(false), draw));
      if (key) box.querySelector(`[data-fk="${key}"]`)?.focus({preventScroll:true});
    };
    draw();
    return box;
  });
})();
