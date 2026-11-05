/* Private local workflow; never stores real survey content in the public demo or browser storage. */
(() => {
  "use strict";
  const { h, mount, $, plural } = window.SC;
  const params = new URLSearchParams(location.search), surveyId = params.get("id");
  let detail, activeRead = false, uncertainSubmission = false;   // uncertain: an earlier POST may still be running
  const pendingKey = 'surveycoach-pending-job';
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  function storePending(value) {
    // One key / one atomic replacement: never remove the uncertain marker before storing a known job.
    try { sessionStorage.setItem(pendingKey, JSON.stringify(value)); return true; }
    catch (_) { return false; }
  }
  function storageWarning() {
    if ($('reading-storage-warning')) return;
    $('reading-actions')?.append(h('p', {id:'reading-storage-warning', role:'status'},
      'Session storage is unavailable. This page cannot recover this request after a reload. Keep it open; do not reload and submit again.'));
  }
  function remember(jobId, started) {
    if (uncertainSubmission) return;      // the unknown marker is never replaced by a guess
    if (!storePending({jobId, started})) storageWarning();
  }
  // Shown above an existing review that was opened while an earlier request is unconfirmed.
  const calmNotice = 'Request status unknown. A recent check may still be running, so new checks and edits are paused. You can read this review here. Check My surveys or ask the local pilot owner to confirm.';
  const uncertainMessage = 'Request status unknown. A test response may already exist. Check My surveys or contact the local pilot owner to verify the request. Do not submit again while it may be running. No job reference was received, so this page cannot resume status checks.';
  function showUncertain(outputId) {
    message(outputId, uncertainMessage, 'error');
    window.SC.readConnection?.('Request needs attention.', true);
    window.SC.finishReadProgress?.();
  }
  function forget() {
    if (uncertainSubmission) return;      // nor cleared: only the owner can confirm what happened
    try { sessionStorage.removeItem(pendingKey); } catch (_) {}
  }
  function pending() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(pendingKey));
      if (Number.isFinite(saved?.started)) {
        // Age or clock rollback cannot prove a job stopped; elapsed display clamps separately.
        if (saved.submissionPending === true) return {submissionPending:true, started:saved.started};
        if (typeof saved.jobId === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(saved.jobId)) return {jobId:saved.jobId, started:saved.started};
      }
    } catch (_) {}
    forget(); return null;
  }
  function lockRead(locked) {
    if (!locked && uncertainSubmission) return;   // new submissions stay locked in this tab; reading is never blocked
    activeRead = locked;
    for (const control of document.querySelectorAll('#import-form input, #import-form button[type=submit], #recheck-form input, #recheck-form button[type=submit], #sample-start, #check-again, #recheck-cancel')) {
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
  window.SC.isReading = () => activeRead;
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
        error.status = response.status;
        error.rejected = response.status >= 400 && response.status < 500 && response.status !== 408;
        throw error;
      }
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  window.SC.api = api;       // the one fetch path, shared with the sign-off step
  // tone: "info" | "progress" | "error"; styled where a page opts in (home.css).
  const message = (id, text, tone = "info") => { const el = $(id); if (el) { el.textContent = text; el.dataset.tone = tone; } };
  async function copy(text, output) {
    try { await navigator.clipboard.writeText(text); output.textContent = "Copied. Paste into RedJade yourself; this does not mark the issue fixed."; }
    catch (_) { output.textContent = "Clipboard unavailable. Select the text and copy it manually."; }
  }
  function announce(outputId, text, tone = 'progress') {
    if ($(outputId)?.textContent !== text) message(outputId, text, tone);
  }
  async function pauseChecking(jobId, outputId, text = 'Status checks paused. The job may still be working. Resume checking this same job; do not start another review.') {
    window.SC.readConnection?.('Review needs attention.', true);
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
      catch (error) {
        if (error.status === 404) {
          await pauseChecking(jobId, outputId, 'Request status unknown. We cannot verify this job has stopped. Check My surveys or contact the local pilot owner. Do not submit again while it may be running. Resume checking only checks this existing job.');
          errors = 0; continue;
        }
        errors++;
        const text = 'Connection interrupted. Waiting for a status response; retrying this job only. No new survey response will be created.';
        window.SC.readConnection?.('Waiting to reconnect. See the status message above.');
        announce(outputId, text, 'error');
        if (errors >= 3) { await pauseChecking(jobId, outputId); errors = 0; attempt = 0; }
        else await sleep(2000);
        continue;
      }
      errors = 0;
      const text = window.SC.renderReadProgress?.(job, jobId, outputId);
      announce(outputId, text || 'Waiting for the next job update.', job.status === 'failed' ? 'error' : 'progress');
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
      if (!storePending({submissionPending:true, started})) storageWarning();
      submitted = true;
      const result = await api(request.path, 'POST', request.body);
      if (typeof result.job_id !== 'string' || !result.job_id) throw new Error('No job reference returned.');
      accepted = true;
      remember(result.job_id, started);
      const job = await waitForJob(result.job_id, 'import-status');
      openReview(job, result);
    } catch (error) {
      ambiguous = submitted && !accepted && !error.rejected;
      if (submitted && !accepted && error.rejected) forget();
      const text = ambiguous ? uncertainMessage : error.message;
      announce('import-status', text, 'error');
      window.SC.readConnection?.('Review needs attention.', true);
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
  async function home() {
    const data = await api("/api/surveys");
    message("survey-count", data.surveys.length ? plural(data.surveys.length, "survey") : "");
    mount($("survey-list"), data.surveys.length ? data.surveys.map(window.SC.surveyCard)
      : h("p", { class: "empty" }, h("strong", null, "Nothing reviewed yet"), "Paste a link above, or try the sample survey to see what a review looks like."));
  }
  function refreshDecisions() {
    window.SC.workspaceDetail = detail;
    mount($('fix-list'), window.SC.renderIssueList(detail));
    window.SC.renderShare(detail, copy);   // renders the sign-off step too
    const kept = window.SC.issueCounts(detail).kept;
    message('decision-verdict', kept ? `${kept} kept on purpose · accepted risk, not verified fixes.` : '');
  }
  /** Check again: the dialog opens prefilled with the last safe link. Submitting reuses the one read path (startRead). */
  function openRecheck() {
    const dialog = $('recheck-dialog');
    $('survey-link').value ||= window.SC.recheckLink(detail.source_url || detail.snapshot?.source_url || '');
    if (!dialog.open) dialog.showModal();
    $('survey-link').focus({preventScroll:true});
  }
  $('recheck-cancel')?.addEventListener('click', () => $('recheck-dialog').close());
  // A check that is running owns the dialog: Escape must not hide its progress.
  $('recheck-dialog')?.addEventListener('cancel', event => { if (activeRead) event.preventDefault(); });
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
    window.SC.renderHeader(detail);
    refreshDecisions();
    window.SC.renderOverview(detail);
    window.dispatchEvent(new CustomEvent('surveycoach-detail-updated', {detail}));
    return detail;
  };
  /** The status line above a review. While a request is unconfirmed it also carries the calm notice. */
  const reviewStatus = (text, tone = 'info') => message('review-status',
    uncertainSubmission ? `${calmNotice} ${text}` : text, uncertainSubmission && tone !== 'error' ? 'notice' : tone);
  async function review(carriedFailure = null) {
    detail = await api(params.get('version') ? endpoint(Number(params.get('version'))) : `/api/surveys/${encodeURIComponent(surveyId)}`);
    detail.decisions ||= {};
    window.SC.renderHeader(detail);
    $('check-again').onclick = openRecheck;
    if (detail.job && ['queued', 'running'].includes(detail.job.status)) {
      lockRead(true);
      const started = Date.now();
      remember(detail.job.id, started);
      window.SC.beginReadProgress?.(started, 'review-status', true);
      let failure = carriedFailure;
      try { await waitForJob(detail.job.id, 'review-status'); }
      catch (error) { failure = error.message; }       // the recheck failed; the previous review is still valid, so load it
      finally { lockRead(false); window.SC.finishReadProgress?.(); }
      return review(failure);
    }
    if (!detail.review) {
      reviewStatus(carriedFailure || detail.job?.error || 'No completed review yet. Use Check again, or return to My surveys.', 'error');
      return;
    }
    const failure = carriedFailure || (detail.job?.status === 'failed' ? detail.job.error || 'Latest check failed.' : null);
    if (failure) reviewStatus(`${failure} Showing the previous completed review.`, 'error');
    else reviewStatus(params.has('unchanged') ? 'We found no wording changes since the last version.' : '');
    refreshDecisions();
    $('survey-link').value = window.SC.recheckLink(detail.source_url || detail.snapshot.source_url || '');
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
    if (saved.submissionPending && surveyId) {
      // Submissions stay locked, but an existing review opens read-only: no job reference is guessed or touched.
      uncertainSubmission = true;
      window.SC.readOnly = {reason:'Read-only while an earlier request is unconfirmed.'};
      review().catch(error => message('review-status', error.message, 'error'));
    } else {
      window.SC.beginReadProgress?.(saved.started, outputId, true);
      // No correlation guess from survey listings: unknown submissions have no safe job reference.
      if (!surveyId) home().catch(() => {});
      if (saved.submissionPending) { uncertainSubmission = true; showUncertain(outputId); }
      else waitForJob(saved.jobId, outputId).then(job => openReview(job)).catch(error => {
        announce(outputId, error.message, 'error');
        window.SC.finishReadProgress?.(); lockRead(false);
        if (surveyId) review(error.message).catch(() => {});
      });
    }
  } else {
    (surveyId ? review() : home()).catch(error => message(surveyId ? 'review-status' : 'import-status', error.message, 'error'));
  }
})();
