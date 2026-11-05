/* The three kinds of fix a card can hold (paste text, steps, a question to answer), the keep-reason panel and Details.
   Presentation only: every field comes from the finding or from the queue item. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;

  /** "Applies to Q4, Q6 and Q8 (screens 5, 7 and 9)" for a grouped card; the plain location otherwise. */
  SC.appliesTo = entry => {
    if (entry.count <= 1 && entry.screens.length <= 1) return entry.location;
    const [labels, screens] = entry.location.split(' · ');
    return screens ? `Applies to ${labels} (${screens.toLowerCase()})` : `Applies to ${labels.charAt(0).toLowerCase()}${labels.slice(1)}`;
  };

  const choiceFor = (row, wanted) => {
    const list = SC.choicesOf(row.f);
    return list.find(c => c.value === wanted?.value) || list[0];
  };

  /** Paste-ready After text first, Copy, the field location, and the diff behind "Show changes". */
  SC.renderPasteFix = (view, ctx) => {
    const [first] = view.rows, {f} = first, choices = SC.choicesOf(f), saved = ctx.decisionByFp(f.fingerprint);
    let choice = choices.find(c => c.value === ctx.draftOf(f)) || choices.find(c => c.text === saved?.picked_text) || choices[0];
    const box = h('div', {class:'fix-paste'});
    const draw = () => {
      const changes = SC.renderChanges(f, ctx.originalOf(first), choice.text, ctx.detail.snapshot);
      const diff = changes && h('div', {class:'changes', id:`changes-${view.entry.id}`, hidden:true}, changes);
      const toggle = diff && h('button', {type:'button', class:'btn-text show-changes', 'aria-expanded':'false', 'aria-controls':diff.id, onclick:event => {
        diff.hidden = !diff.hidden;
        event.currentTarget.setAttribute('aria-expanded', String(!diff.hidden));
      }}, 'Show changes');
      SC.mount(box,
        h('p', {class:'fix-label'}, f.edit_kind === 'add_answer' ? 'Add this answer' : 'Paste this'),
        SC.renderAfter(f, choice.text, ctx.detail.snapshot),
        h('div', {class:'fix-tools'},
          h('button', {type:'button', class:'btn btn-copy', 'aria-label':'Copy the new wording', onclick:() => SC.copyWithToast(choice.text)}, SC.icon('copy', {size:16}), 'Copy'),
          toggle),
        diff,
        h('ul', {class:'field-hints'}, view.rows.map(row => row.f.field_location && h('li', null, row.f.field_location))),
        choices.length > 1 && h('div', {class:'alternatives', role:'group', 'aria-label':'Alternative wording'}, choices.map((c, index) =>
          h('button', {type:'button', 'aria-pressed':String(c === choice), onclick:() => {
            if (ctx.operation.busy) return;
            choice = c; ctx.onDraft(first.key, c.value); draw();
            box.querySelector('.alternatives [aria-pressed="true"]')?.focus({preventScroll:true});      // the redraw replaced the button: keep the keyboard user in place
          }}, c.label || ['Recommended', 'Shorter', 'Friendlier'][index] || `Alternative ${index + 1}`))));
    };
    draw();
    /** The text to save for each member: the version the user is looking at, found by its position in that member's own list. */
    return {node:box, textFor:row => choiceFor(row, choice).text};
  };

  /** One to three numbered steps. A card with no steps falls back to its explanation as the single step. */
  SC.renderStepsFix = f => h('div', {class:'fix-steps'}, h('p', {class:'fix-label'}, 'Do this'),
    h('ol', null, (f.steps?.length ? f.steps : [f.explanation]).map(step => h('li', null, step))));

  /** One question, one place to look, and a checkbox that unlocks "Mark done". */
  SC.renderCheckFix = (view, onTick) => h('div', {class:'fix-check'}, h('p', {class:'fix-label'}, 'Check this'),
    h('p', {class:'check-question'}, view.item?.instruction || view.rows[0]?.f.you_check || view.entry.title),
    h('label', {class:'check-row'}, h('input', {type:'checkbox', id:'i-checked', onchange:event => onTick(event.target.checked)}), 'I checked'));

  /** Keep as is: pick a reason, add a short note if you like, then save. Nothing is saved before Save. */
  SC.renderKeepPanel = onSave => {
    let reason = null;
    const note = h('textarea', {rows:2, maxlength:200, id:'keep-note', 'aria-label':'Note (optional, up to 200 characters)', placeholder:'Add a note (optional)'});
    const save = h('button', {type:'button', class:'btn btn-primary', id:'keep-save', disabled:true, onclick:() => onSave(reason, note.value.trim())}, 'Keep as is');
    const chips = Object.entries(SC.KEEP_REASONS).map(([value, label]) => h('button', {type:'button', class:'reason-chip', 'data-reason':value, 'aria-pressed':'false', onclick:event => {
      reason = value; save.disabled = false;
      for (const chip of chips) chip.setAttribute('aria-pressed', String(chip === event.currentTarget));
    }}, label));
    return h('div', {class:'keep-reason', hidden:true}, h('div', {class:'reason-chips', role:'group', 'aria-label':'Why keep it'}, chips), note, save);
  };

  /** Methodology and evidence: where the honest nuance lives. Collapsed by default. */
  SC.renderFixDetails = (view, ctx) => h('details', {class:'more'}, h('summary', null, 'Details'),
    view.rows.length ? view.rows.map(row => {
      const {f} = row, adding = f.edit_kind === 'add_answer';
      return h('div', {class:'detail-block', 'data-fingerprint':f.fingerprint},
        view.rows.length > 1 && h('p', {class:'detail-where'}, SC.improveLocation(f, ctx.detail)),
        h('p', null, f.explanation),
        f.current_text && h('div', {class:'issue-original'}, h('strong', null, adding ? 'Keep this question' : 'Original'), h('blockquote', null, ctx.originalOf(row))),
        adding && h('p', null, 'Copy only the new answer label into a new answer option. Do not replace the question. Preview does not configure its behavior.'),
        f.also_affects?.length > 0 ? h('div', {class:'also-affects'}, h('strong', null, 'Also affects'),
          h('ul', null, f.also_affects.map(fp => h('li', null, ctx.detail.review.findings.find(other => other.fingerprint === fp)?.headline || 'Related finding')))) : null,
        h('pre', {class:'evidence'}, typeof f.evidence === 'string' ? f.evidence : f.evidence ? JSON.stringify(f.evidence, null, 2) : 'No additional evidence.'));
    }) : h('p', null, `Where to look: ${view.entry.location}.`));
})();
