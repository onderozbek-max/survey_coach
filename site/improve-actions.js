/* Save, then copy. Undo is revision-guarded and never rolls over a newer choice.
   A late completion belongs to the queue item that started it (ctx.originId): once the user has moved on, it reports
   through the toast only and never navigates, writes status text or takes focus. */
(() => {
  'use strict';
  const SC = window.SC;
  SC.improveActions = ctx => {
    const operation = ctx.operation;
    const focusRow = entries => {
      const row = [...document.querySelectorAll('#coach .pattern-row')]
        .find(row => row.dataset.fingerprint === entries[0]?.f.fingerprint);
      (row?.querySelector('h4') || document.querySelector('#coach-h'))?.focus({preventScroll:true});
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
          if (await ctx.onRestore(record.fingerprint, record.prior, record.version)) restored++;
        }
        operation.recovery = null;
        SC.toast(restored === records.length ? 'Previous decisions restored.' : 'Some decisions could not be restored; missing findings or newer choices were left alone.');
      } catch (_) {
        SC.toast('Some decisions could not be restored. Try again.');
      } finally {
        operation.busy = false; ctx.onRender();
        if (restored && SC.currentChapter() === 'improve') ctx.onFocusFinding(records[0]?.fingerprint);
        if (SC.currentChapter() === 'improve') focusRow(records.map(r => ({f:{fingerprint:r.fingerprint}})));
        else document.querySelector(`#chapter-${SC.currentChapter()} h2`)?.focus({preventScroll:true});
      }
    };
    return async (entries, valueOf, reason, copyText, advance = true) => {
      if (operation.busy) return;
      operation.busy = true;
      operation.recovery = null;
      const records = [];
      const expected = entries.map(({f}) => ({fingerprint:f.fingerprint, revision:SC.decisionRevisions.get(f.fingerprint)}));
      const batchCurrent = () => current(expected) && ctx.isCurrent();
      let finalStatus = '', shouldAdvance = false, clipboardStarted = false;
      focusRow(entries);
      status('Saving…');
      try {
        for (const entry of entries) {
          if (!batchCurrent()) throw Error('A newer choice stopped this operation. Nothing copied.');
          const fp = entry.f.fingerprint, prior = ctx.decisionOf(entry.key);
          const record = {fingerprint:fp, version:ctx.version, prior:prior ? structuredClone(prior) : null};
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
          clipboardStarted = true;
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
        const message = clipboardStarted ? `${records.length} of ${entries.length} suggestions saved. Clipboard request already started; check its contents before pasting. This operation stopped.`
          : records.length ? `${records.length} of ${entries.length} suggestions saved. The rest were not saved. Nothing copied.`
          : error.message || 'Not saved. Try again.';
        finalStatus = message;
        shouldAdvance = false;
        SC.toast(message, records.length ? {undo:undoFor(records)} : {});
      } finally {
        operation.busy = false;
        ctx.onRender();
        if (!ctx.isActive(ctx.originId)) return;
        if (finalStatus) status(finalStatus);
        if (shouldAdvance) ctx.onAdvance(ctx.originId);
        else focusRow(entries);
      }
    };
  };
})();
