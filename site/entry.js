/* Real job evidence only. Animation says “waiting”, never “the worker is alive”. */
(() => {
  'use strict';
  const SC = window.SC, {h, $} = SC;
  let timer, started, lastResponse, panel, currentJob, lastCount = 0, lastCapture, context = '';
  const seconds = stamp => Math.max(0, Math.floor((Date.now() - stamp) / 1000));
  // The test-link line beside the link field is fixed product copy (brief 4.7); the server's engineering notice is not shown.

  function tick() {
    if (!panel) return;
    if (context) $('reading-context').textContent = context + (lastCapture !== null ? ` This page observed this capture count ${seconds(lastCapture)}s ago; not a server capture timestamp.` : '');
    $('reading-elapsed').textContent = `Elapsed ${SC.clock(seconds(started))}`;
    $('reading-response').textContent = lastResponse
      ? `Last status response ${seconds(lastResponse)}s ago. This is connection information, not proof the reader is still working.`
      : 'Waiting for the first status response. No reader activity confirmed yet.';
  }
  SC.beginReadProgress = (start = Date.now(), outputId = 'import-status', restoring = false) => {
    clearInterval(timer);
    $('reading-preview')?.remove();
    currentJob = null; lastCount = 0; lastCapture = null; lastResponse = null; context = ''; started = start;
    const phone = h('div', {class:'reading-phone', 'aria-label':'Preview placeholder, not a captured survey'},
      SC.icon('eye'), h('span', null, 'Preparing review content'));
    panel = h('section', {id:'reading-preview', class:'read-progress', 'aria-labelledby':'reading-heading', 'aria-busy':'true'},
      h('div', {class:'read-progress-heading'}, h('span', {class:'reading-pulse', 'aria-hidden':'true'}),
        h('div', null, h('p', {class:'reading-eyebrow'}, 'SURVEYCOACH · REVIEW IN PROGRESS'),
          h('h2', {id:'reading-heading'}, 'Preparing your review'))),
      h('div', {class:'read-progress-body'}, phone, h('div', {class:'reading-detail'},
        h('p', {id:'reading-progress'}, 'Sending your request…'),
        h('p', {id:'reading-context'}, 'Waiting for job details. No reader activity confirmed yet.'),
        h('ol', {id:'reading-steps', 'aria-label':'Review progress'}))),
      h('div', {class:'reading-connection'}, h('span', {id:'reading-elapsed'}), h('p', {id:'reading-response'})),
      h('div', {id:'reading-actions'}));
    ($(outputId) || $('import-status')).after(panel);
    // The live region stays outside aria-busy, so it can announce transitions immediately.
    const output = $(outputId);
    const initial = restoring ? 'Resuming status checks for your existing job…' : 'Sending your request…';
    $('reading-progress').textContent = initial;
    if (output) { output.textContent = `Preparing your review. ${initial}`; output.dataset.tone = 'progress'; }
    tick(); timer = setInterval(tick, 1000);
    steps(-1, false);
  };
  function steps(active, failed, reader = false) {
    const labels = reader ? ['Opening test survey', 'Read screens', 'Check wording & flow', 'Review ready']
      : ['Prepare review', 'Read supplied content', 'Check wording & flow', 'Review ready'];
    SC.mount($('reading-steps'), labels.map((label, index) => {
      const done = active === 3 || (reader && active >= 0 && index < active);
      return h('li', {'data-complete':String(done), 'aria-current':!failed && index === active ? 'step' : null},
        SC.icon(done ? 'check' : 'clock'), label);
    }));
  }
  SC.readConnection = (text, paused = false) => {
    if (!panel) return;
    $('reading-progress').textContent = text;
    panel.dataset.paused = String(paused);
    panel.setAttribute('aria-busy', String(!paused));
  };
  SC.finishReadProgress = () => {
    clearInterval(timer);
    if (panel) { panel.setAttribute('aria-busy', 'false'); panel.dataset.paused = 'true'; }
  };
  SC.renderReadProgress = (job, jobId, outputId = 'import-status') => {
    if (!panel || !panel.isConnected) SC.beginReadProgress(Date.now(), outputId);
    const count = Math.max(0, Number(job.pages_captured) || 0);
    if (currentJob !== jobId) {
      currentJob = jobId; lastCount = 0; lastCapture = null;
      SC.mount(panel.querySelector('.reading-phone'), SC.icon('eye'), h('span', null, 'Waiting for a captured screen'));
    }
    lastResponse = Date.now();
    if (count !== lastCount) lastCapture = Date.now();
    lastCount = count;
    if (count) {
      let image = panel.querySelector('img');
      if (!image) {
        image = h('img', {alt:'Latest captured survey screen. Not an interactive survey.'});
        SC.mount(panel.querySelector('.reading-phone'), image);
      }
      const source = `/api/reader/jobs/${encodeURIComponent(jobId)}/preview/${count - 1}`;
      if (image.getAttribute('src') !== source) image.src = source;
      panel.querySelector('.reading-phone').setAttribute('aria-label', 'Actual captured survey preview');
    } else {
      SC.mount(panel.querySelector('.reading-phone'), SC.icon('eye'), h('span', null, 'No captured screen yet'));
      panel.querySelector('.reading-phone').setAttribute('aria-label', 'Preview placeholder, not a captured survey');
    }
    const failed = job.status === 'failed', completed = job.status === 'completed';
    const reader = job.stage === 'reading' || count > 0;
    const active = completed ? 3 : job.status === 'queued' ? -1 : job.stage === 'checking' || !reader ? 2 : count ? 1 : 0;
    const text = failed ? job.error || 'Review did not finish.' : completed ? 'Review ready. Opening your review…'
      : job.status === 'queued' ? 'Review queued…'
      : job.stage === 'checking' || !reader ? `${count ? `${count} screens captured. ` : ''}Checking wording and flow…`
      : count ? `Reading screen ${count}…` : 'Opening the test survey…';
    $('reading-progress').textContent = failed ? 'Review needs attention.' : text;
    if (failed && $(outputId)?.textContent !== text) {
      $(outputId).textContent = text; $(outputId).dataset.tone = 'error';
    }
    context = count
      ? `${count} screens captured · only the visited path is checked.${!failed && !completed && job.stage === 'reading' ? ' Waiting for the next screen update.' : ''}`
      : reader ? 'No screens captured yet. The total is not known.' : 'Reviewing supplied content; no captured screen reported.';
    if (!reader) SC.mount(panel.querySelector('.reading-phone'), SC.icon('eye'), h('span', null, 'Review content'));
    steps(active, failed, reader);
    panel.dataset.paused = 'false'; panel.setAttribute('aria-busy', String(!failed && !completed));
    tick();
    if (failed || completed) SC.finishReadProgress();
    return text;
  };
})();
