/* Native modal semantics: focus containment, Escape and return to the trigger. */
(() => {
  'use strict';
  const { $, icon } = window.SC;
  const dialog = $('data-handling-dialog'), trigger = $('data-handling');
  trigger?.addEventListener('click', () => dialog.showModal());
  $('close-data-handling')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('close', () => trigger.focus());
  dialog?.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('button, a[href], input, select, textarea, [tabindex="0"]')]
      .filter(node => !node.disabled && node.getClientRects().length);
    const edge = event.shiftKey ? controls[0] : controls.at(-1);
    if (document.activeElement === edge) {
      event.preventDefault();
      (event.shiftKey ? controls.at(-1) : controls[0]).focus();
    }
  });
  for (const item of document.querySelectorAll('.narrative [data-icon]')) {
    item.prepend(icon(item.dataset.icon));
  }
})();
