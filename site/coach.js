(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const reasons = ['Required wording', 'Keep comparable to earlier research', 'Intentional research design', 'Not relevant here'];

  /** The only decision form: recommended previews never become saved picks implicitly. */
  SC.renderIssueCard = (entry, ctx) => {
    const {f, key, n} = entry, choices = SC.choicesOf(f), adding = f.edit_kind === 'add_answer';
    const saved = ctx.decisionOf?.(key) || SC.issueDecision?.(f);
    const picked = ctx.choiceOf(key);
    const output = h('p', {class:'issue-save-status note', role:'status', 'aria-live':'polite'});
    const reason = h('textarea', {'aria-label':`Reason for keeping ${f.headline}`, rows:2,
      placeholder:'Why keep it? Acknowledge the trade-off.'});
    reason.value = saved?.reason || '';
    const keepPanel = h('div', {class:'keep-reason', hidden:!['keep', 'original'].includes(saved?.action)},
      h('p', {class:'note'}, 'Keeping this acknowledges the risk; it does not verify a fix.'),
      h('div', {class:'reason-chips'}, reasons.map(text => h('button', {type:'button', class:'reason-chip',
        onclick:() => { reason.value = text; reason.focus(); }}, text))), reason);
    let busy = false;
    const act = async (value, metadata, text) => {
      if (busy) return;
      busy = true;
      const buttons = [...article.querySelectorAll('button')];
      buttons.forEach(b => { b.disabled = true; });
      output.textContent = 'Saving…';
      let revision;
      try {
        const request = ctx.onChoose(key, value, metadata.reason);
        revision = SC.decisionRevisions?.get(f.fingerprint);
        const result = await request;
        if (revision !== SC.decisionRevisions?.get(f.fingerprint)) return;
        if (result === false) throw new Error('Your decision could not be saved. Try again.');
        // app may rerender the card while the request is in flight. Always report to the current card.
        const live = document.getElementById(`card-${key}`)?.querySelector('.issue-save-status') || output;
        live.textContent = SC.workspaceDetail ? 'Decision saved. Not verified in RedJade.' : 'Choice recorded for this preview.';
        if (text) await ctx.onCopy(text, live);
      } catch (error) {
        if (revision !== SC.decisionRevisions?.get(f.fingerprint)) return;
        const live = document.getElementById(`card-${key}`)?.querySelector('.issue-save-status') || output;
        live.textContent = error.message || 'Not saved. Try again.';
      } finally { busy = false; buttons.forEach(b => { b.disabled = false; }); }
    };
    keepPanel.append(h('button', {type:'button', class:'btn', 'data-fk':`keep-save-${key}`, onclick:() => {
      if (!reason.value.trim()) { output.textContent = 'Add a reason to keep this on purpose.'; reason.focus(); return; }
      act('original', {action:'keep', reason:reason.value.trim()});
    }}, 'Save reason & keep mine'));
    const tier = SC.issueTier?.(f), location = SC.workspaceDetail && SC.issueLocation(f, SC.workspaceDetail.snapshot);
    const article = h('article', {class:`card ${f.severity}${ctx.selected === key ? ' selected' : ''}`, id:`card-${key}`},
      h('div', {class:'chips'}, h('span', {class:'badge-n'}, String(n)),
        h('span', {class:`chip ${f.severity}`}, SC.ISSUE_TIERS?.[tier] || SC.SEVERITY[f.severity]),
        location && h('span', {class:'chip area'}, location.label),
        f.source === 'ai' && h('span', {class:'chip ai'}, 'AI · review the advice')),
      h('h3', null, h('button', {type:'button', class:'card-head', 'data-fk':`card-${key}`,
        'aria-pressed':String(ctx.selected === key), onclick:() => ctx.onSelect(key)}, f.headline)),
      saved?.carried_from_round && h('p', {class:'note'}, `Choice carried from Round ${saved.carried_from_round}. Still flagged; review it in this round’s context.`),
      h('p', {class:'why'}, f.member_impact), h('p', {class:'fix'}, f.explanation),
      f.current_text && h('div', {class:'issue-original'}, h('strong', null, adding ? 'Keep this question' : 'Original'), h('blockquote', null, adding ? f.current_text : ctx.originalOf?.(entry) || f.current_text)),
      choices.length ? h('div', {class:'issue-rewrites'}, choices.map((choice, index) => h('section', {class:'issue-rewrite'},
        h('h4', null, adding ? 'Add answer option' : choices.length > 1 ? `Rewrite ${index + 1}` : 'Rewrite'),
        h('blockquote', null, choice.text),
        h('button', {type:'button', class:'btn', 'data-fk':`use-${key}-${choice.value}`,
          'aria-label':adding ? 'Use this answer option' : choices.length > 1 ? `Use this rewrite ${index + 1}` : 'Use this',
          onclick:() => act(choice.value, {action:'pick', reason:''}, choice.text)},
        saved?.action === 'pick' && saved.picked_text === choice.text ? 'Use this · chosen' : adding ? 'Use this answer option' : 'Use this'))))
        : h('p', {class:'note'}, 'No text rewrite for this issue. Make the change in RedJade using the guidance above, then check again.'),
      adding && h('p',{class:'note'},'Copy only the new answer label into a new answer option. Do not replace the question. Preview does not add options or configure their behavior.'),
      !adding && !saved && (!picked || picked === 'open') && choices.length > 0 && h('p', {class:'note'}, 'Rewritten previews recommended wording only. Nothing is accepted until you choose Use this.'),
      h('button', {type:'button', class:'btn keep-mine', 'data-fk':`keep-${key}`,
        'aria-expanded':String(!keepPanel.hidden), onclick:event => {
          keepPanel.hidden = !keepPanel.hidden; event.currentTarget.setAttribute('aria-expanded', String(!keepPanel.hidden));
          if (!keepPanel.hidden) reason.focus();
        }}, 'Keep mine'), keepPanel,
      SC.acceptedRisk?.(f) && h('p', {class:'accepted-risk'}, `Kept on purpose: ${saved.reason} · accepted risk, not a verified fix.`), output);
    return article;
  };

  SC.renderCoach = (item, ctx) => {
    const entries = item.entries, selected = entries.find(e => e.key === ctx.selected) || entries[0];
    const all = ctx.review.findings;
    const currentIndex = selected ? all.indexOf(selected.f) : -1;
    const next = all.length > 1 ? all[(currentIndex + 1) % all.length] : null;
    return [h('div', {class:'section-kicker'}, h('h2', {id:'coach-h', tabindex:'-1'}, 'Make this screen better'),
      h('p', null, entries.length ? `${entries.length} ${entries.length === 1 ? 'issue' : 'issues'} on this screen.` : 'Nothing flagged here in the checks run.')),
      // One active decision card keeps the phone and decision in the same context.
      entries.length > 1 && h('nav', {class:'screen-issue-nav', 'aria-label':'Issues on this screen'}, entries.map(e =>
        h('button', {type:'button', 'aria-current':e === selected ? 'true' : false, onclick:() => ctx.onSelect(e.key)}, `${e.n}. ${e.f.headline}`))),
      selected ? SC.renderIssueCard(selected, ctx) : h('p', {class:'screen-clear'}, 'Keep walking through the survey. Unvisited paths remain unverified.'),
      next && h('button', {type:'button', class:'btn next-issue', onclick:() => {
        if (next.fingerprint) window.dispatchEvent(new CustomEvent('surveycoach-focus-finding', {detail:next.fingerprint}));
        else ctx.onSelect(all.indexOf(next));
      }}, 'Next issue →'),
      h('p', {class:'coach-footnote'}, 'Copy chosen wording into RedJade yourself. Check again to compare the next round; choosing or copying is not verification.')];
  };
})();
