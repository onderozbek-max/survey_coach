/* The status chip on a Home card. One function, so "Checking…" can only mean a live job with real stage data,
   and a finished review always reads as its verdict in the four-state language. */
(() => {
  'use strict';
  const SC = window.SC;
  const live = job => ['queued', 'running'].includes(job?.status);
  SC.surveyStatus = s => {
    if (live(s.job)) {
      if (typeof s.job.stage === 'string' && s.job.stage) return {label: 'Checking…', state: null, running: true};
      return {label: s.job.status === 'queued' ? 'Queued' : 'In progress', state: null, running: true};
    }
    if (s.verdict) return SC.verdictState(s.verdict);
    return {label: s.job?.status === 'failed' ? 'Check did not finish' : 'Not checked yet', state: null};
  };
})();
