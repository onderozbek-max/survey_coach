/* Private local workflow; never stores real survey content in the public demo or browser storage. */
(() => {
  "use strict";
  const { h, mount, $, plural, READINESS } = window.SC;
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
      const stage = job.stage === 'reading' ? `Reading screen ${job.pages_captured || 1}…`
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
      location.href = `review.html?id=${encodeURIComponent(result.id || result.survey_id || job.survey_id)}&version=${result.version || job.version}${result.deduplicated || job.deduplicated ? '&unchanged=1' : ''}`;
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
  const surveyCard = (s) => h("a", { class: "survey-card", href: `review.html?id=${encodeURIComponent(s.id)}` },
    h("div", null, h("span", { class: `chip ${s.readiness || ""}` }, READINESS[s.readiness] || "Not reviewed")),
    h("h3", null, s.title),
    h("div", { class: "card-meta" },
      s.must_fix != null && h("span", { class: s.must_fix ? "red" : null }, `${s.must_fix} to fix before launch`),
      s.score_checked && h("span", null, `${s.score_checked[0]} of ${s.score_checked[1]} checked points`),
      h("span", null, `Round ${s.version}`), h("span", null, `Updated ${since(s.created_at)}`)),
    h("span", { class: "card-open", "aria-hidden": "true" }, "Open review →"));
  async function home() {
    const data = await api("/api/surveys");
    message("survey-count", data.surveys.length ? plural(data.surveys.length, "survey") : "");
    mount($("survey-list"), data.surveys.length ? data.surveys.map(surveyCard)
      : h("p", { class: "empty" }, h("strong", null, "Nothing reviewed yet"), "Paste a link above, or try the sample survey to see what a review looks like."));
  }
  function renderSummary() {
    const r = detail.review, card = r.scorecard, coverage = detail.coverage;
    const stops = {
      definition_captured: 'Read the available survey definition.', final_control: 'Reached the final survey control.',
      path_end: 'Reached the end of the observed path.', screen_out: 'Reached a screening exit.',
      unsupported: 'Stopped at a control the reader could not safely use.', unmet_requirement: 'Could not meet a page requirement.',
      time_limit: 'Stopped at the time limit.', page_limit: 'Stopped at the screen limit.', loop: 'Stopped after a repeated screen.',
      blocked: 'A safety restriction stopped the read.', reader_error: 'The reader could not finish.',
      external_progression_unverified: 'Could not verify progress in the survey.', same_page_change: 'The screen changed without confirmed progress.',
      not_started: 'The read has not started.'
    };
    mount($("review-summary"), h('p', null, coverage
      ? `${coverage.pages_captured} captured screens checked. ${stops[coverage.stop_reason] || 'The read stopped before all paths could be verified.'}`
      : 'Imported survey screens checked; capture completeness was not independently verified.'),
      h('p', null, `${!r.ai ? 'AI wording checks have not run. ' : Object.keys(r.ai.failed || {}).length ? 'Some AI checks did not finish. ' : 'AI advice needs your judgment. '}Unvisited paths are not checked. This is not launch approval.`),
      r.unchecked?.length > 0 && h('details', null, h('summary', null, `${r.unchecked.length} checks not completed`), h('ul', null, r.unchecked.map(name => h('li', null, name)))),
      r.projection?.score_limitations?.map(text => h('p',{class:'note'},text)),
      h('details', null, h('summary', null, 'Technical details & source evidence'),
        h('p', null, `${Math.round(window.SC.scoreDisplay(card).earned)} of ${window.SC.scoreDisplay(card).checked} checked points earned. ${card.unchecked_points} points unchecked.`),
        coverage && h('p', null, `Reader stop code: ${coverage.stop_reason}`),
        coverage && h('ul', null, (coverage.warnings || []).map(w => h('li', null, w))),
        coverage && Array.from({length:coverage.pages_captured}, (_, i) => h('a', {href:`${endpoint()}/captures/${i}`, target:'_blank', rel:'noopener'}, `Captured screen ${i + 1} `))));
  }
  function refreshDecisions() {
    window.SC.workspaceDetail = detail;
    mount($('fix-list'), window.SC.renderIssueList(detail));
    mount($('change-sheet'), window.SC.renderChangeSheet(detail));
    const count = window.SC.issueCounts(detail).chosen;
    $('copy-all').textContent = `Copy all changes (${count})`;
    $('copy-all').disabled = count === 0;
    const kept = window.SC.issueCounts(detail).kept;
    message('decision-verdict', kept ? `${kept} kept on purpose · accepted risk, not verified fixes.` : '');
  }
  function revealRecheck() {
    $('recheck-details').open = true;
    $('survey-link').value ||= detail.source_url || detail.snapshot.source_url || '';
    $('recheck-panel').scrollIntoView({block:'center', behavior:'smooth'});
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
    titleEditor(); renderSummary(); refreshDecisions();
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
    titleEditor(); renderSummary(); refreshDecisions();
    mount($('version-changes'), window.SC.renderRounds(detail, surveyId));
    $('survey-link').value = detail.source_url || detail.snapshot.source_url || '';
    $('check-again').onclick = revealRecheck;
    $('sign-off').href = `${endpoint()}/summary`;
    $('copy-all').onclick = () => copy(window.SC.changeSheetText(detail), $('action-status'));
    window.SC.loadWorkspace(detail);
  }
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
      location.href = `review.html?id=${encodeURIComponent(result.id)}`;
    } catch (error) { message("import-status", error.message, "error"); $("sample-start").disabled = false; }
  });
  // One accessible inline error path for both malformed and disallowed URLs.
  for (const id of ["import-form", "recheck-form"]) if ($(id)) $(id).noValidate = true;
  $("import-form")?.addEventListener("submit", submit);
  $("recheck-form")?.addEventListener("submit", submit);
  (surveyId ? review() : home()).catch((error) => message(surveyId ? "review-status" : "import-status", error.message, "error"));
})();
