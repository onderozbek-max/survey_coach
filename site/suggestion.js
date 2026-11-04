/* Presentation only: choices keep their exact clipboard/decision text. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const choiceKinds = new Set(['single_choice', 'multi_choice', 'dropdown']);

  /** Judge contract: first line is the stem, then one answer per line.
   * `structural` alone only means multiline. Corroborate with captured choices
   * or an unchanged stem; prose and ungrounded bundles remain verbatim.
   */
  SC.bundleParts = (finding, text, snapshot) => {
    if (!finding.structural || finding.edit_kind === 'add_answer' || !text) return null;
    const questions = (snapshot?.pages || []).filter(p => !finding.page_id || p.id === finding.page_id)
      .flatMap(p => p.questions || []).filter(q => q.id === finding.question_id);
    if (questions.length !== 1 || !choiceKinds.has(questions[0].kind)) return null;
    const question = questions[0], lines = text.trim().split(/\r?\n/).map(line => line.trim());
    if (lines.length < 2 || lines.some(line => !line)) return null;
    const [stem, ...answers] = lines, known = new Set((question.options || []).map(o => o.label.trim()));
    if (!known.size || (stem !== question.text.trim() && !answers.some(answer => known.has(answer)))) return null;
    return {question:stem, answers};
  };

  SC.renderSuggestion = (finding, before, text, snapshot) => {
    if (finding.edit_kind === 'add_answer') return h('div', {class:'suggestion-answer'},
      h('h5', null, 'Answer choice'), h('blockquote', null, text));
    const parts = SC.bundleParts(finding, text, snapshot);
    if (parts) return h('div', {class:'suggestion-bundle'},
      h('h5', null, 'Question'), h('p', {class:'suggestion-question'}, parts.question),
      h('h5', null, 'Answer choices'),
      h('ul', {'aria-label':'Answer choices'}, parts.answers.map(answer => h('li', null, answer))));
    // A structural bundle is not one replaceable sentence. Avoid interleaving
    // deleted answers with new answers; Details retains the complete original.
    return finding.structural ? h('blockquote', null, text) : SC.renderDiff(before, text);
  };
})();
