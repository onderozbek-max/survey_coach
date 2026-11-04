/* Save, then copy. Undo is revision-guarded and never rolls over a newer choice. */
(() => {
  'use strict';
  const SC = window.SC;
  SC.improveActions = ctx => {
    let busy = false;
    const status = text => {
      const live = document.querySelector('#coach .issue-save-status');
      if (live) live.textContent = text;
    };
    const undoFor = records => async () => {
      let restored = 0;
      for (const record of records) {
        if (SC.decisionRevisions.get(record.fingerprint) !== record.revision) continue;
        if (await ctx.onRestore(record.key, record.prior)) restored++;
      }
      SC.toast(restored === records.length ? 'Previous decisions restored.' : 'Some decisions could not be restored; newer choices were left alone.');
    };
    return async (entries, valueOf, reason, copyText, advance = true) => {
      if (busy) return;
      busy = true;
      const records = [];
      const buttons = [...document.querySelectorAll('#coach button')];
      buttons.forEach(button => { button.disabled = true; });
      status('Saving…');
      try {
        for (const entry of entries) {
          const fp = entry.f.fingerprint, prior = ctx.decisionOf(entry.key);
          const record = {key:entry.key, fingerprint:fp, prior:prior ? structuredClone(prior) : null};
          const request = ctx.onChoose(entry.key, valueOf(entry), reason);
          record.revision = SC.decisionRevisions.get(fp);
          const result = await request;
          if (record.revision !== SC.decisionRevisions.get(fp)) return;
          if (result === false) throw Error('Your decision could not be saved. Try again.');
          records.push(record);
        }
        let message = 'Kept on purpose. Not a verified fix.';
        if (copyText) {
          const copied = await ctx.onCopy(copyText, {set textContent(text) { status(text); }});
          // A newer edit during clipboard permission must not advance its panel.
          if (records.some(r => r.revision !== SC.decisionRevisions.get(r.fingerprint))) return;
          message = copied ? 'Copied. Paste it into RedJade.' : 'Decision saved. Copy unavailable; select the suggestion and copy it manually.';
        }
        SC.toast(message, {undo:undoFor(records)});
        if (advance) ctx.onAdvance();
      } catch (error) {
        const message = records.length ? `${records.length} of ${entries.length} suggestions saved. The rest were not saved. Nothing copied.`
          : error.message || 'Not saved. Try again.';
        status(message);
        SC.toast(message, records.length ? {undo:undoFor(records)} : {});
      } finally { busy = false; buttons.forEach(button => { button.disabled = false; }); }
    };
  };
})();
