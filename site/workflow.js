/* Private local workflow; never stores real survey content in the public demo or browser storage. */
(() => {
  "use strict";
  const { h, mount, $, plural, READINESS } = window.SC;
  const params = new URLSearchParams(location.search), surveyId = params.get("id");
  let detail;
  const clientId = window.SC.decisionClient, revisions = window.SC.decisionRevisions;
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
      message(outputId, job.status === "running" ? "Review in progress. AI checks can take a few minutes…" : "Review queued…", "progress");
      if (job.status === "failed") throw new Error(job.error || "Review did not finish. Your previous review is unchanged.");
      if (job.status === "completed") return;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("Still working. Return to My surveys to reopen this review; do not start another copy.");
  }
  async function submit(event) {
    event.preventDefault();
    const button = event.target.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      let result;
      const file = $("snapshot").files[0], ai = true;
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
      location.href = `review.html?id=${encodeURIComponent(result.id || result.survey_id || job.survey_id)}&version=${result.version || job.version}`;
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
      s.must_fix != null && h("span", { class: s.must_fix ? "red" : null }, `${s.must_fix} must fix`),
      s.score_checked && h("span", null, `${s.score_checked[0]} of ${s.score_checked[1]} checked points`),
      h("span", null, `Version ${s.version}`), h("span", null, `Updated ${since(s.created_at)}`)),
    h("span", { class: "card-open", "aria-hidden": "true" }, "Open review →"));
  async function home() {
    const data = await api("/api/surveys");
    message("survey-count", data.surveys.length ? plural(data.surveys.length, "survey") : "");
    mount($("survey-list"), data.surveys.length ? data.surveys.map(surveyCard)
      : h("p", { class: "empty" }, h("strong", null, "Nothing reviewed yet"), "Paste a link above, or try the sample survey to see what a review looks like."));
  }
  async function save(finding, value, output) {
    output.textContent = "Saving…";
    const revision = (revisions.get(finding.fingerprint) || 0) + 1;
    revisions.set(finding.fingerprint, revision);
    try {
      const saved = await api(`${endpoint()}/decisions/${finding.fingerprint}`, "PUT", { ...value, client_id: clientId, revision });
      if (revision === revisions.get(finding.fingerprint)) {
        detail.decisions[finding.fingerprint] = saved;
        window.dispatchEvent(new CustomEvent('surveycoach-decisions', { detail }));
        output.textContent = "Saved on this computer.";
      }
      return true;
    } catch (error) { output.textContent = `Not saved: ${error.message}`; return false; }
  }
  function fixCard(finding) {
    const saved = detail.decisions[finding.fingerprint] || { action: "open", reason: "", manual_done: false };
    const choices = window.SC.choicesOf(finding);
    const select = h("select", { "aria-label": `Version for ${finding.headline}` },
      h("option", { value: "open", selected: saved.action === "open" }, "Choose a version…"),
      h("option", { value: "original", selected: ["original", "keep"].includes(saved.action) }, "Keep my original"),
      choices.map((choice, i) => h("option", { value: String(i), selected: saved.action === "pick" && choice.text === saved.picked_text }, choice.label)));
    const preview = h("blockquote", null), output = h("p", { role: "status", class: "saved" });
    const reason = h("textarea", { "aria-label": `Reason for keeping ${finding.headline}`, placeholder: "Why keep it? For example: required wording or comparability.", value: saved.reason });
    reason.value = saved.reason || "";
    const done = h("input", { type: "checkbox", checked: saved.manual_done });
    const copyButton = h("button", { class: "btn", type: "button", onclick: () => copy(preview.textContent, output) }, "Copy chosen fix");
    const update = () => {
      const pick = choices[Number(select.value)];
      preview.textContent = select.value === "original" ? (finding.current_text || finding.evidence) : pick?.text || "Choose a suggested version to preview and copy it.";
      copyButton.disabled = ["open", "original"].includes(select.value);
      reason.hidden = select.value !== "original";
    };
    const persist = async () => {
      const action = select.value === "original" ? (reason.value.trim() ? "keep" : "original") : select.value === "open" ? "open" : "pick";
      return save(finding, { action, picked_text: action === "pick" ? choices[Number(select.value)]?.text || null : null, reason: reason.value, manual_done: done.checked }, output);
    };
    select.onchange = () => { update(); persist(); };
    done.onchange = persist;
    reason.onchange = persist;
    update();
    const askInput = h("textarea", { "aria-label": `Question about ${finding.headline}`, placeholder: "Ask why this matters or how to improve it." });
    const askOutput = h("p", { role: "status" });
    const askButton = h("button", { type: "button", class: "btn", onclick: async () => {
      if (!askInput.value.trim()) { askOutput.textContent = "Type a question first."; return; }
      askButton.disabled = true;
      askOutput.textContent = "Asking the coach…";
      try {
        const answer = await api(`${endpoint()}/ask`, "POST", { fingerprint: finding.fingerprint, question: askInput.value });
        askOutput.textContent = `${answer.answer}\n${answer.warning}`;
      } catch (error) { askOutput.textContent = error.message; }
      finally { askButton.disabled = false; }
    } }, "Ask the coach");
    const question = detail.snapshot.pages.flatMap((p) => p.questions).find((q) => q.id === finding.question_id);
    return h("article", { class: "fix-card" },
      h("p", { class: "meta" }, `${finding.severity === "must_fix" ? "Must fix" : "Worth improving"} · ${finding.source === "ai" ? "AI—check before use" : "Local check"} · ${finding.criterion_id}`),
      h("h3", null, finding.headline), h("blockquote", null, finding.evidence),
      h("p", null, finding.explanation), h("p", null, finding.member_impact),
      question && h("details", null, h("summary", null, "See the original question and answer choices"), h("p", null, question.text), h("ul", null, question.options.map((o) => h("li", null, o.label)))),
      h("label", null, choices.length ? "Which version do you want?" : "Decision on this finding", select),
      choices.length ? preview : h("p", { class: "note" }, "Action required · No ready-to-use rewrite. Follow the guidance above and verify the result in RedJade."), reason,
      h("div", { class: "actions" }, choices.length ? copyButton : null, h("label", { class: "check" }, done, "I made this change in RedJade (not verified yet)")), output,
      h("details", null, h("summary", null, "Ask about this finding"), h("p", null, "Uses Wibey AI and sends survey wording. Check its answer before use."), askInput, askButton, askOutput));
  }
  async function changes() {
    if (detail.version < 2) return;
    const previous = await api(`/api/surveys/${encodeURIComponent(surveyId)}/versions/${detail.version - 1}`);
    const oldFindings = previous.review?.findings || [], current = detail.review.findings;
    const key = (f) => `${f.criterion_id}:${f.page_id || ""}:${f.question_id || ""}`;
    const unchecked = !detail.review.ai || detail.review.unchecked.length || Object.keys(detail.review.ai.failed).length;
    const disappeared = oldFindings.filter((f) => !current.some((n) => key(n) === key(f)));
    const newCount = current.filter((f) => !oldFindings.some((n) => key(n) === key(f))).length;
    mount($("version-changes"), h("h2", null, "Since the previous version"),
      h("p", null, `${newCount} newly flagged. ${current.length - newCount} still flagged. ${disappeared.length} previously flagged locations are no longer flagged.`),
      h("p", null, unchecked ? "Some checks are incomplete. Not flagged does not mean verified resolved." : "Review changed wording and advice before deciding a problem is resolved."));
  }
  async function review() {
    detail = await api(params.get("version") ? `${endpoint(Number(params.get("version")))}` : `/api/surveys/${encodeURIComponent(surveyId)}`);
    message("review-title", detail.title);
    if (detail.job && ["queued", "running"].includes(detail.job.status)) {
      await waitForJob(detail.job.id, "review-status");
      return review();
    }
    if (!detail.review) { message("review-status", detail.job?.error || "No completed review. Try checking again below."); return; }
    const r = detail.review, c = r.scorecard;
    message("review-status", `Version ${detail.version} · Saved on this computer. You make all changes in RedJade.`);
    const versions = h("select", { "aria-label": "Review version", onchange: (e) => { location.href = `review.html?id=${encodeURIComponent(surveyId)}&version=${e.target.value}`; } },
      detail.versions.map((v) => h("option", { value: v.version, selected: v.version === detail.version }, `Version ${v.version}`)));
    const copyStatus = h("p", { role: "status" });
    mount($("review-toolbar"),
      h("a", { href: `${endpoint()}/summary`, target: "_blank", rel: "noopener" }, "Export review report"), versions,
      h("button", { type: "button", class: "btn", onclick: () => {
        const text = r.findings.flatMap((f) => { const d = detail.decisions[f.fingerprint]; return d?.action === "pick" ? [`${f.question_id || f.page_id || "Survey"}: ${f.headline}\n${d.picked_text}`] : []; }).join("\n\n");
        if (!text) { copyStatus.textContent = "Choose at least one suggested fix first. Original choices are not copied."; return; }
        copy(text, copyStatus);
      } }, "Copy all chosen fixes"), copyStatus);
    const failed = Object.keys(r.ai?.failed || {});
    const coverage = detail.coverage;
    mount($("review-summary"), h("h2", null, c.readiness === "needs_work" ? "Fix the must-fix issues before launch." : c.readiness === "ready" ? "No launch blockers found in the checks run." : "Review incomplete or improvements remain."),
      h("p", null, `${r.findings.filter((f) => f.severity === "must_fix").length} must fix · ${r.findings.filter((f) => f.severity !== "must_fix").length} worth improving · about ${r.est_minutes} minutes for members`),
      h("p", null, `${Math.round(c.score - c.unchecked_points)} of ${100 - c.unchecked_points} checked points earned. ${c.unchecked_points} points not checked.`),
      h("p", null, !r.ai ? "AI checks have not run." : failed.length ? `AI could not check: ${failed.join(", ")}.` : "AI review completed. Its advice still needs your judgment."),
      failed.length > 0 && h("ul", { role: "status" }, [...new Set(Object.values(r.ai.failed))].map((reason) => h("li", null, reason))),
      r.unchecked.length > 0 && h("details", null, h("summary", null, "Checks not completed"), h("ul", null, r.unchecked.map((name) => h("li", null, name)))),
      coverage && h("details", { open: true }, h("summary", null, `Read coverage: ${coverage.pages_captured} pages captured`), h("p", null, `Reader stopped: ${coverage.stop_reason}. This does not establish full branching coverage.`), h("ul", null, coverage.warnings.map((warning) => h("li", null, warning))),
        h("p", null, "Actual captured screens (only the pages the reader visited):"),
        Array.from({ length: coverage.pages_captured }, (_, index) => h("a", { href: `${endpoint()}/captures/${index}`, target: "_blank", rel: "noopener" }, `Open captured screen ${index + 1} `))),
      h("p", null, "You are responsible for the final launch decision. A snapshot preview is not a verified replica of RedJade."));
    const groups = new Map();
    r.findings.forEach((f) => { const place = f.question_id || f.page_id || "Survey-wide"; if (!groups.has(place)) groups.set(place, []); groups.get(place).push(f); });
    mount($("fix-list"), groups.size ? [...groups].map(([place, findings]) => h("section", { class: "fix-group" }, h("h3", null, place), findings.map(fixCard))) : h("p", null, "No findings in the checks run. Review the unchecked items above."));
    window.SC.loadWorkspace?.(detail);
    await changes();
  }
  window.addEventListener('surveycoach-choice-saved', event => {
    detail.decisions = event.detail.decisions;
    // Refresh checklist from the same saved state without replacing the phone workspace.
    const groups = new Map();
    detail.review.findings.forEach(f => { const place = f.question_id || f.page_id || 'Survey-wide'; if (!groups.has(place)) groups.set(place, []); groups.get(place).push(f); });
    mount($('fix-list'), [...groups].map(([place, findings]) => h('section', {class:'fix-group'}, h('h3', null, place), findings.map(fixCard))));
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
