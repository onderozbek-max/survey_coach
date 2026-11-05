/* Setup confirmation on the Verdict (brief 4.8): "Two quick checks so the verdict is right".
   (a) Is this the right survey type?  (b) Does the survey offer a reward?
   Never blocks the verdict. Both saves are optimistic, report an error with Retry, and cannot be submitted twice. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const TYPES = [['community_pulse', 'Community & fun', 'community survey'], ['non_ihut_product', 'Product test', 'product test'],
    ['ihut', 'Home-use test', 'home-use test'], ['services_concept', 'Concept or services', 'concept test'], ['market_research', 'Market research', 'market research survey']];
  const noun = type => TYPES.find(row => row[0] === type)?.[2] || 'survey';
  const capital = text => text.charAt(0).toUpperCase() + text.slice(1);
  const MAX_REWARD = 120;
  // One card per page at a time; its small state outlives the re-renders a save causes.
  let ui = {id: null}, current = null, root = null;
  const fresh = id => ({id, busy: false, error: null, expanded: false, changingType: false, pendingType: null,
    pendingReward: null, rewardChoice: null, rewardText: null});

  function view(detail) {
    const found = detail.survey_type_detection, reward = ui.pendingReward || detail.reward;
    const confirmed = ui.pendingType !== null || found.confirmed;
    const type = ui.pendingType ?? (found.confirmed ? detail.survey_type || found.type : found.type);
    return {found, type, confirmed, reward, rewardAnswered: reward.has_reward !== null};
  }

  async function putReward(detail, body) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(`/api/surveys/${encodeURIComponent(detail.id)}/reward`,
        {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), signal: controller.signal});
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === 'string' ? payload.detail : `Could not save the reward answer (${response.status}).`);
      }
    } catch (error) {
      throw error.name === 'AbortError' ? new Error('The request took too long. Nothing was changed; try again.') : error;
    } finally { clearTimeout(timer); }
    return SC.refreshDetail(detail.version);
  }

  /** Run one save: show the answer at once, refuse a second save, and on failure put the old answer back with a Retry. */
  async function save(kind, optimistic, action, announcement) {
    if (ui.busy) return;
    const focusId = document.activeElement?.id || null;
    Object.assign(ui, optimistic, {busy: true, error: null});
    redraw(focusId);
    try {
      await action();
      Object.assign(ui, {pendingType: null, pendingReward: null, rewardChoice: null, rewardText: null, changingType: false, expanded: false});
      SC.say(announcement);
    } catch (error) {
      Object.assign(ui, {pendingType: null, pendingReward: null, error: {kind, message: error.message, retry: () => save(kind, optimistic, action, announcement)}});
      SC.say(error.message);
    }
    ui.busy = false;
    redraw(focusId);
  }
  const saveType = value => save('type', {pendingType: value}, () => SC.updateSurvey({survey_type: value}), 'Survey type saved');
  const saveReward = body => save('reward', {pendingReward: body}, () => putReward(current, body), 'Reward answer saved');

  function typeOptions(state) {
    return h('fieldset', {id: 'survey-style', disabled: ui.busy}, h('legend', null, 'Survey type'),
      h('p', {class: 'meta'}, 'The time target depends on it.'),
      h('div', {class: 'survey-style-options'}, TYPES.map(([value, label]) => h('label', null,
        h('input', {type: 'radio', name: 'survey-style', value, checked: state.type === value, onchange: () => saveType(value)}), label))));
  }

  function typeRow(state) {
    const {found, type, confirmed} = state, error = ui.error?.kind === 'type' ? ui.error : null;
    return h('div', {class: 'setup-row', 'data-row': 'type'},
      confirmed
        ? h('p', {class: 'setup-question'}, 'Survey type: ', h('strong', null, capital(noun(type))), SC.icon('check', {size: 16}))
        : h('p', {class: 'setup-question'}, 'Looks like a ', h('strong', null, noun(found.type)),
          h('span', {class: 'setup-chip'}, `${capital(found.label)} confidence`)),
      h('div', {class: 'setup-actions'},
        !confirmed && h('button', {type: 'button', id: 'setup-confirm', class: 'btn btn-primary', disabled: ui.busy, onclick: () => saveType(found.type)}, 'Confirm'),
        !ui.changingType && h('button', {type: 'button', id: 'setup-type-change', class: 'btn btn-secondary', disabled: ui.busy,
          onclick: () => { ui.changingType = true; redraw('setup-type-change'); }}, 'Change')),
      ui.changingType && typeOptions(state),
      error && failure(error));
  }

  function rewardRow(state) {
    const {reward} = state, error = ui.error?.kind === 'reward' ? ui.error : null;
    const choice = ui.rewardChoice ?? (reward.has_reward === true ? 'yes' : reward.has_reward === false ? 'no' : null);
    const text = ui.rewardText ?? reward.text ?? '';
    const radio = (value, label) => h('label', null, h('input', {type: 'radio', name: 'reward', id: `reward-${value}`, value, checked: choice === value,
      onchange: () => {
        if (value === 'no') saveReward({has_reward: false, text: ''});
        else { ui.rewardChoice = 'yes'; redraw('reward-text'); }
      }}), label);
    return h('fieldset', {id: 'setup-reward', class: 'setup-row', 'data-row': 'reward', disabled: ui.busy},
      h('legend', {class: 'setup-question'}, 'Does this survey offer a reward?'),
      h('div', {class: 'survey-style-options'}, radio('no', 'No'), radio('yes', 'Yes')),
      choice === 'yes' && h('div', {class: 'setup-reward-text'},
        h('label', {for: 'reward-text'}, 'What is it? (optional, up to 120 characters)'),
        h('input', {type: 'text', id: 'reward-text', maxlength: String(MAX_REWARD), value: text, autocomplete: 'off',
          oninput: event => { ui.rewardText = event.target.value; }}),
        h('button', {type: 'button', id: 'reward-save', class: 'btn btn-primary',
          onclick: () => saveReward({has_reward: true, text: ui.rewardText ?? text})}, 'Save reward')),
      error && failure(error));
  }

  const failure = error => h('p', {class: 'setup-error', role: 'alert'}, error.message,
    h('button', {type: 'button', id: 'setup-retry', class: 'btn btn-secondary', onclick: error.retry}, 'Retry'));

  function summaryText(state) {
    const {reward} = state;
    return [`Survey type: ${capital(noun(state.type))}`, `Reward: ${reward.has_reward ? (reward.text || 'yes') : 'none'}`].join(' · ');
  }

  function draw() {
    if (!root || !current) return;
    const state = view(current), done = state.confirmed && state.rewardAnswered && !ui.error;
    if (done && !ui.expanded) {
      SC.mount(root, h('p', {class: 'setup-line'}, summaryText(state), ' ',
        h('button', {type: 'button', id: 'setup-change', class: 'btn-text', onclick: () => { ui.expanded = true; ui.changingType = true; redraw('setup-type-change'); }}, 'Change')));
      root.classList.add('collapsed');
      return;
    }
    root.classList.remove('collapsed');
    SC.mount(root, h('h3', {id: 'setup-h', tabindex: '-1'}, 'Two quick checks so the verdict is right'),
      h('p', {class: 'meta'}, 'Your answers sharpen the time target and the welcome-text checks. The verdict is shown either way.'),
      typeRow(state), rewardRow(state),
      ui.expanded && h('button', {type: 'button', id: 'setup-done', class: 'btn-text', disabled: ui.busy,
        onclick: () => { ui.expanded = false; ui.changingType = false; redraw('setup-change'); }}, 'Done'));
  }

  /** Redraw the card and put keyboard focus back where it was (or on the nearest sensible control). */
  function redraw(focusId) {
    draw();
    if (!focusId || !root?.isConnected) return;
    (document.getElementById(focusId) || root.querySelector('#setup-change, #setup-h'))?.focus({preventScroll: true});
  }

  /** Null when the page cannot save (the sample) or the server did not send the setup fields. */
  SC.renderSetupCard = detail => {
    if (!detail.survey_type_detection || !detail.reward || !SC.updateSurvey) return null;
    if (ui.id !== detail.id) ui = fresh(detail.id);
    current = detail;
    root = h('section', {id: 'setup-card', class: 'setup-card', 'aria-label': 'Survey setup'});
    draw();
    return root;
  };
})();
