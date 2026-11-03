/* Private local workflow; never stores real survey content in the public demo or browser storage. */
(() => {
  "use strict";
  const { h, mount, $ } = window.SC;
  const params = new URLSearchParams(location.search), surveyId = params.get("id");
  let detail;
  const clientId = crypto.randomUUID(), revisions = new Map();
  const endpoint = (version = detail.version) => `/api/surveys/${encodeURIComponent(surveyId)}/versions/${version}`;
  async function api(path, method = "GET", body) {
    const response = await fetch(path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(typeof payload.detail === "string" ? payload.detail : `Request failed (${response.status}). Check the survey input and try again.`);
    }
    return response.json();
  }
  const message = (id, text) => { if ($(id)) $(id).textContent = text; };
  async function copy(text, output) {
    try { await navigator.clipboard.writeText(text); output.textContent = "Copied. Paste into RedJade yourself; this does not mark the issue fixed."; }
    catch (_) { output.textContent = "Clipboard unavailable. Select the text and copy it manually."; }
  }
  async function waitForJob(jobId, outputId) {
    for (let attempt = 0; attempt < 600; attempt++) {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      message(outputId, job.status === "running" ? "Review in progress. AI checks can take a few minutes…" : "Review queued…");
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
      const file = $("snapshot").files[0], ai = $("use-ai").checked;
      if (file) {
        if (file.size > 950000) throw new Error("Snapshot must be smaller than 950 KB.");
        const snapshot = JSON.parse(await file.text());
        result = await api(surveyId ? `/api/surveys/${encodeURIComponent(surveyId)}/recheck` : "/api/surveys", "POST", { snapshot, ai });
      } else {
        if (!$("survey-link").value.trim()) throw new Error("Paste an approved preview link or choose a snapshot file.");
        if (!$("approval").checked) throw new Error("Confirm that this is an approved test link with agreed test-participant handling.");
        result = await api("/api/reader/jobs", "POST", { url: $("survey-link").value.trim(), approval: true, ai, survey_id: surveyId || null });
      }
      await waitForJob(result.job_id, "import-status");
      const job = await api(`/api/jobs/${encodeURIComponent(result.job_id)}`);
      location.href = `review.html?id=${encodeURIComponent(result.id || result.survey_id || job.survey_id)}&version=${result.version || job.version}`;
    } catch (error) { message("import-status", error.message); }
    finally { button.disabled = false; }
  }
  async function home() {
    const data = await api("/api/surveys");
    mount($("survey-list"), data.surveys.length ? data.surveys.map((s) => h("div", { class: "survey-row" },
      h("div", null, h("strong", null, s.title), h("p", { class: "meta" }, `Version ${s.version}`)),
      h("a", { href: `review.html?id=${encodeURIComponent(s.id)}` }, "Open review"))) : h("p", null, "No surveys yet. Start with an approved preview link or a captured snapshot."));
  }
  async function save(finding, value, output) {
    output.textContent = "Saving…";
    const revision = (revisions.get(finding.fingerprint) || 0) + 1;
    revisions.set(finding.fingerprint, revision);
    try {
      const saved = await api(`${endpoint()}/decisions/${finding.fingerprint}`, "PUT", { ...value, client_id: clientId, revision });
      if (revision === revisions.get(finding.fingerprint)) {
        detail.decisions[finding.fingerprint] = saved;
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
      return save(finding, { action, picked_text: action === "pick" ? choices[Number(select.value)].text : null, reason: reason.value, manual_done: done.checked }, output);
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
      h("label", null, "Which version do you want?", select), preview, reason,
      h("div", { class: "actions" }, copyButton, h("label", { class: "check" }, done, "I made this change in RedJade (not verified yet)")), output,
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
    mount($("review-toolbar"), h("a", { href: `index.html?id=${encodeURIComponent(surveyId)}&version=${detail.version}` }, "Open phone preview"),
      h("a", { href: `${endpoint()}/summary`, target: "_blank", rel: "noopener" }, "Open shareable summary"), versions,
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
      r.unchecked.length > 0 && h("details", null, h("summary", null, "Checks not completed"), h("ul", null, r.unchecked.map((name) => h("li", null, name)))),
      coverage && h("details", { open: true }, h("summary", null, `Read coverage: ${coverage.pages_captured} pages captured`), h("ul", null, coverage.warnings.map((warning) => h("li", null, warning))),
        h("p", null, "Actual captured screens (only the pages the reader visited):"),
        Array.from({ length: coverage.pages_captured }, (_, index) => h("a", { href: `${endpoint()}/captures/${index}`, target: "_blank", rel: "noopener" }, `Open captured screen ${index + 1} `))),
      h("p", null, "You are responsible for the final launch decision. A snapshot preview is not a verified replica of RedJade."));
    const groups = new Map();
    r.findings.forEach((f) => { const place = f.question_id || f.page_id || "Survey-wide"; if (!groups.has(place)) groups.set(place, []); groups.get(place).push(f); });
    mount($("fix-list"), groups.size ? [...groups].map(([place, findings]) => h("section", { class: "fix-group" }, h("h3", null, place), findings.map(fixCard))) : h("p", null, "No findings in the checks run. Review the unchecked items above."));
    await changes();
  }
  $("sample-start")?.addEventListener("click", async () => {
    $("sample-start").disabled = true;
    try {
      const result = await api("/api/samples/boxer-briefs", "POST", {});
      await waitForJob(result.job_id, "import-status");
      location.href = `review.html?id=${encodeURIComponent(result.id)}`;
    } catch (error) { message("import-status", error.message); $("sample-start").disabled = false; }
  });
  $("import-form")?.addEventListener("submit", submit);
  $("recheck-form")?.addEventListener("submit", submit);
  (surveyId ? review() : home()).catch((error) => message(surveyId ? "review-status" : "import-status", error.message));
})();
