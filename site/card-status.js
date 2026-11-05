/* The status chip on a Home card. One function, so "Checking…" can only mean a live job with real stage data. */
(() => {
  'use strict';
  const SC = window.SC;
  const live = job => ['queued', 'running'].includes(job?.status);
  SC.surveyStatus = s => {
    if (live(s.job)) {
      if (typeof s.job.stage === 'string' && s.job.stage) return {label: 'Checking…', state: 'unknown'};
      return {label: s.job.status === 'queued' ? 'Queued' : 'In progress', state: 'unknown'};
    }
    if (s.must_fix > 0) return {label: `${s.must_fix} ${s.must_fix === 1 ? 'must-fix' : 'must-fixes'}`, state: 'needs_work'};
    if (s.ready_to_share === true) return {label: 'Ready to share', state: 'strong'};
    if (SC.READINESS[s.readiness]) return {label: SC.READINESS[s.readiness], state: s.readiness === 'needs_work' ? 'needs_work' : 'mixed'};
    return {label: s.job?.status === 'failed' ? 'Check did not finish' : 'Not checked yet', state: 'unknown'};
  };
})();
