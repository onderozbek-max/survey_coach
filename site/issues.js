/* Shared issue language and locations. No persisted decisions are inferred from previews. */
(() => {
  'use strict';
  const SC = window.SC;
  const POLISH = new Set(['9.1', '9.2']);
  SC.issueTier = f => f.severity === 'must_fix' ? 'blocker'
    : f.triage === 'polish' || f.severity === 'polish' || POLISH.has(f.criterion_id) ? 'polish' : 'worth';
  SC.ISSUE_TIERS = {blocker: 'Must-fix', worth: 'Idea', polish: 'Nice to have'};
  SC.issueLocation = (f, snapshot) => {
    let questionNumber = 0;
    for (const [index, page] of (snapshot?.pages || []).entries()) {
      for (const question of page.questions || []) {
        questionNumber += 1;
        if (question.id === f.question_id) return {screen: index + 1, question: questionNumber,
          label: `Q${questionNumber} · Screen ${index + 1}`, target: SC.issueTarget(f, question)};
      }
      if (!f.question_id && page.id === f.page_id) return {screen: index + 1, label: `Screen ${index + 1}`, target: 'Screen text'};
    }
    return {screen: Infinity, label: 'Whole survey', target: 'Survey wording or structure'};
  };
  SC.issueTarget = (f, question) => {
    if (f.edit_kind === 'add_answer') return 'New answer option';
    if (f.structural) return 'Question and answer choices';
    const index = (question.options || []).findIndex(o => o.label === f.current_text);
    if (index >= 0) return `Answer ${index + 1}`;
    if (question.help_text === f.current_text) return 'Help text';
    if (question.scale && f.current_text !== question.text) return 'Scale labels';
    return 'Question text';
  };
  SC.issueDecision = (f, detail = SC.workspaceDetail) => detail?.decisions?.[f.fingerprint];
  SC.acceptedRisk = (f, detail) => {
    const d = SC.issueDecision(f, detail);
    return ['keep', 'original'].includes(d?.action) && Boolean(d.reason?.trim());
  };
  SC.issueCounts = detail => {
    const counts = {blocker: 0, worth: 0, polish: 0, kept: 0, chosen: 0};
    for (const f of detail.review.findings) {
      const d = SC.issueDecision(f, detail);
      if (SC.acceptedRisk(f, detail)) counts.kept++;
      else counts[SC.issueTier(f)]++;
      if (d?.action === 'pick' && d.picked_text) counts.chosen++;
    }
    return counts;
  };
  SC.issueVerdict = detail => {
    const c = SC.issueCounts(detail);
    return `${c.blocker ? `${c.blocker} must-fix` : 'No unacknowledged blockers in what we checked'} · ${c.worth} ideas · ${c.polish} nice to have${c.kept ? ` · ${c.kept} kept on purpose (accepted risk, not verified fixes)` : ''}`;
  };
})();
