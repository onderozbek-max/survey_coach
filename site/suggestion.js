/* Presentation only: choices keep their exact clipboard/decision text. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const choiceKinds = new Set(['single_choice', 'multi_choice', 'dropdown']);

  const capturedQuestion = (finding, snapshot) => {
    const questions = (snapshot?.pages || []).filter(p => !finding.page_id || p.id === finding.page_id)
      .flatMap(p => p.questions || []).filter(q => q.id === finding.question_id);
    return questions.length === 1 ? questions[0] : null;
  };

  /** Never infer answer roles from partial lexical overlap. Changed answers
   * require explicit labels and list markers. The legacy unlabelled contract
   * is supported only when the complete captured answer sequence is unchanged.
   */
  SC.bundleParts = (finding, text, snapshot) => {
    if (!finding.structural || finding.edit_kind === 'add_answer' || !text) return null;
    const question = capturedQuestion(finding, snapshot);
    if (!question || !choiceKinds.has(question.kind)) return null;
    const lines = text.trim().split(/\r?\n/).map(line => line.trim());
    if (lines.length < 2 || lines.some(line => !line)) return null;
    const labelled = /^Question: (.+)$/.exec(lines[0]);
    if (labelled && lines[1] === 'Answer choices:' && lines.length > 2) {
      const answers = lines.slice(2).map(line => /^- (.+)$/.exec(line));
      return answers.every(Boolean) ? {question:labelled[1], answers:answers.map(match => match[1])} : null;
    }
    const [stem, ...answers] = lines, known = (question.options || []).map(o => o.label.trim());
    if (!known.length || answers.length !== known.length || answers.some((answer, i) => answer !== known[i])) return null;
    return {question:stem, answers};
  };

  const asBundle = (finding, text, snapshot) => {
    if (finding.edit_kind === 'add_answer') return h('div', {class:'suggestion-answer'},
      h('h5', null, 'Answer choice'), h('blockquote', null, text));
    const parts = SC.bundleParts(finding, text, snapshot);
    if (parts) return h('div', {class:'suggestion-bundle'},
      h('h5', null, 'Question'), h('p', {class:'suggestion-question'}, parts.question),
      h('h5', null, 'Answer choices'),
      h('ul', {'aria-label':'Answer choices'}, parts.answers.map(answer => h('li', null, answer))));
    // A structural bundle is not one replaceable sentence. Avoid interleaving
    // deleted answers with new answers; Details retains the complete original.
    return finding.structural && /[\r\n]/.test(text) ? h('blockquote', null, text) : null;
  };

  /** The paste-ready After text, first and plain. Answers and bundles keep their own shape. */
  SC.renderAfter = (finding, text, snapshot) => asBundle(finding, text, snapshot) || h('p', {class:'after-text'}, text);

  /** The word-level diff behind "Show changes"; null when there is nothing meaningful to compare (a bundle, a new answer). */
  SC.renderChanges = (finding, before, text, snapshot) => {
    if (asBundle(finding, text, snapshot)) return null;
    const original = finding.structural ? capturedQuestion(finding, snapshot)?.text || finding.current_text || before : before;
    return original ? SC.renderDiff(original, text) : null;
  };
})();
