/* One workspace, two views. Keyboard tabs and shared live review state. */
(() => {
  'use strict';
  const tabs = [...document.querySelectorAll('[role=tab]')];
  function activate(tab, focus = false) {
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute('aria-selected', String(active));
      item.tabIndex = active ? 0 : -1;
      document.getElementById(item.getAttribute('aria-controls')).hidden = !active;
    });
    sessionStorage.setItem('surveycoach-review-view', tab.id);
    if (focus) tab.focus();
  }
  tabs.forEach((tab, index) => {
    tab.onclick = () => activate(tab);
    tab.onkeydown = event => {
      const next = {ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1}[event.key];
      if (next !== undefined) { event.preventDefault(); activate(tabs[next], true); }
    };
  });
  const saved = tabs.find(tab => tab.id === sessionStorage.getItem('surveycoach-review-view'));
  if (saved) activate(saved);
  window.SC.activateReviewTab = id => activate(document.getElementById(id));
  window.SC.loadWorkspace = async detail => {
    window.SC.workspaceDetail = detail;
    // app.js consumes precisely the same version as the checklist; no duplicate fetch.
    if (!document.querySelector('script[data-workspace-app]')) {
      const script = document.createElement('script');
      script.src = 'app.js'; script.dataset.workspaceApp = 'true';
      document.body.append(script);
    } else window.dispatchEvent(new CustomEvent('surveycoach-decisions', {detail}));
  };
})();
