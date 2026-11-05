/* The raw snapshot import is a developer tool. Business pages ship it hidden; the server's environment.js sets the
   flag (SURVEYCOACH_DEVELOPER=1 or --developer). Nothing else changes: the import API itself is not gated here. */
(() => {
  'use strict';
  if (window.SURVEYCOACH_DEVELOPER !== true) return;
  for (const element of document.querySelectorAll('.developer-only')) element.hidden = false;
})();
