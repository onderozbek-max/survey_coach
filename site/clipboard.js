/* One copy path for the card, the tray and Copy all: the async clipboard first, a hidden textarea second. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const UNAVAILABLE = 'Copy unavailable. Select the text and copy it yourself.';

  /** Resolves true when the text reached the clipboard. Focus goes back where it was. */
  SC.copyText = async text => {
    try { await navigator.clipboard.writeText(text); return true; } catch (_) { /* fall through to the shim */ }
    const before = document.activeElement, area = h('textarea', {class:'copy-shim', readonly:true, tabindex:'-1', 'aria-hidden':'true'});
    area.value = text;
    document.body.append(area);
    area.select();
    let copied = false;
    try { copied = document.execCommand('copy'); } catch (_) { copied = false; }
    area.remove();
    before?.focus?.({preventScroll:true});
    return copied;
  };

  /** Copy, then say so once through the polite toast. */
  SC.copyWithToast = async text => {
    const copied = await SC.copyText(text);
    SC.toast(copied ? 'Copied' : UNAVAILABLE);
    return copied;
  };
})();
