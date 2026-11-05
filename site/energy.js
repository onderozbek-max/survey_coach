/* Supplied energy evidence and one playback clock shared by both previews. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.uncertainWalkthrough = 'Captured-screen walkthrough; route uncertain.';
  const zones = {fresh:'Low', fatigue_builds:'Building', high:'High'};
  SC.renderEnergy = (detail, navigate, {compact = false, selected = null} = {}) => {
    const energy = detail.overview.energy, screens = energy.screens;
    const max = Math.max(1, ...screens.map(screen => screen.seconds));
    const heaviest = screens.find(screen => screen.page_id === energy.heaviest[0]);
    return h('div', {class:`energy-map${compact ? ' compact' : ''}`},
      h('nav', {class:'energy-bars', 'aria-label':compact ? 'Preview screen scrubber' : 'Member effort by screen'},
        screens.map((screen, i) => {
          const count = detail.plan.must_fix.filter(item => item.screen === screen.screen).length;
          return h('button', {type:'button', class:`energy-bar ${screen.zone}`, 'data-page':screen.page_id,
            'aria-current':selected === screen.page_id ? 'step' : null,
            'aria-label':`${screen.name}, about ${Math.round(screen.seconds)} seconds, estimate, ${(zones[screen.zone] || 'Unknown').toLowerCase()} estimated load, ${count} must-fix${count === 1 ? '' : 'es'}`,
            onclick:() => navigate(screen.page_id)},
            h('span', {class:'energy-column'}, count > 0 && h('span', {class:'energy-must', 'aria-hidden':'true'}, SC.icon('dot')),
              h('span', {class:'energy-fill', style:`height:${screen.seconds / max * (compact ? 42 : 96)}px`})),
            h('span', {class:`energy-label${screens.length > 14 && i % 2 ? ' sparse' : ''}`, title:screen.name}, screen.name));
        })),
      compact && h('p', {class:'energy-quick-guide'}, 'Height = screen effort · Color = accumulated effort'),
      h(compact ? 'details' : 'div', {class:'energy-guide'},
        compact && h('summary', null, 'Effort guide'),
        h('div', {class:'energy-legend'}, h('strong', null, 'Estimated load:'),
          Object.entries(zones).map(([zone, label]) =>
            h('span', null, h('i', {class:zone, 'aria-hidden':'true'}), label))),
        h('p', {class:'energy-explanation'},
          'Height: estimated effort per screen. Color: accumulated effort (heuristic), not severity or measured time or fatigue. Blue outline: selected screen. Tap a bar to navigate.')),
      h('p', {class:'energy-swipe'}, 'Swipe for more'),
      h('p', {class:'energy-caption'}, heaviest && `Heaviest: ${heaviest.name} (about ${Math.round(heaviest.seconds)}s). `,
        energy.path_uncertain && `${SC.uncertainWalkthrough} `,
        'Reading and tapping estimate; real completion is not measured.'));
  };

  // A single pending timeout. Pausing preserves remaining reading time; hidden tabs never advance.
  SC.createPlayback = ({seconds, advance, changed = () => {}}) => {
    let timer = null, playing = false, remaining = null, started = 0, disposed = false;
    const clear = () => { clearTimeout(timer); timer = null; };
    const pause = () => {
      if (playing) remaining = Math.max(0, remaining - (Date.now() - started));
      clear(); playing = false; changed(false);
    };
    const schedule = () => {
      clear();
      if (!playing || document.hidden || disposed) { pause(); return; }
      remaining ??= Math.max(1, seconds()) * 1000;
      started = Date.now();
      timer = setTimeout(() => {
        timer = null; remaining = null;
        if (!advance()) { playing = false; changed(false); return; }
        schedule();
      }, remaining);
    };
    const hidden = () => { if (document.hidden) pause(); };
    document.addEventListener('visibilitychange', hidden);
    return {
      play() { if (disposed || playing || document.hidden) return; playing = true; changed(true); schedule(); },
      pause,
      reset() { clear(); remaining = null; if (playing) schedule(); },
      get playing() { return playing; },
      dispose() { pause(); disposed = true; document.removeEventListener('visibilitychange', hidden); },
    };
  };

  SC.previewReadingDelta = (page, plan) => {
    const count = text => (text || '').trim().split(/\s+/).filter(Boolean).length * .3;
    let delta = 0;
    const compare = (text, question_id) => {
      const original = text || '';
      delta += count(original) - count(SC.applyFixes(original, plan, null, {page_id:page.id, question_id}));
    };
    compare(page.intro_text); compare(page.text);
    for (const q of page.questions || []) {
      compare(q.text, q.id); compare(q.help_text, q.id);
      if (!['dropdown','grid_single','grid_multi'].includes(q.kind)) for (const option of q.options || []) compare(option.label, q.id);
    }
    return Math.round(delta);
  };

  SC.openMemberPreview = detail => {
    if (document.querySelector('#member-preview')) return;
    const opener = document.activeElement, model = SC.buildModel(detail);
    const {screens, path_uncertain:uncertain} = detail.overview.energy;
    if (!screens.length) return;
    let index = 0;
    const phone = h('div', {class:'member-phone'}), scrubber = h('div'), elapsed = h('p', {class:'meta'});
    const toggle = h('button', {type:'button', class:'btn', onclick:() => playback.playing ? playback.pause() : playback.play()}, 'Pause');
    const dialog = h('dialog', {id:'member-preview', 'aria-labelledby':'member-preview-h'},
      h('header', null, h('h2', {id:'member-preview-h'}, 'Preview as a member'),
        h('button', {type:'button', class:'btn', autofocus:true, onclick:() => close()}, 'Close preview')),
      phone, h('div', {class:'member-playback'}, toggle, elapsed), scrubber);
    const render = () => {
      const focusedPage = scrubber.contains(document.activeElement) ? document.activeElement.dataset.page : null;
      const screen = screens[index], item = model.items.find(item => item.page.id === screen.page_id);
      SC.mount(phone, SC.renderPhone(item, SC.overviewPhoneContext(detail, item)));
      // This is a reconstruction, not an answer-entry or submission surface.
      phone.inert = true;
      elapsed.textContent = uncertain
        ? `${SC.uncertainWalkthrough} Screen estimate: ${Math.round(screen.seconds)} seconds`
        : `Elapsed estimate: ${Math.round(screens.slice(0, index).reduce((sum, s) => sum + s.seconds, 0))} seconds`;
      SC.mount(scrubber, SC.renderEnergy(detail, pageId => {
        index = screens.findIndex(screen => screen.page_id === pageId); render(); playback.reset();
      }, {compact:true, selected:screen.page_id}));
      if (focusedPage) [...scrubber.querySelectorAll('button')].find(button => button.dataset.page === focusedPage)?.focus({preventScroll:true});
    };
    const playback = SC.createPlayback({seconds:() => screens[index].seconds,
      advance:() => { if (index === screens.length - 1) return false; index++; render(); return true; },
      changed:playing => { toggle.textContent = playing ? 'Pause' : 'Play'; }});
    dialog.addEventListener('keydown', event => {
      if (event.key !== 'Tab') return;
      const buttons = [...dialog.querySelectorAll('button:not(:disabled)')].filter(button => !button.closest('[inert]'));
      const first = buttons[0], last = buttons.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    const close = () => {
      playback.dispose(); window.removeEventListener('surveycoach-chapter', close);
      dialog.close(); dialog.remove(); opener?.focus({preventScroll:true});
    };
    window.addEventListener('surveycoach-chapter', close);
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    dialog.addEventListener('close', () => { if (dialog.isConnected) close(); }, {once:true});
    document.body.append(dialog); render(); dialog.showModal(); playback.play();
  };
})();
