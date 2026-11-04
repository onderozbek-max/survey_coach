/* Server-curated membership and order. Decisions update progress, never regroup findings. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const tabs = [['must_fix','Must-fix'], ['quick_wins','Quick wins'], ['more','More ideas']];
  SC.createQueue = (detail, navigate, redraw) => {
    let tab = 'must_fix', active = null, filter = {};
    const entries = item => item.fingerprints.map(fp => {
      const key = detail.review.findings.findIndex(f => f.fingerprint === fp);
      return key < 0 ? null : {f:detail.review.findings[key], key};
    }).filter(Boolean);
    const decided = item => entries(item).every(({f}) => {
      const d = detail.decisions[f.fingerprint];
      return d?.action === 'pick' && !d.stale_pick || d?.action === 'original'
        || d?.action === 'keep' && Boolean(d.reason?.trim());
    });
    const allowed = item => {
      const screen = detail.screens.find(s => s.page_id === filter.page_id);
      return entries(item).some(({f}) =>
        (!Object.hasOwn(filter, 'fingerprints') || filter.fingerprints.includes(f.fingerprint)) &&
        (!filter.page_id || f.page_id === filter.page_id || screen?.questions?.some(q => q.id === f.question_id)));
    };
    const items = () => detail.plan[tab].filter(allowed);
    function show(item, focus = false) {
      active = item?.id || null;
      if (item) navigate(entries(item).find(e => !SC.issueDecision(e.f)?.action || SC.issueDecision(e.f)?.action === 'open') || entries(item)[0]);
      redraw();
      if (focus) {
        const heading = document.querySelector('#coach h3'); heading?.focus({preventScroll:true});
        SC.say(item ? `Next: ${item.headline}` : document.querySelector('#coach h3')?.textContent || 'Section complete');
      }
    }
    function chooseTab(value) {
      tab = value; filter = {};
      show(items().find(item => !decided(item)));
    }
    const api = {
      update(updated) {
        detail = updated;
        if (!items().some(item => item.id === active)) active = items().find(item => !decided(item))?.id || null;
      },
      entries, decided,
      get item() { return items().find(item => item.id === active) || null; },
      start() { show(items().find(item => !decided(item))); },
      focus(fp) {
        for (const [name] of tabs) {
          const item = detail.plan[name].find(item => item.fingerprints.includes(fp));
          if (item) { tab = name; filter = {}; show(item); return true; }
        }
        return false;
      },
      options(options) {
        filter = options;
        if (tabs.some(([name]) => name === options.tab)) tab = options.tab;
        const constrainedTabs = options.tab ? tabs.filter(([name]) => name === tab) : tabs;
        const all = constrainedTabs.flatMap(([name]) => detail.plan[name].filter(allowed).map(item => ({name,item})));
        const hit = all.find(({item}) => !decided(item)) || all[0];
        if (hit) { tab = hit.name; show(hit.item); }
        else show(items().find(item => !decided(item)));
      },
      screen(pageId) {
        filter = {};
        const screen = detail.screens.find(s => s.page_id === pageId);
        const matches = tabs.flatMap(([name]) => detail.plan[name].filter(item => entries(item).some(({f}) =>
          f.page_id === pageId || screen?.questions?.some(q => q.id === f.question_id))).map(item => ({name,item})));
        const hit = matches.find(({item}) => !decided(item)) || matches[0];
        if (hit) { tab = hit.name; active = hit.item.id; } else active = null;
        redraw();
      },
      advance() {
        const list = items(), index = list.findIndex(item => item.id === active);
        const rest = [...list.slice(index + 1), ...list.slice(0,index)];
        show(rest.find(item => !decided(item)), true);
      },
      renderBar(mode, changeMode, screenId) {
        const nav = h('div', {id:'queue-tabs',role:'tablist','aria-label':'Improvement queue'}, tabs.map(([name,label], i) => {
          const count = detail.plan[name].filter(decided).length;
          return h('button', {type:'button', role:'tab', tabindex:name === tab ? '0' : '-1',
            'aria-selected':String(name === tab), 'aria-controls':'coach', 'data-fk':`queue-${name}`, onclick:() => chooseTab(name),
            onkeydown:event => {
              const offset = {ArrowRight:1, ArrowLeft:-1, Home:-i, End:2-i}[event.key];
              if (offset == null) return;
              event.preventDefault(); const next = tabs[(i + offset + 3) % 3][0]; chooseTab(next);
              document.querySelectorAll('#queue-tabs [role=tab]')[(i + offset + 3) % 3]?.focus();
            }}, name === 'more' ? label : `${label} ${count}/${detail.plan.counts[name]}`);
        }));
        return [nav, SC.renderEnergy(detail, pageId => window.dispatchEvent(new CustomEvent('surveycoach-screen',{detail:pageId})), {compact:true,selected:screenId}),
          h('div', {class:'queue-tools'}, h('button', {type:'button',id:'all-screens',onclick:() => SC.openScreens(detail)}, 'All screens'),
            h('div', {class:'seg',role:'group','aria-label':'Preview wording'}, [['current','Original'],['fixes','With changes']].map(([value,label]) =>
              h('button', {type:'button','aria-pressed':String(mode === value),'data-fk':`queue-mode-${value}`,onclick:() => changeMode(value)},label))))];
      },
      render(ctx) {
        if (api.item) return SC.renderImproveItem(api.item, {...ctx, detail, entries:entries(api.item), onAdvance:api.advance});
        return h('section', {class:'screen-clear'}, h('h3', {id:'coach-h',tabindex:'-1'}, tab === 'must_fix' && detail.plan.must_fix.every(decided)
          ? `All ${detail.plan.counts.must_fix} must-fixes handled` : 'Nothing more in this view'),
          h('button', {type:'button',class:'btn btn-primary',onclick:() => chooseTab('quick_wins')}, 'Continue to quick wins'),
          h('button', {type:'button',class:'btn-text',onclick:() => SC.goChapter('share')}, 'Go to Share'));
      },
    };
    return api;
  };
})();
