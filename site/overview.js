/* Chapter one presents Part A evidence verbatim; absence is never a pass. */
(() => {
  'use strict';
  const SC = window.SC, {h, mount, $, icon} = SC;
  const types = [['community_pulse','Community & fun'], ['non_ihut_product','Product test'],
    ['ihut','Home-use test'], ['services_concept','Concept or services'], ['market_research','Market research']];
  const tones = {strong:'positive', mixed:'attention', needs_work:'critical', unknown:'neutral'};
  const symbols = {strong:'check', mixed:'alert', needs_work:'alert', unknown:'minus'};
  let detail;
  SC.overviewPhoneContext = (survey, item) => ({data:window.SURVEYCOACH_DEMO, review:survey.review,
    selected:item.entries.find(entry => entry.f.severity === 'must_fix')?.key, device:390, large:false,
    total:survey.screens.length, pageId:item.page.id, plan:null, applied:() => false,
    blocked:() => false, offscreen:() => false, onPin:() => {}});
  const route = options => SC.goChapter('improve', options);
  const relative = stamp => {
    if (!stamp) return 'time unavailable';
    const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(stamp) ? stamp : stamp.replace(' ', 'T') + 'Z');
    if (!Number.isFinite(date.getTime())) return 'time unavailable';
    const minutes = Math.round((date.getTime() - Date.now()) / 60000);
    return new Intl.RelativeTimeFormat(undefined, {numeric:'auto'}).format(
      Math.abs(minutes) < 60 ? minutes : Math.round(minutes / 60), Math.abs(minutes) < 60 ? 'minute' : 'hour');
  };
  async function update(payload, announcement) {
    if (!SC.updateSurvey) return;
    try { await SC.updateSurvey(payload); SC.say(announcement); }
    catch (error) { SC.say(error.message); }
  }
  function nameEditor() {
    if (!/^(surveys?|untitled)$/i.test(detail.title.trim()) || !SC.updateSurvey) return null;
    const button = h('button', {type:'button', id:'name-survey', class:'btn-text', onclick:() => {
      form.hidden = false; button.hidden = true; input.focus();
    }}, 'Name this survey');
    const input = h('input', {type:'text', maxlength:200, value:detail.title, 'aria-label':'Survey title'});
    const form = h('form', {class:'overview-title-form', hidden:true, onsubmit:async event => {
      event.preventDefault();
      if (!input.value.trim()) { SC.say('Enter a title.'); return; }
      const save = form.querySelector('[type=submit]'); save.disabled = true;
      await update({title:input.value.trim()}, 'Title saved'); save.disabled = false;
    }}, input, h('button', {type:'submit', class:'btn'}, 'Save title'),
      h('button', {type:'button', class:'btn-text', onclick:() => { form.hidden = true; button.hidden = false; }}, 'Cancel'));
    return h('div', null, button, form);
  }
  SC.renderOverview = survey => {
    detail = survey;
    const overview = detail.overview;
    if (!overview) return;
    const active = document.activeElement;
    const restoreHeading = SC.currentChapter() === 'overview' && (active === document.body || active?.id === 'overview-h');
    const model = SC.buildModel(detail);
    const first = model.items.find(item => item.worst === 'must_fix') || model.items[0];
    const mini = first && h('div', {class:'overview-mini', inert:true, 'aria-hidden':'true'},
      SC.renderPhone(first, SC.overviewPhoneContext(detail, first)));
    const styleStatus = h('p', {class:'meta'}, 'Sets length targets and how we treat playful voice.');
    mount($('chapter-overview'),
      h('div', {class:'overview-hero'}, h('div', {class:'overview-intro'},
        h('p', {class:'meta'}, `Version ${detail.version || 1} · checked ${relative(detail.created_at || detail.versions?.find(version => version.version === detail.version)?.created_at)}`),
        h('h2', {id:'overview-h', tabindex:'-1'}, detail.title), nameEditor(),
        h('p', {id:'overview-headline'}, overview.headline), h('p', {id:'overview-subline'}, overview.subline),
        h('div', {class:'overview-actions'},
          h('button', {id:'start-improving', type:'button', class:'btn btn-primary', onclick:() => route({tab:'must_fix'})}, 'Start improving', icon('arrow-right')),
          h('button', {id:'preview-member', type:'button', class:'btn btn-secondary', disabled:!first,
            onclick:() => SC.openMemberPreview(detail)}, icon('play'), 'Preview as a member'))),
        h('div', {'aria-describedby':'overview-headline'}, mini)),
      h('h3', null, 'Member experience'),
      h('ul', {id:'signals'}, overview.signals.map(signal => h('li', {'data-signal':signal.id},
        h('div', {class:'signal-name'}, icon(signal.id === 'time' ? 'clock' : 'sparkle'), h('strong', null, signal.name)),
        h('span', {class:'signal-state', 'data-tone':tones[signal.state]}, icon(symbols[signal.state]), signal.label),
        h('p', {class:'signal-summary'}, signal.summary),
        h('details', {class:'signal-details'}, h('summary', null, 'Details'),
          h('p', null, signal.summary)),
        h('button', {type:'button', class:'signal-link btn-text', onclick:() => route({signal:signal.id,
          page_id:signal.pages[0], fingerprints:signal.findings})}, `See ${SC.plural(signal.pages.length, 'screen')}`)))),
      h('h3', null, 'Energy map'), h('div', {id:'energy-map'}, SC.renderEnergy(detail, page_id => route({page_id}))),
      h('div', {class:'overview-bottom'}, overview.strengths.length > 0 && h('section', null,
        h('h3', null, 'What members will like'), h('ul', {id:'strengths'}, overview.strengths.slice(0,3).map(text => h('li', null, icon('check'), text)))),
        h('section', {id:'plan-summary'}, h('h3', null, 'Your plan'),
          [['must_fix','Must-fix'], ['quick_wins','Quick wins'], ['more','More ideas']].map(([tab, label]) =>
            h('button', {type:'button', class:'btn-text', onclick:() => route({tab})}, `${label} ${detail.plan.counts[tab]}`)))),
      h('fieldset', {id:'survey-style', disabled:!SC.updateSurvey}, h('legend', null, 'What kind of survey is this?'),
        h('div', {class:'survey-style-options'}, types.map(([value, label]) => h('label', null,
          h('input', {type:'radio', name:'survey-style', value, checked:(detail.survey_type || detail.snapshot.survey_type) === value,
            onchange:async event => {
              const fieldset = event.target.closest('fieldset'); fieldset.disabled = true;
              await update({survey_type:value}, 'Survey style saved');
              fieldset.disabled = false;
              if (fieldset.isConnected) SC.renderOverview(detail);
              document.querySelector(`#survey-style input[value="${value}"]`)?.focus({preventScroll:true});
            }}), label))), styleStatus));
    if (restoreHeading) $('overview-h').focus({preventScroll:true});
  };
})();
