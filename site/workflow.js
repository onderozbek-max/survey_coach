/* Private local workflow; never stores real survey content in the public demo or browser storage. */
(() => {
  "use strict";
  const { h, mount, $, plural } = window.SC;
  const params = new URLSearchParams(location.search), surveyId = params.get("id");
  let detail, activeRead = false;
  const pendingKey = 'surveycoach-pending-job';
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  function remember(jobId, started) {
    try { sessionStorage.setItem(pendingKey, JSON.stringify({jobId, started})); } catch (_) { /* storage is optional */ }
  }
  function forget() { try { sessionStorage.removeItem(pendingKey); } catch (_) {} }
  function pending() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(pendingKey));
      if (typeof saved?.jobId === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(saved.jobId)
          && Number.isFinite(saved.started) && saved.started <= Date.now() && Date.now() - saved.started < 7200000) return saved;
    } catch (_) {}
    forget(); return null;
  }
  function lockRead(locked) {
    activeRead = locked;
    for (const control of document.querySelectorAll('#import-form input, #import-form button[type=submit], #recheck-form input, #recheck-form button[type=submit], #sample-start, #check-again')) {
      if (locked) {
        control.dataset.readDisabled = String(control.disabled);
        if (control.matches('button[type=submit]')) {
          control.dataset.readLabel = control.textContent;
          control.textContent = 'Checking…';
        }
        control.disabled = true;
      } else if ('readDisabled' in control.dataset) {
        control.disabled = control.dataset.readDisabled === 'true';
        if (control.dataset.readLabel) { control.textContent = control.dataset.readLabel; delete control.dataset.readLabel; }
        delete control.dataset.readDisabled;
      }
    }
  }
  const endpoint = (version = detail.version) => `/api/surveys/${encodeURIComponent(surveyId)}/versions/${version}`;
  async function api(path, method = "GET", body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(path, { method, signal:controller.signal,
        headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const error = new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}).`);
        // Only explicit client rejection proves that starting a fresh submission is safe.
        error.rejected = response.status >= 400 && response.status < 500 && response.status !== 408;
        throw error;
      }
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  // tone: "info" | "progress" | "error"; styled where a page opts in (home.css).
  const message = (id, text, tone = "info") => { const el = $(id); if (el) { el.textContent = text; el.dataset.tone = tone; } };
  async function copy(text, output) {
    try { await navigator.clipboard.writeText(text); output.textContent = "Copied. Paste into RedJade yourself; this does not mark the issue fixed."; }
    catch (_) { output.textContent = "Clipboard unavailable. Select the text and copy it manually."; }
  }
  function announce(outputId, text, tone = 'progress') {
    if ($(outputId)?.textContent !== text) message(outputId, text, tone);
  }
  async function pauseChecking(jobId, outputId) {
    const text = 'Status checks paused. The job may still be working. Resume checking this same job; do not start another review.';
    window.SC.readConnection?.(text, true);
    announce(outputId, text, 'error');
    await new Promise(resolve => {
      const resume = h('button', {type:'button', id:'resume-checking', class:'btn', onclick:() => {
        resume.remove(); resolve();
      }}, 'Resume checking');
      ($('reading-actions') || $(outputId)).append(resume);
    });
  }
  async function waitForJob(jobId, outputId) {
    let errors = 0;
    for (let attempt = 0; ; attempt++) {
      if (attempt >= 600) { await pauseChecking(jobId, outputId); attempt = 0; }
      let job;
      try { job = await api(`/api/jobs/${encodeURIComponent(jobId)}`); }
      catch (_) {
        errors++;
        const text = 'Connection interrupted. Waiting for a status response; retrying this job only. No new survey response will be created.';
        window.SC.readConnection?.(text);
        announce(outputId, text, 'error');
        if (errors >= 3) { await pauseChecking(jobId, outputId); errors = 0; attempt = 0; }
        else await sleep(2000);
        continue;
      }
      errors = 0;
      const text = window.SC.renderReadProgress?.(job, jobId, outputId);
      announce(outputId, text || 'Waiting for the next job update.');
      if (job.status === 'failed') {
        forget();
        throw new Error(job.error || 'Review did not finish. Your previous review is unchanged.');
      }
      if (job.status === 'completed') { forget(); return job; }
      await sleep(1000);
    }
  }
  function openReview(job, result = {}) {
    location.href = `review.html?id=${encodeURIComponent(result.id || result.survey_id || job.survey_id)}&version=${result.version || job.version}${result.deduplicated || job.deduplicated ? '&unchanged=1' : ''}${surveyId ? '' : '#overview'}`;
  }
  async function startRead(makeRequest) {
    if (activeRead) return;
    lockRead(true);
    const started = Date.now();
    window.SC.beginReadProgress?.(started);
    let submitted = false, accepted = false, ambiguous = false;
    try {
      const request = await makeRequest();
      submitted = true;
      const result = await api(request.path, 'POST', request.body);
      if (typeof result.job_id !== 'string' || !result.job_id) throw new Error('No job reference returned.');
      accepted = true;
      remember(result.job_id, started);
      const job = await waitForJob(result.job_id, 'import-status');
      openReview(job, result);
    } catch (error) {
      ambiguous = submitted && !accepted && !error.rejected;
      const text = ambiguous
        ? 'No submission confirmation received. Status is unknown: a test response may already have been created. Do not submit again or reload to retry. This page cannot safely resume without a job reference. Ask the local pilot owner to check the job before starting another review.'
        : error.message;
      message('import-status', text, 'error');
      window.SC.readConnection?.(text, true);
      window.SC.finishReadProgress?.();
    } finally {
      // An unconfirmed POST is never automatically repeated or labelled a safe failure.
      if (!ambiguous) lockRead(false);
    }
  }
  async function submit(event) {
    event.preventDefault();
    if (activeRead) return;
    const file = $('snapshot')?.files[0], value = $('survey-link').value.trim();
    await startRead(async () => {
      const ai = true;
      if (file) {
        if (file.size > 950000) throw new Error('Snapshot must be smaller than 950 KB.');
        const snapshot = JSON.parse(await file.text());
        return {path:surveyId ? `/api/surveys/${encodeURIComponent(surveyId)}/recheck` : '/api/surveys', body:{snapshot, ai}};
      }
      if (!value) throw new Error('Paste an approved preview link or choose a snapshot file.');
      let url;
      try { url = new URL(value); } catch (_) { /* shared inline error below */ }
      if (!url || url.protocol !== 'https:' || !(url.hostname === 'redjade.net' || url.hostname.endsWith('.redjade.net')) ||
          url.username || url.password || url.search || url.hash || url.port || /[\s\\]/.test(value)) {
        throw new Error('Use a valid HTTPS RedJade test link without credentials, query parameters, or a fragment.');
      }
      return {path:'/api/reader/jobs', body:{url:value, approval:true, ai, survey_id:surveyId || null}};
    });
  }
  const since = (stamp) => {
    // SQLite CURRENT_TIMESTAMP is UTC without a zone marker.
    const minutes = Math.round((new Date(stamp.replace(" ", "T") + "Z") - Date.now()) / 60000);
    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
    if (Math.abs(minutes) < 60) return rtf.format(minutes, "minute");
    if (Math.abs(minutes) < 1440) return rtf.format(Math.round(minutes / 60), "hour");
    return rtf.format(Math.round(minutes / 1440), "day");
  };
  const signalNames = ['Time', 'Clarity', 'Honest answers', 'Energy & flow', 'Tone & fun', 'Phone comfort'];
  const signalIcons = {strong:'check', mixed:'minus', needs_work:'alert', unknown:'clock'};
  function surveyCard(s) {
    const signals = signalNames.map((name, index) => s.signals?.[index]
      || {name, state:'unknown', label:'Not checked yet'});
    const pending = s.job && ['queued', 'running'].includes(s.job.status);
    const must = !pending && s.must_fix > 0;
    const ready = !pending && !must && s.ready_to_share === true;
    const label = must ? `${s.must_fix} must-fixes` : ready ? 'Ready to share' : 'Checking…';
    return h('a', {class:'survey-card', href:`review.html?id=${encodeURIComponent(s.id)}#overview`},
      h('h3', null, s.title?.trim() || 'Untitled survey'),
      window.SC.renderQualityCompact(s.quality),
      h('span', {class:'chip', 'data-state':must ? 'needs_work' : ready ? 'strong' : 'unknown'},
        window.SC.icon(must ? 'alert' : ready ? 'check' : 'clock'), label),
      h('div', {class:'signals', role:'img', 'aria-label':signals.map(v => `${v.name}: ${v.label}`).join(', ')},
        signals.map(v => h('span', {class:'signal-dot', 'data-state':v.state, title:`${v.name}: ${v.label}`, 'aria-hidden':'true'},
          window.SC.icon(signalIcons[v.state] || 'clock')))),
      h('p', {class:'meta'}, `Version ${s.version} · ${since(s.created_at)}`));
  }
  async function home() {
    const data = await api("/api/surveys");
    message("survey-count", data.surveys.length ? plural(data.surveys.length, "survey") : "");
    mount($("survey-list"), data.surveys.length ? data.surveys.map(surveyCard)
      : h("p", { class: "empty" }, h("strong", null, "Nothing reviewed yet"), "Paste a link above, or try the sample survey to see what a review looks like."));
  }
  function refreshDecisions() {
    window.SC.workspaceDetail = detail;
    mount($('fix-list'), window.SC.renderIssueList(detail));
    window.SC.renderShare(detail, copy);
    const kept = window.SC.issueCounts(detail).kept;
    message('decision-verdict', kept ? `${kept} kept on purpose · accepted risk, not verified fixes.` : '');
  }
  function revealRecheck() {
    window.SC.goChapter('share');
    $('survey-link').value ||= window.SC.recheckLink(detail.source_url || detail.snapshot.source_url || '');
    $('recheck-panel').scrollIntoView({block:'center', behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    $('survey-link').focus({preventScroll:true});
  }
  function titleEditor() {
    const title = $('review-title'), input = h('input', {type:'text', maxlength:200, 'aria-label':'Survey title'});
    const edit = h('button', {type:'button', class:'title-edit', onclick:() => {
      input.value = detail.title; form.hidden = false; edit.hidden = true; input.focus();
    }}, 'Rename');
    const status = h('span', {role:'status'});
    const form = h('form', {class:'title-form', hidden:true, onsubmit:async event => {
      event.preventDefault();
      if (!input.value.trim()) { status.textContent = 'Enter a title.'; return; }
      const button = form.querySelector('button[type=submit]'); button.disabled = true;
      try {
        await window.SC.updateSurvey({title:input.value.trim()});
        title.textContent = detail.title;
        form.hidden = true; edit.hidden = false; status.textContent = 'Title saved.';
      } catch (error) { status.textContent = error.message; }
      finally { button.disabled = false; }
    }}, input, h('button', {type:'submit', class:'btn'}, 'Save title'),
      h('button', {type:'button', class:'btn', onclick:() => { form.hidden = true; edit.hidden = false; }}, 'Cancel'));
    mount($('title-tools'), edit, form, status);
  }
  window.SC.refreshDetail = async version => {
    const updated = await api(endpoint(version));
    if (detail.version !== version) return;
    // A GET started around another write must not erase a newer local revision.
    for (const [fp, local] of Object.entries(detail.decisions)) {
      const revision = window.SC.decisionRevisions.get(fp) || 0;
      if (revision > (updated.decisions?.[fp]?.revision || 0)) {
        throw Error('Decision saved, but the overview could not refresh. Reload to retry.');
      }
    }
    detail = updated;
    detail.decisions ||= {};
    window.SC.renderOverview(detail);
    window.dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail}));
    return detail;
  };
  window.SC.updateSurvey = async payload => {
    await api(`/api/surveys/${encodeURIComponent(surveyId)}`, 'PATCH', payload);
    const updated = await api(params.get('version') ? endpoint(Number(params.get('version'))) : `/api/surveys/${encodeURIComponent(surveyId)}`);
    detail = updated;
    detail.decisions ||= {};
    message('review-title', detail.title);
    titleEditor(); refreshDecisions();
    window.SC.renderOverview(detail);
    window.dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail}));
    return detail;
  };
  async function review() {
    detail = await api(params.get('version') ? endpoint(Number(params.get('version'))) : `/api/surveys/${encodeURIComponent(surveyId)}`);
    detail.decisions ||= {};
    message('review-title', detail.title);
    if (detail.job && ['queued', 'running'].includes(detail.job.status)) {
      lockRead(true);
      const started = Date.now();
      remember(detail.job.id, started);
      window.SC.beginReadProgress?.(started, 'review-status', true);
      try { await waitForJob(detail.job.id, 'review-status'); }
      finally { lockRead(false); window.SC.finishReadProgress?.(); }
      return review();
    }
    if (!detail.review) {
      message('review-status', detail.job?.error || 'No completed review. Return to My surveys or open Share to start a new check.', 'error');
      return;
    }
    if (detail.job?.status === 'failed') message('review-status', `${detail.job.error || 'Latest check failed.'} Showing the previous completed review.`, 'error');
    if (detail.job?.status !== 'failed') message('review-status', `Version ${detail.version} · ${params.has('unchanged') ? 'No changes found in the captured wording. ' : ''}You make changes in RedJade.`);
    titleEditor(); refreshDecisions();
    $('survey-link').value = window.SC.recheckLink(detail.source_url || detail.snapshot.source_url || '');
    $('check-again').onclick = revealRecheck;
    window.SC.loadWorkspace(detail);
  }
  window.addEventListener('surveycoach-detail-updated', event => {
    if (!detail || event.detail.id !== detail.id || event.detail.version !== detail.version) return;
    detail = event.detail;
    refreshDecisions();
  });
  window.addEventListener('surveycoach-choice-saved', event => {
    if (!detail || event.detail.version !== detail.version) return;
    detail.decisions = event.detail.decisions;
    refreshDecisions();
  });
  $("sample-start")?.addEventListener("click", () => startRead(async () => ({path:'/api/samples/boxer-briefs', body:{}})));
  // One accessible inline error path for both malformed and disallowed URLs.
  for (const id of ["import-form", "recheck-form"]) if ($(id)) $(id).noValidate = true;
  $("import-form")?.addEventListener("submit", submit);
  $("recheck-form")?.addEventListener("submit", submit);
  const saved = pending();
  if (saved) {
    lockRead(true);
    const outputId = surveyId ? 'review-status' : 'import-status';
    window.SC.beginReadProgress?.(saved.started, outputId, true);
    // Restoration only polls the opaque job reference. No survey URL or capture is stored.
    if (!surveyId) home().catch(() => {});
    waitForJob(saved.jobId, outputId).then(job => openReview(job)).catch(error => {
      message(outputId, error.message, 'error');
      window.SC.finishReadProgress?.(); lockRead(false);
      if (surveyId) review().catch(() => {});
    });
  } else {
    (surveyId ? review() : home()).catch(error => message(surveyId ? 'review-status' : 'import-status', error.message, 'error'));
  }
})();
