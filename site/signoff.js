/* Sign off (brief 4.7): one named record per version, stored by the server (detail.signoff).
   The name is remembered in this browser only. Open items stay on screen before, during and after signing. */
(() => {
  'use strict';
  const SC = window.SC, {h, mount, plural} = SC;
  const NAME_KEY = 'surveycoach-signoff-name', MAX_NAME = 80, READY = 'ready_for_signoff';
  const draft = {name: '', ack: false, error: null, failed: false};
  let busy = false;

  const storedName = () => { try { return localStorage.getItem(NAME_KEY) || ''; } catch (_) { return ''; } };
  const remember = name => { try { localStorage.setItem(NAME_KEY, name); } catch (_) { /* private mode: the name just is not kept */ } };
  /** The server folds whitespace too; do the same here so the length we check is the length it checks. */
  const cleanName = value => value.replace(/\s+/g, ' ').trim();
  SC.signoffNameError = value => {
    const name = cleanName(value);
    if (!name) return 'Enter your name.';
    return name.length > MAX_NAME ? `Use ${MAX_NAME} characters or fewer.` : null;
  };

  const openCount = detail => SC.openCount(detail.overview?.verdict?.tiles);
  const ready = detail => detail.overview?.verdict?.kind === READY;
  const itemsOpen = n => `${plural(n, 'item')} ${n === 1 ? 'is' : 'are'} still open`;

  const openList = record => (record?.open_items?.length ? h('ul', {class: 'open-at-signing', 'aria-label': 'Items that were open when signed'},
    record.open_items.map(item => h('li', null, SC.stateIcon(item.state), h('span', null, item.headline, h('span', {class: 'where'}, ` · ${item.location}`))))) : null);

  function signedState(detail, state) {
    const record = state.record;
    const note = record.acknowledged_open ? `Signed off with ${plural(record.open_items.length, 'open item')}.` : null;
    return [
      h('p', {class: 'signed-line'}, SC.icon('check-circle', {size: 20}), h('strong', null, `Signed off by ${state.signed_off_by} · ${SC.dateLabel(state.signed_off_at)}`)),
      note ? h('p', null, note) : null, openList(record),
      state.changed_since ? h('p', {class: 'quiet'}, 'Items changed since this was signed. The record above is what was true then.') : null,
      h('button', {type: 'button', class: 'btn btn-text', id: 'copy-slack-again', disabled: !detail.share?.slack_post,
        onclick: () => SC.copyWithToast(detail.share.slack_post)}, 'Copy Slack post again')];
  }

  function form(detail) {
    const open = openCount(detail), needsAck = !ready(detail), version = detail.version;
    const name = h('input', {id: 'signoff-name', type: 'text', autocomplete: 'name', value: draft.name, 'aria-describedby': 'signoff-error',
      'aria-invalid': draft.error ? 'true' : false, oninput: event => { draft.name = event.target.value; }});
    const ack = needsAck ? h('label', {class: 'ack', for: 'signoff-ack'},
      h('input', {id: 'signoff-ack', type: 'checkbox', checked: draft.ack, onchange: event => { draft.ack = event.target.checked; }}),
      `I know ${itemsOpen(open)}`) : null;
    const error = h('p', {id: 'signoff-error', class: 'field-error', role: 'alert'}, draft.error || '');
    const button = h('button', {id: 'signoff-submit', type: 'submit', class: 'btn btn-secondary signoff-button', 'aria-busy': busy ? 'true' : false, disabled: busy || Boolean(SC.readOnly)},
      busy ? 'Signing off…' : needsAck ? `Sign off with ${plural(open, 'open item')}` : "I've reviewed this survey");
    const retry = draft.failed && !busy ? h('button', {id: 'signoff-retry', type: 'button', class: 'btn btn-text', onclick: () => submit(detail)}, 'Retry') : null;
    return h('form', {id: 'signoff-form', class: 'signoff-form', novalidate: true, onsubmit: event => { event.preventDefault(); submit(detail); }},
      h('label', {for: 'signoff-name'}, 'Your name'), name, ack, error, h('div', {class: 'signoff-row'}, button, retry),
      SC.readOnly ? h('p', {class: 'quiet'}, SC.readOnly.reason) : null,
      h('p', {class: 'quiet'}, `This records your name and the time for version ${version}. It does not check anything for you.`));
  }

  async function submit(detail) {
    if (busy) return;                                   // a double click must not send twice
    const needsAck = !ready(detail), name = cleanName(draft.name);
    draft.error = SC.signoffNameError(draft.name) || (needsAck && !draft.ack ? `Tick the box to confirm ${itemsOpen(openCount(detail))}.` : null);
    draft.failed = false;
    if (draft.error) { render(detail); document.getElementById(draft.error.startsWith('Tick') ? 'signoff-ack' : 'signoff-name')?.focus(); return; }
    busy = true; render(detail);
    document.getElementById('signoff-submit')?.focus({preventScroll: true});
    try {
      const state = await SC.api(`/api/surveys/${encodeURIComponent(detail.id)}/versions/${detail.version}/signoff`, 'POST', {name, acknowledge_open: needsAck && draft.ack});
      remember(name); Object.assign(draft, {ack: false, error: null, failed: false}); detail.signoff = state; busy = false;
      render(detail);
      SC.say(`Signed off by ${state.signed_off_by}.`);
      document.getElementById('signoff-h')?.focus({preventScroll: true});
      SC.refreshDetail?.(detail.version).catch(() => { /* the record is saved; the next load shows the same state */ });
    } catch (error) {
      busy = false; draft.failed = true; draft.error = `Sign-off was not saved. ${error.message}`;
      render(detail);
      document.getElementById('signoff-retry')?.focus({preventScroll: true});
    }
  }

  function history(detail, state) {
    const shown = state.signed ? state.record : null;
    const rows = (state.history || []).filter(row => !(shown && row.version === shown.version && row.signed_at === shown.signed_at));
    if (!rows.length) return null;
    return h('section', {class: 'signoff-history', 'aria-labelledby': 'signoff-history-h'}, h('h4', {id: 'signoff-history-h'}, 'Earlier sign-offs'),
      h('ol', {class: 'signoff-timeline'}, rows.map(row => h('li', null, h('strong', null, `v${row.version}`),
        ` signed off by ${row.name} · ${SC.dateLabel(row.signed_at)}`, row.acknowledged_open ? ' · with items open' : ''))));
  }

  function render(detail) {
    const host = document.getElementById('signoff');
    const state = detail.signoff;
    if (!host || !state) { host?.replaceChildren(); return; }
    const open = openCount(detail), focusedId = host.contains(document.activeElement) ? document.activeElement.id : '';
    mount(host, h('section', {class: 'signoff-card', 'data-signed': String(state.signed), 'aria-labelledby': 'signoff-h'},
      h('h3', {id: 'signoff-h', tabindex: '-1'}, 'Sign off'),
      h('p', {id: 'signoff-open', class: 'signoff-open'}, open ? `Open now: ${SC.openSummary(detail.overview.verdict.tiles)}` : 'Nothing is open.'),
      state.signed ? signedState(detail, state)
        : [h('p', {class: 'quiet'}, state.history?.length ? `Version ${detail.version} has not been signed off yet.` : 'Not signed off yet.'), form(detail)],
      history(detail, state)));
    if (focusedId) document.getElementById(focusedId)?.focus({preventScroll: true});   // a re-render never drops the user's place
  }

  SC.renderSignoff = detail => {
    if (!draft.name) draft.name = storedName();         // the last name used, from this browser only
    render(detail);
  };
})();
