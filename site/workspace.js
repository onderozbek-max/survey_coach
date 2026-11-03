/* One workspace. The issue drawer navigates; only the coach edits decisions. */
(() => {
  'use strict';
  const SC = window.SC;
  SC.activateReviewTab = () => {}; // Older app callers must not hide the phone workspace.
  SC.loadWorkspace = detail => {
    SC.workspaceDetail = detail;
    if (!document.querySelector('script[data-workspace-app]')) {
      const script = document.createElement('script');
      script.src = 'app.js'; script.dataset.workspaceApp = 'true';
      document.body.append(script);
    } else window.dispatchEvent(new CustomEvent('surveycoach-decisions', {detail}));
  };
})();
