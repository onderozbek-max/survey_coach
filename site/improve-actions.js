/* Save, then move on. One decision per click: bound to the item that started it, never a second submit while one is
   running, never an automatic retry (the card offers "Try again"), and Undo only rolls back what it saved. A late
   completion belongs to its own item: once the user has moved on it reports through the toast and changes nothing else. */
(() => {
  'use strict';
  const SC = window.SC;
  SC.improveActions = ctx => {
    const operation = ctx.operation, queue = ctx.queue, origin = ctx.originId;
    const current = records => records.every(r => SC.decisionRevisions.get(r.fingerprint) === r.revision);
    const status = text => {
      const live = document.querySelector('#coach .issue-save-status');
      if (live) live.textContent = text;
    };
    const focusCard = () => document.querySelector('#coach-h')?.focus({preventScroll:true});

    const undoFor = records => async () => {
      if (operation.busy) return;
      operation.busy = true;
      let restored = 0;
      try {
        for (const record of records) {
          if (!current([record])) continue;
          if (await ctx.onRestore(record.fingerprint, record.prior, record.version)) restored++;
        }
        queue.reopen(origin);
        SC.toast(restored === records.length ? 'Back on your list' : 'Some changes could not be undone; newer choices were left alone.');
      } catch (_) {
        SC.toast('Some changes could not be undone. Try again.');
      } finally {
        operation.busy = false; ctx.onRender();
        if (restored && SC.currentChapter() === 'improve') ctx.onFocusFinding(records[0]?.fingerprint);
      }
    };

    /** `spec`: kind (use|done|keep|open), message for the toast, build(fingerprint) -> decision body, advance (default true). */
    const act = async (view, spec) => {
      if (operation.busy) return;
      operation.busy = true;
      const {entry} = view, records = [], advance = spec.advance !== false;
      const expected = entry.fingerprints.map(fingerprint => ({fingerprint, revision:SC.decisionRevisions.get(fingerprint)}));
      const batchCurrent = () => current(expected) && ctx.isCurrent();
      let failed = '';
      queue.clearFailure();
      queue.mark(entry.id, spec.kind);               // optimistic: the list ticks now, the server confirms below
      ctx.onRender();
      try {
        for (const fingerprint of entry.fingerprints) {
          if (!batchCurrent()) throw Error('A newer choice stopped this save. Nothing else was changed.');
          const prior = ctx.decisionByFp(fingerprint);
          const record = {fingerprint, version:ctx.version, prior:prior ? structuredClone(prior) : null};
          const request = ctx.onDecide(fingerprint, spec.build(fingerprint));
          record.revision = SC.decisionRevisions.get(fingerprint);
          expected.find(r => r.fingerprint === fingerprint).revision = record.revision;
          const saved = await request;
          if (saved !== false) records.push(record);
          if (!batchCurrent()) throw Error('A newer choice stopped this save. Nothing else was changed.');
          if (saved === false) throw Error('Not saved. Your choice is still open.');
        }
      } catch (error) {
        failed = records.length ? `${records.length} of ${entry.fingerprints.length} saved. The rest were not. Try again.` : error.message || 'Not saved. Try again.';
      }
      operation.busy = false;
      const here = ctx.isActive(origin);
      if (failed) {
        queue.settle(entry.id, {force:true});
        if (records.length) SC.toast(failed, {undo:undoFor(records)});
        if (here) queue.fail(entry.id, failed, () => act(view, spec)); else { ctx.onRender(); if (!records.length) SC.toast(failed); }
        return;
      }
      queue.settle(entry.id);
      if (spec.kind === 'open') queue.reopen(entry.id);
      else SC.toast(spec.message, {undo:undoFor(records)});
      ctx.onRender();
      if (!here) return;
      if (advance) ctx.onAdvance(origin); else focusCard();
      status('');
    };
    return act;
  };
})();
