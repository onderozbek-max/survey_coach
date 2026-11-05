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
    // Done, related findings and page membership are shared with the tabs, toolbar and drawer (progress.js).
    const decided = item => SC.itemDecided(detail, item);
    const related = item => SC.itemRelated(detail, item);
    const onPage = (f, pageId) => SC.findingOnPage(detail, f, pageId);
    const allowed = item => related(item).some(f =>
      (!Object.hasOwn(filter, 'fingerprints') || filter.fingerprints.includes(f.fingerprint)) &&
      (!filter.page_id || onPage(f, filter.page_id)));
    const allItems = () => tabs.flatMap(([name]) => detail.plan[name]);
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
        const inspection = options.page_id || Object.hasOwn(options, 'fingerprints');
        const hit = all.find(({item}) => !decided(item)) || (inspection ? all[0] : null);
        if (hit) { tab = hit.name; show(hit.item); }
        else show(items().find(item => !decided(item)));
      },
      screen(pageId) {
        filter = {page_id:pageId};
        const matches = tabs.flatMap(([name]) => detail.plan[name].filter(allowed).map(item => ({name,item})));
        const hit = matches.find(({item}) => !decided(item)) || matches[0];
        if (hit) { tab = hit.name; active = hit.item.id; } else active = null;
        redraw();
      },
      advance(origin) {
        // A late save/copy passes the item that started it; anything else may have moved on since.
        if (origin !== undefined && !api.isActive(origin)) return false;
        const list = items(), index = list.findIndex(item => item.id === active);
        const rest = [...list.slice(index + 1), ...list.slice(0,index)];
        show(rest.find(item => !decided(item)), true);
        return true;
      },
      isActive: origin => origin === active && SC.currentChapter() === 'improve',
      renderBar(mode, changeMode, screenId) {
        const nav = h('div', {id:'queue-tabs',role:'tablist','aria-label':'Improvement queue'}, tabs.map(([name,label], i) => {
          const progress = SC.progressOf(detail, name);
          return h('button', {type:'button', role:'tab', tabindex:name === tab ? '0' : '-1',
            'aria-selected':String(name === tab), 'aria-controls':'coach', 'data-fk':`queue-${name}`, onclick:() => chooseTab(name),
            onkeydown:event => {
              const offset = {ArrowRight:1, ArrowLeft:-1, Home:-i, End:2-i}[event.key];
              if (offset == null) return;
              event.preventDefault(); const next = tabs[(i + offset + 3) % 3][0]; chooseTab(next);
              document.querySelectorAll('#queue-tabs [role=tab]')[(i + offset + 3) % 3]?.focus();
            }}, label, ' ', h('span', {class:'tab-progress'}, progress.total ? SC.progressText(progress) : 'none'));
        }));
        const progress = h('p', {id:'queue-progress', class:'meta', 'aria-live':'polite'}, SC.progressText(SC.progressAll(detail)));
        return [h('div', {class:'queue-navigation'}, nav, progress), SC.renderEnergy(detail, pageId => window.dispatchEvent(new CustomEvent('surveycoach-screen',{detail:pageId})), {compact:true,selected:screenId}),
          h('div', {class:'queue-tools'}, h('button', {type:'button',id:'all-screens',onclick:() => SC.openScreens(detail)}, 'All screens'),
            h('div', {class:'seg',role:'group','aria-label':'Preview wording'}, [['current','Original'],['fixes','With changes']].map(([value,label]) =>
              h('button', {type:'button','aria-pressed':String(mode === value),'data-fk':`queue-mode-${value}`,onclick:() => changeMode(value)},label))))];
      },
      render(ctx) {
        if (api.item) return SC.renderImproveItem(api.item, {...ctx, detail, entries:entries(api.item), onAdvance:api.advance, isActive:api.isActive});
        const scoped = filter.page_id || Object.hasOwn(filter, 'fingerprints');
        const pageId = filter.page_id || ctx.pageId;
        const pageFindings = detail.review.findings.filter(f => onPage(f, pageId));
        const pageItems = allItems().filter(item => related(item).some(f => onPage(f, pageId)));
        const filteredItems = allItems().filter(allowed);
        let heading = 'Nothing more in this view';
        let explanation = 'Other recommendations may be outside this category or already handled.';
        if (scoped && pageFindings.length === 0) {
          heading = 'No issues found for this screen in the checks run';
          explanation = 'This is not a guarantee that the screen is issue-free; only the checks run are covered.';
        } else if (scoped && pageItems.length && pageItems.every(decided) &&
            pageFindings.every(f => pageItems.some(item => related(item).includes(f)))) {
          heading = 'All recommendations for this screen handled';
          explanation = 'These are saved decisions, not verified fixes. Recheck after making changes in RedJade.';
        } else if (scoped) {
          explanation = filteredItems.length
            ? 'Recommendations remain outside this category or have been skipped in this view.'
            : 'Recommendations may remain outside this filter. Show all recommendations to review them.';
        } else if (detail.plan[tab].length && detail.plan[tab].every(decided)) {
          heading = tab === 'must_fix' ? `All ${detail.plan.must_fix.length} must-fixes handled`
            : 'All recommendations in this category handled';
          explanation = 'These are saved decisions, not verified fixes. Recheck after making changes in RedJade.';
        } else if (!detail.plan[tab].length) {
          heading = tab === 'must_fix' ? 'No must-fixes in this review' : 'No recommendations in this category';
          explanation = 'Other categories may still contain recommendations.';
        }
        return h('section', {class:'screen-clear'}, h('h3', {id:'coach-h',tabindex:'-1'}, heading),
          h('p', null, explanation),
          scoped && h('button', {type:'button',class:'btn',onclick:() => {
            filter = {};
            const hit = tabs.flatMap(([name]) => detail.plan[name].map(item => ({name,item})))
              .find(({item}) => !decided(item));
            if (hit) tab = hit.name;
            show(hit?.item, true);
          }}, 'Show all recommendations'),
          h('button', {type:'button',class:'btn btn-primary',onclick:() => chooseTab('quick_wins')}, 'Continue to quick wins'),
          h('button', {type:'button',class:'btn-text',onclick:() => SC.goChapter('share')}, 'Go to Share'));
      },
    };
    return api;
  };
})();
