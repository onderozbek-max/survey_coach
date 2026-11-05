/* One header for every review page (brief 4.1): logo, My surveys, the survey's name (the page's only H1, editable in
   place), one version chip, the three steps, Check again, and a "How we check" overflow menu.
   Built synchronously so chapters.js finds #chapter-nav; SC.renderHeader fills in the survey once it is known. */
(() => {
  'use strict';
  const SC = window.SC, {h, $, icon} = SC;
  const host = $('app-header');
  if (!host) return;
  const STEPS = [['overview', 'Verdict'], ['improve', 'Fix'], ['share', 'Sign off']];
  let detail = null;

  const title = h('h1', {id: 'review-title'}, 'Opening your survey…');
  const renameButton = h('button', {type: 'button', id: 'rename-survey', class: 'icon-btn', hidden: true, 'aria-label': 'Rename survey'}, icon('pencil'));
  const chip = h('span', {id: 'version-chip', class: 'version-chip', hidden: true});
  const status = h('span', {class: 'rename-status', role: 'status'});
  const input = h('input', {type: 'text', id: 'survey-name', maxlength: 200, 'aria-label': 'Survey name'});
  const cancel = h('button', {type: 'button', id: 'rename-cancel', class: 'btn btn-secondary'}, 'Cancel');
  const form = h('form', {id: 'rename-form', class: 'rename-form', hidden: true},
    input, h('button', {type: 'submit', class: 'btn btn-primary'}, 'Save'), cancel);

  const canEdit = () => Boolean(detail && SC.updateSurvey && !SC.readOnly);
  function setEditing(editing) {
    const was = !form.hidden;
    form.hidden = !editing;
    title.hidden = editing;
    renameButton.hidden = editing || !canEdit();
    if (editing) { input.value = SC.surveyName(detail.title) === 'Untitled survey' ? '' : detail.title; input.focus(); input.select(); }
    else if (was && canEdit()) renameButton.focus();   // only when leaving the editor, never on page load
  }
  renameButton.addEventListener('click', () => setEditing(true));
  title.addEventListener('click', () => { if (canEdit()) setEditing(true); });
  cancel.addEventListener('click', () => setEditing(false));
  form.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); setEditing(false); } });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const name = input.value.trim();
    if (!name) { status.textContent = 'Enter a name.'; input.focus(); return; }
    const save = form.querySelector('[type=submit]'); save.disabled = true;
    try { await SC.updateSurvey({title: name}); status.textContent = 'Name saved.'; }
    catch (error) { status.textContent = error.message; }
    finally { save.disabled = false; }
  });

  const stepLinks = STEPS.map(([name, label], index) => h('a', {href: `#${name}`, 'data-chapter': name},
    h('span', {class: 'step-n', 'aria-hidden': 'true'}, String(index + 1)), label));
  const nav = h('nav', {id: 'chapter-nav', 'aria-label': 'Review steps'}, stepLinks);
  const stepsLabel = h('span', {id: 'steps-current'}, STEPS[0][1]);
  const stepsButton = h('button', {type: 'button', id: 'steps-button', class: 'btn btn-secondary hdr-steps', 'aria-controls': 'chapter-nav'},
    stepsLabel, icon('chevron-down'));
  const checkAgain = h('button', {type: 'button', id: 'check-again', class: 'btn btn-secondary', hidden: true},
    icon('refresh'), h('span', {class: 'btn-label'}, 'Check again'));
  const menuButton = h('button', {type: 'button', id: 'header-menu-button', class: 'icon-btn', 'aria-haspopup': 'menu',
    'aria-controls': 'header-menu', 'aria-label': 'More options'}, icon('more'));
  const menu = h('div', {id: 'header-menu', class: 'hdr-menu', role: 'menu', 'aria-label': 'More options'},
    h('a', {href: 'local.html', role: 'menuitem', class: 'menu-mysurveys'}, 'My surveys'),
    h('button', {type: 'button', id: 'about-review', role: 'menuitem', 'aria-haspopup': 'dialog', 'aria-controls': 'about-review-dialog'}, 'How we check'));

  host.append(
    h('a', {href: 'local.html', class: 'hdr-brand', 'aria-label': 'SurveyCoach home'},
      SC.logoMark(), h('span', {class: 'brand-word'}, 'Survey', h('span', null, 'Coach'))),
    h('a', {href: 'local.html', class: 'hdr-mysurveys'}, 'My surveys'),
    h('div', {class: 'hdr-title'}, h('div', {class: 'hdr-name'}, title, renameButton, form, status), chip),
    h('div', {class: 'hdr-steps-wrap'}, stepsButton, nav),
    h('div', {class: 'hdr-actions'}, checkAgain, h('div', {class: 'hdr-more'}, menuButton, menu)));

  const stepsMenu = SC.disclosure(stepsButton, nav);
  SC.menu(menuButton, menu);
  window.addEventListener('surveycoach-chapter', event => {
    const label = STEPS.find(([name]) => name === event.detail.name)?.[1];
    if (label) stepsLabel.textContent = label;
    stepsButton.setAttribute('aria-label', `Review steps, current step: ${stepsLabel.textContent}`);
    stepsMenu.close();
  });

  // Sticky bars below the header offset themselves by its real height (it wraps on narrower screens).
  new ResizeObserver(() => document.documentElement.style.setProperty('--header-h', `${host.getBoundingClientRect().height}px`)).observe(host);

  /** The name, version chip and actions for the survey on screen. Safe to call again after a rename. */
  SC.renderHeader = (survey, {recheck = Boolean(SC.updateSurvey)} = {}) => {
    detail = survey;
    const name = SC.surveyName(survey.title);
    title.textContent = name;
    document.title = `${name} · SurveyCoach`;
    const stamp = survey.created_at || survey.versions?.find(v => v.version === survey.version)?.created_at;
    chip.hidden = !survey.version;
    chip.textContent = survey.version ? `v${survey.version} · checked ${SC.ago(stamp)}` : '';
    checkAgain.hidden = !recheck;
    status.textContent = '';
    setEditing(false);
  };
})();
