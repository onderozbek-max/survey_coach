/* One decision panel. Suggestions are previews until an explicit, persisted choice. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const reasons = ['Intentional for this study', 'Matches a tracker / keep comparable',
    'Stakeholder requirement', 'Not accurate', 'Other…'];
  SC.improveLocation = (f, detail) => {
    const screen = detail.screens.find(s => s.page_id === f.page_id || s.questions?.some(q => q.id === f.question_id));
    if (!screen) return 'Whole survey';
    const question = screen.questions?.find(q => q.id === f.question_id);
    const captured = detail.snapshot.pages.flatMap(p => p.questions || []).find(q => q.id === f.question_id);
    const topic = question ? captured?.text?.split(/\s+/).slice(0,5).join(' ') : screen.topic;
    const label = question?.label || screen.name;
    return `${label} · Screen ${screen.screen}${topic ? ` · ${topic}` : ''}`;
  };
  const suggestionText = (entry, values) => SC.choicesOf(entry.f).find(c => c.value === values.get(entry.key))?.text;
  /** "Use all N" counts only findings that really have a suggestion, hides below two, and says why it is disabled. */
  const useAll = (applicable, missing, act, values, ctx) => {
    if (applicable.length < 2) return null;
    const chosen = applicable.every(e => ctx.decisionOf(e.key)?.action === 'pick' && ctx.decisionOf(e.key).picked_text === suggestionText(e, values));
    const note = chosen ? `All ${applicable.length} suggestions are already chosen.`
      : missing ? `${SC.plural(missing, 'finding')} here ${missing === 1 ? 'has' : 'have'} no suggested wording and stays open for you to decide.` : null;
    return [h('button', {type:'button', id:'use-all', class:'btn btn-primary', disabled:chosen, 'aria-describedby':note ? 'use-all-note' : null,
      onclick:() => act(applicable, e => values.get(e.key), '', applicable.map(e => suggestionText(e, values)).join('\n\n'))},
      `Use all ${SC.plural(applicable.length, 'suggestion')}`), note && h('p', {id:'use-all-note', class:'meta'}, note)];
  };
  SC.renderImproveItem = (item, ctx) => {
    const pattern = item.count > 1, act = SC.improveActions({...ctx, originId:item.id}), values = new Map();
    const rows = ctx.entries.map(entry => {
      const {f, key} = entry, saved = ctx.decisionOf(key), choices = SC.choicesOf(f), adding = f.edit_kind === 'add_answer';
      let choice = choices.find(c => c.value === ctx.draftOf(f)) || choices.find(c => c.text === saved?.picked_text) || choices[0];
      values.set(key, choice?.value);
      const suggested = h('div', {class:'suggested'});
      const renderSuggestion = () => SC.mount(suggested,
        h('h4', null, !choice ? 'Recommended action' : adding ? 'Add answer option' : 'Suggested change'),
        choice ? SC.renderSuggestion(f, ctx.originalOf(entry), choice.text, ctx.detail.snapshot)
          : h('p', null, f.explanation));
      renderSuggestion();
      const output = h('p', {class:'issue-save-status',role:'status'});
      const reason = h('textarea', {rows:2,'aria-label':`Reason for keeping ${f.headline}`,hidden:true});
      reason.value = saved?.reason || '';
      const saveReason = h('button', {type:'button',class:'btn',hidden:true,onclick:() => {
        if (!reason.value.trim()) { output.textContent = 'Add a reason to keep this on purpose.'; reason.focus(); return; }
        act([entry], () => 'original', reason.value.trim(), null, !pattern);
      }}, 'Save reason');
      const keepPanel = h('div', {class:'keep-reason',hidden:true},
        h('div', {class:'reason-chips'}, reasons.map(text => h('button', {type:'button',class:'reason-chip',onclick:() => {
          if (text === 'Other…') { reason.hidden = saveReason.hidden = false; reason.focus(); }
          else act([entry], () => 'original', text, null, !pattern);
        }},text))), reason, saveReason);
      const location = SC.improveLocation(f, ctx.detail);
      return h(pattern ? 'section' : 'div', {class:pattern ? 'pattern-row' : 'decision-content', 'data-fingerprint':f.fingerprint},
        pattern && h('p', {class:'location'}, location),
        pattern && h('h4', {tabindex:'-1','data-fk':`pattern-${f.fingerprint}`}, f.headline),
        saved?.stale_pick && h('p', {class:'stale-pick'}, 'We improved this suggestion since you chose it. Choose again.'),
        saved?.carried_from_round && h('details', null, h('summary', null, `Choice carried from Version ${saved.carried_from_round}`),
          h('p', null, 'Still flagged; review it in this version’s context.')),
        h('p', {class:'why'}, f.member_impact),
        suggested,
        choices.length > 1 && h('div', {class:'alternatives','aria-label':'Alternative wording'}, choices.map((c,index) =>
          h('button', {type:'button','aria-pressed':String(c === choice),onclick:event => {
            if (ctx.operation.busy) return;
            choice = c; values.set(key,c.value); renderSuggestion();
            event.currentTarget.parentElement.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === event.currentTarget)));
            ctx.onDraft(key, c.value);       // the phone and comparison follow the same pick
          }},c.label || ['Recommended','Shorter','Friendlier'][index] || `Alternative ${index + 1}`))),
        f.also_affects?.length > 0 ? h('div', {class:'also-affects'}, h('strong', null, 'Also affects'),
          h('ul', null, f.also_affects.map(fp => h('li', null, ctx.detail.review.findings.find(other => other.fingerprint === fp)?.headline || 'Related finding')))) : null,
        h('details', {class:'more'}, h('summary', null, 'Details'), choice && h('p', null, f.explanation),
          f.current_text && h('div', {class:'issue-original'}, h('strong', null, adding ? 'Keep this question' : 'Original'),
            h('blockquote', null, ctx.originalOf(entry))),
          adding && h('p', null, 'Copy only the new answer label into a new answer option. Do not replace the question. Preview does not configure its behavior.'),
          h('pre', {class:'evidence'}, typeof f.evidence === 'string' ? f.evidence : f.evidence ? JSON.stringify(f.evidence,null,2) : 'No additional evidence.')),
        h('div', {class:'decision-actions'}, choice && h('button', {type:'button', id:pattern ? null : 'use-change',class:pattern ? 'btn use-change' : 'btn btn-primary use-change',
          onclick:() => act([entry], () => values.get(key), '', choice.text, !pattern)}, pattern ? 'Use' : 'Use this change'),
          h('button', {type:'button',id:pattern ? null : 'keep-as-is',class:'btn keep-as-is','aria-expanded':'false',onclick:event => {
            if (ctx.operation.busy) return;
            keepPanel.hidden = !keepPanel.hidden; event.currentTarget.setAttribute('aria-expanded',String(!keepPanel.hidden));
            if (!keepPanel.hidden) keepPanel.querySelector('button').focus();
          }},pattern ? 'Keep' : 'Keep as is')), keepPanel,
        SC.acceptedRisk(f,ctx.detail) && h('p', {class:'accepted-risk'}, `Kept on purpose: ${saved.reason} · accepted risk, not a verified fix.`), output);
    });
    const applicable = ctx.entries.filter(entry => values.get(entry.key));
    return h('article', {class:'card selected',id:`card-${ctx.entries[0]?.key}`},
      !pattern && h('p', {class:'location'}, SC.improveLocation(ctx.entries[0].f,ctx.detail)),
      h('span', {class:'pill'}, SC.icon(item.tier === 'must_fix' ? 'alert' : 'sparkle'),
        {must_fix:'Must-fix',improve:'Quick win',nice_to_have:'Nice to have'}[item.tier]),
      h('h3', {class:'headline',id:'coach-h',tabindex:'-1'}, item.headline),
      ctx.entries.some(({f}) => f.source === 'ai') && h('span', {class:'pill ai',title:'Written by AI. Read it before using.'}, SC.icon('sparkle'), 'AI suggestion'),
      rows,
      ctx.operation.recovery?.fingerprints.some(fp => item.fingerprints.includes(fp)) &&
        h('section', {class:'copy-recovery'}, h('label', null, 'Saved text — select and copy manually',
          h('textarea', {readonly:true, rows:6, 'aria-label':'Saved text for manual copy'}, ctx.operation.recovery.text)),
          h('button', {type:'button',class:'btn',onclick:() => {
            if (ctx.operation.busy) return;
            ctx.operation.recovery = null; ctx.onAdvance();
          }}, 'Continue without copying')),
      useAll(applicable, ctx.entries.length - applicable.length, act, values, ctx),
      h('button', {type:'button',id:'skip',class:'btn-text',onclick:() => { if (!ctx.operation.busy) ctx.onAdvance(); }}, 'Skip for now'));
  };
})();
