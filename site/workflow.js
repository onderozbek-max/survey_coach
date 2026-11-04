/* Private local workflow; never stores real survey content in the public demo or browser storage. */
(() => {
  "use strict";
  const { h, mount, $, plural } = window.SC;
  const params = new URLSearchParams(location.search), surveyId = params.get("id");
  let detail;
  const endpoint = (version = detail.version) => `/api/surveys/${encodeURIComponent(surveyId)}/versions/${version}`;
  async function api(path, method = "GET", body) {
    const response = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}). Check the survey input and try again.`);
    }
    return response.json();
  }
  // tone: "info" | "progress" | "error"; styled where a page opts in (home.css).
  const message = (id, text, tone = "info") => { const el = $(id); if (el) { el.textContent = text; el.dataset.tone = tone; } };
  async function copy(text, output) {
    try { await navigator.clipboard.writeText(text); output.textContent = "Copied. Paste into RedJade yourself; this does not mark the issue fixed."; }
    catch (_) { output.textContent = "Clipboard unavailable. Select the text and copy it manually."; }
  }
  async function waitForJob(jobId, outputId) {
    for (let attempt = 0; attempt < 600; attempt++) {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      window.SC.renderReadProgress?.(job, jobId);
      const stage = job.stage === 'reading' ? job.pages_captured ? `Reading screen ${job.pages_captured}…` : 'Opening the test survey…'
        : job.stage === 'checking' ? `${job.pages_captured || 0} screens captured. Checking wording and flow…`
        : job.status === 'running' ? 'Checking survey wording and flow. AI checks can take a few minutes…' : 'Review queued…';
      message(outputId, stage, "progress");
      if (job.status === "failed") throw new Error(job.error || "Review did not finish. Your previous review is unchanged.");
      if (job.status === "completed") return;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    let resume = $('resume-checking');
    if (!resume) {
      resume = h('button', {type:'button',id:'resume-checking',class:'btn',onclick:async()=>{
        resume.disabled=true;
        try { await waitForJob(jobId,outputId); const finished=await api(`/api/jobs/${encodeURIComponent(jobId)}`);
          location.href=`review.html?id=${encodeURIComponent(finished.survey_id)}&version=${finished.version}`;
        } catch(error) { message(outputId,error.message,'error'); resume.disabled=false; }
      }},'Resume checking');
      $(outputId).after(resume);
    }
    throw new Error(`Still working. Keep this page open and use Resume checking; do not start another review. Reference ${jobId.slice(0,8)}.`);
  }
  async function submit(event) {
    event.preventDefault();
    const button = event.target.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      let result;
      const file = $("snapshot")?.files[0], ai = true;
      if (file) {
        if (file.size > 950000) throw new Error("Snapshot must be smaller than 950 KB.");
        const snapshot = JSON.parse(await file.text());
        result = await api(surveyId ? `/api/surveys/${encodeURIComponent(surveyId)}/recheck` : "/api/surveys", "POST", { snapshot, ai });
      } else {
        if (!$("survey-link").value.trim()) throw new Error("Paste an approved preview link or choose a snapshot file.");
        const value = $("survey-link").value.trim();
        let url;
        try { url = new URL(value); } catch (_) { /* handled by the shared message below */ }
        if (!url || url.protocol !== "https:" ||
            !(url.hostname === "redjade.net" || url.hostname.endsWith(".redjade.net")) ||
            url.username || url.password || url.search || url.hash || url.port || /[\s\\]/.test(value)) {
          throw new Error("Use a valid HTTPS RedJade test link without credentials, query parameters, or a fragment.");
        }
        result = await api("/api/reader/jobs", "POST", { url: value, approval: true, ai, survey_id: surveyId || null });
      }
      await waitForJob(result.job_id, "import-status");
      const job = await api(`/api/jobs/${encodeURIComponent(result.job_id)}`);
      location.href = `review.html?id=${encodeURIComponent(result.id || result.survey_id || job.survey_id)}&version=${result.version || job.version}${result.deduplicated || job.deduplicated ? '&unchanged=1' : ''}${surveyId ? '' : '#overview'}`;
    } catch (error) { message("import-status", error.message, "error"); }
    finally { button.disabled = false; }
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
      await waitForJob(detail.job.id, 'review-status'); return review();
    }
    if (!detail.review) { message('review-status', detail.job?.error || 'No completed review. Try checking again below.'); return; }
    message('review-status', `Round ${detail.version} · ${params.has('unchanged') ? 'No changes found in the captured wording. ' : ''}You make changes in RedJade.`);
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
  $("sample-start")?.addEventListener("click", async () => {
    $("sample-start").disabled = true;
    try {
      const result = await api("/api/samples/boxer-briefs", "POST", {});
      await waitForJob(result.job_id, "import-status");
      location.href = `review.html?id=${encodeURIComponent(result.id)}#overview`;
    } catch (error) { message("import-status", error.message, "error"); $("sample-start").disabled = false; }
  });
  // One accessible inline error path for both malformed and disallowed URLs.
  for (const id of ["import-form", "recheck-form"]) if ($(id)) $(id).noValidate = true;
  $("import-form")?.addEventListener("submit", submit);
  $("recheck-form")?.addEventListener("submit", submit);
  (surveyId ? review() : home()).catch((error) => message(surveyId ? "review-status" : "import-status", error.message, "error"));
})();
