/* One progress model, "N of M done", for the queue tabs, the toolbar line and the screen drawer.
   An item is done when every finding it owns has a saved decision; position in the list is not progress. */
(() => {
  'use strict';
  const SC = window.SC;
  const TABS = ['must_fix', 'quick_wins', 'more'];
  const owned = (detail, item) => item.fingerprints
    .map(fp => detail.review.findings.find(f => f.fingerprint === fp)).filter(Boolean);

  SC.itemDecided = (detail, item) => owned(detail, item).every(f => {
    const d = detail.decisions[f.fingerprint];
    return d?.action === 'pick' && !d.stale_pick || d?.action === 'original'
      || d?.action === 'keep' && Boolean(d.reason?.trim());
  });
  // Absorbed findings keep their own location but are handled by the item that owns them.
  SC.itemRelated = (detail, item) => {
    const roots = new Set(item.fingerprints);
    for (const f of owned(detail, item)) for (const fp of f.also_affects || []) roots.add(fp);
    return detail.review.findings.filter(f => roots.has(f.fingerprint) || roots.has(f.absorbed_by));
  };
  SC.findingOnPage = (detail, f, pageId) => f.page_id === pageId || Boolean(f.question_id &&
    detail.screens.find(s => s.page_id === pageId)?.questions?.some(q => q.id === f.question_id));

  const count = (detail, items) => ({done: items.filter(item => SC.itemDecided(detail, item)).length, total: items.length});
  SC.progressOf = (detail, tab) => count(detail, detail.plan[tab]);
  SC.progressAll = detail => count(detail, TABS.flatMap(tab => detail.plan[tab]));
  SC.progressOnScreen = (detail, pageId) => {
    const items = TABS.flatMap(tab => detail.plan[tab])
      .filter(item => SC.itemRelated(detail, item).some(f => SC.findingOnPage(detail, f, pageId)));
    return {...count(detail, items), openMust: detail.plan.must_fix.some(item => items.includes(item) && !SC.itemDecided(detail, item))};
  };
  SC.progressText = ({done, total}) => `${done} of ${total} done`;
})();
