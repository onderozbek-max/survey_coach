/* The one rule for the team tool's address, shared by the sample banner and the landing page: it is returned only
   when it is a plain https URL; anything else (empty, http, javascript:, protocol-relative) is null, so nothing
   ever renders a link it should not. */
(() => {
  'use strict';
  window.SC.teamAddress = value => {
    if (typeof value !== 'string') return null;
    try {
      const url = new URL(value.trim());
      return url.protocol === 'https:' && url.hostname ? url.href : null;
    } catch { return null; }
  };
})();
