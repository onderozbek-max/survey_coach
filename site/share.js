/* Share records explicit choices, never preview defaults or claims of launch readiness. */
(() => {
  'use strict';
  const SC = window.SC, {h, mount, $} = SC;
  SC.shareChanges = detail => detail.review.findings.filter(f => {
    const d = SC.issueDecision(f, detail);
    return !f.absorbed_by && d?.action === 'pick' && !d.stale_pick && Boolean(d.picked_text?.trim());
  });
  const place = (f, detail) => {
    const model = SC.buildModel(detail);
    return model.items.find(item => item.page.id === f.page_id || item.page.questions.some(q => q.id === f.question_id)) || model.whole;
  };
  SC.shareChangeText = (f, detail) => {
    const d = SC.issueDecision(f, detail), name = place(f, detail).name;
    return `${name} · ${f.headline}\n${f.edit_kind === 'add_answer'
      ? `Keep question: ${f.current_text}\nAdd answer option: ${d.picked_text}\n${f.explanation}`
      : `Find: ${f.current_text || 'Locate using the guidance above'}\nReplace with: ${d.picked_text}`}`;
  };
  SC.shareChangesText = detail => SC.shareChanges(detail).map(f => SC.shareChangeText(f, detail)).join('\n\n');
  // Do not turn an unsafe/member-token link into a seemingly approved test link by stripping it.
  SC.recheckLink = value => {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && (url.hostname === 'redjade.net' || url.hostname.endsWith('.redjade.net'))
        && !url.username && !url.password && !url.search && !url.hash && !url.port && !/[\s\\]/.test(value) ? value : '';
    } catch (_) { return ''; }
  };
  SC.renderShare = (detail, copy) => {
    const changes = SC.shareChanges(detail), kept = detail.review.findings.filter(f => !f.absorbed_by && SC.acceptedRisk(f, detail));
    const handled = fp => {
      const f = detail.review.findings.find(f => f.fingerprint === fp);
      return f && (changes.includes(f) || SC.acceptedRisk(f, detail));
    };
    const open = (detail.plan?.must_fix || []).filter(item => !item.fingerprints.length || !item.fingerprints.every(handled)).length;
    $('share-summary').textContent = `${changes.length} changes chosen · ${kept.length} kept on purpose · ${open} must-fixes still open`;
    const groups = new Map();
    for (const f of changes) {
      const item = place(f, detail);
      if (!groups.has(item.index)) groups.set(item.index, {name:item.name, findings:[]});
      groups.get(item.index).findings.push(f);
    }
    mount($('change-list'), ...[...groups].sort(([a], [b]) => a - b).map(([, group]) => h('section', null,
      h('h3', null, group.name), h('ul', null, group.findings.map(f => h('li', null,
        h('strong', null, f.headline),
        f.edit_kind === 'add_answer' ? h('div', null, h('p', null, `Keep question: ${f.current_text}`),
          h('p', null, 'Add answer option: ', h('ins', null, SC.issueDecision(f, detail).picked_text)))
          : SC.renderDiff(f.current_text, SC.issueDecision(f, detail).picked_text),
        h('button', {type:'button', class:'btn-secondary', onclick:() => copy(SC.shareChangeText(f, detail), $('action-status'))}, 'Copy change')))))));
    if (!changes.length) mount($('change-list'), h('p', null, 'No changes chosen yet. Recommended previews are not included.'));
    mount($('kept-reasons'), kept.length && h('details', null, h('summary', null, `Kept on purpose (${kept.length})`),
      h('p', null, 'These are accepted risk, not verified fixes.'), h('ul', null, kept.map(f => h('li', null,
        `${place(f, detail).name} · ${f.headline}: ${SC.issueDecision(f, detail).reason}`)))));
    const button = $('copy-all');
    button.textContent = `Copy all changes (${changes.length})`;
    button.disabled = !changes.length; button.hidden = !changes.length;
    button.onclick = () => copy(SC.shareChangesText(detail), $('action-status'));
    mount($('version-changes'), SC.renderRounds(detail, detail.id));
    $('download-summary').href = `/api/surveys/${encodeURIComponent(detail.id)}/versions/${detail.version}/summary?download=1`;
  };
})();
