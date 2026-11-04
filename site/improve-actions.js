/* Save, then copy. Undo is revision-guarded and never rolls over a newer choice. */
(() => {
  'use strict';
  const SC = window.SC;
  SC.improveActions = ctx => {
    const operation = ctx.operation;
    const focusRow = entries => {
      const row = [...document.querySelectorAll('#coach .pattern-row')]
        .find(row => row.dataset.fingerprint === entries[0]?.f.fingerprint);
      row?.querySelector('h4')?.focus({preventScroll:true});
    };
    const current = records => records.every(r => SC.decisionRevisions.get(r.fingerprint) === r.revision);
    const status = text => {
      const live = document.querySelector('#coach .issue-save-status');
      if (live) live.textContent = text;
    };
    const undoFor = records => async () => {
      if (operation.busy) return;
      operation.busy = true;
      let restored = 0;
      try {
        for (const record of records) {
          if (!current([record])) continue;
          if (await ctx.onRestore(record.key, record.prior)) restored++;
        }
        operation.recovery = null;
        SC.toast(restored === records.length ? 'Previous decisions restored.' : 'Some decisions could not be restored; newer choices were left alone.');
      } finally {
        operation.busy = false; ctx.onRender();
        focusRow(records.map(r => ({f:{fingerprint:r.fingerprint}})));
      }
    };
    return async (entries, valueOf, reason, copyText, advance = true) => {
      if (operation.busy) return;
      operation.busy = true;
      operation.recovery = null;
      const records = [];
      const expected = entries.map(({f}) => ({fingerprint:f.fingerprint, revision:SC.decisionRevisions.get(f.fingerprint)}));
      const batchCurrent = () => current(expected);
      let finalStatus = '', shouldAdvance = false;
      focusRow(entries);
      status('Saving…');
      try {
        for (const entry of entries) {
          if (!batchCurrent()) throw Error('A newer choice stopped this operation. Nothing copied.');
          const fp = entry.f.fingerprint, prior = ctx.decisionOf(entry.key);
          const record = {key:entry.key, fingerprint:fp, prior:prior ? structuredClone(prior) : null};
          const request = ctx.onChoose(entry.key, valueOf(entry), reason);
          record.revision = SC.decisionRevisions.get(fp);
          expected.find(r => r.fingerprint === fp).revision = record.revision;
          const result = await request;
          if (result !== false) records.push(record);
          if (!batchCurrent()) throw Error('A newer choice stopped this operation. Nothing copied.');
          if (result === false) throw Error('Your decision could not be saved. Try again.');
        }
        if (!batchCurrent()) throw Error('A newer choice stopped this operation. Nothing copied.');
        let message = 'Kept on purpose. Not a verified fix.';
        shouldAdvance = advance;
        if (copyText) {
          const copied = await ctx.onCopy(copyText, {set textContent(text) { status(text); }});
          // A newer edit during clipboard permission must not advance its panel.
          if (!batchCurrent()) throw Error('A newer choice stopped this operation.');
          if (!copied) {
            shouldAdvance = false;
            operation.recovery = {fingerprints:entries.map(e => e.f.fingerprint), text:copyText};
          }
          message = copied ? 'Copied. Paste it into RedJade.' : 'Decision saved. Copy unavailable; select the suggestion and copy it manually.';
        }
        SC.toast(message, {undo:undoFor(records)});
      } catch (error) {
        const message = records.length ? `${records.length} of ${entries.length} suggestions saved. The rest were not saved. Nothing copied.`
          : error.message || 'Not saved. Try again.';
        finalStatus = message;
        shouldAdvance = false;
        SC.toast(message, records.length ? {undo:undoFor(records)} : {});
      } finally {
        operation.busy = false;
        ctx.onRender();
        if (finalStatus) status(finalStatus);
        if (shouldAdvance) ctx.onAdvance();
        else focusRow(entries);
      }
    };
  };
})();
