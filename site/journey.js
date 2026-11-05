/* The journey strip (brief 4.4): one segment per screen, width = estimated seconds, section labels above,
   state pins in the four-state language. Numbers, labels, states and tooltip text are all served in
   presentation.journey / journey_sections; this file only draws them. One encoding only: width. */
(() => {
  'use strict';
  const SC = window.SC, {h, plural} = SC;
  let serial = 0;

  SC.journeyOf = detail => detail?.presentation?.journey || [];
  SC.journeySectionsOf = detail => detail?.presentation?.journey_sections || [];

  /** Consecutive segments of one section, labelled from journey_sections (the served label wins over the segment's copy). */
  function sectionsOf(detail, segments) {
    const names = new Map(SC.journeySectionsOf(detail).map(section => [section.id, section.label]));
    const groups = [];
    for (const segment of segments) {
      const last = groups.at(-1);
      if (last && last.id === segment.section) last.segments.push(segment);
      else groups.push({id: segment.section, label: names.get(segment.section) ?? segment.section_label, segments: [segment]});
    }
    return groups;
  }

  const sumSeconds = segments => segments.reduce((sum, segment) => sum + segment.seconds, 0);

  /** What a screen reader hears for one segment: the screen, the served tooltip, the state in words, the section. */
  const segmentName = (segment, label) => [`Screen ${segment.screen}`, segment.tooltip,
    segment.state ? SC.STATES[segment.state]?.label : null, label].filter(Boolean).join(', ');

  const summaryOf = (detail, segments) => {
    const open = segments.filter(segment => segment.state).length;
    return [`Survey journey: ${plural(segments.length, 'screen')}`, detail.overview?.verdict?.time?.label,
      open ? `${plural(open, 'screen')} with something open` : 'nothing open on any screen'].filter(Boolean).join('. ') + '.';
  };

  function segmentButton(segment, label, {selected, stop, onSelect, focusKey}) {
    return h('li', {class: 'journey-seg', style: `--sec:${segment.seconds}`},
      h('button', {type: 'button', 'data-page': segment.page_id, 'data-fk': focusKey ? `journey-${segment.page_id}` : null,
        'data-state': segment.state || 'none', 'aria-current': selected === segment.page_id ? 'step' : null,
        tabindex: stop === segment ? '0' : '-1', onclick: () => onSelect(segment.page_id, segment)},
        h('span', {class: 'journey-num num', 'aria-hidden': 'true'}, String(segment.screen)),
        segment.state ? h('span', {class: 'journey-pin', 'aria-hidden': 'true'}, SC.stateIcon(segment.state)) : null,
        h('span', {class: 'sr-only'}, segmentName(segment, label))));
  }

  /** A text tooltip for hover and keyboard focus. Escape hides it; it never takes focus. */
  function tooltip(root) {
    const tip = h('span', {class: 'journey-tip', 'aria-hidden': 'true', hidden: true});
    const show = button => {
      tip.textContent = button.closest('li').dataset.tip;
      tip.hidden = false;
      const base = root.getBoundingClientRect(), box = button.getBoundingClientRect(), half = tip.offsetWidth / 2;
      tip.style.left = `${Math.min(Math.max(box.left + box.width / 2 - base.left, half), Math.max(half, base.width - half))}px`;
    };
    root.addEventListener('pointerover', event => { const b = event.target.closest('button[data-page]'); if (b && event.pointerType !== 'touch') show(b); });
    root.addEventListener('pointerout', event => { if (event.target.closest('button[data-page]')) tip.hidden = true; });
    root.addEventListener('focusin', event => { const b = event.target.closest('button[data-page]'); if (b?.matches(':focus-visible')) show(b); });
    root.addEventListener('focusout', () => { tip.hidden = true; });
    root.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || tip.hidden) return;
      tip.hidden = true; event.stopPropagation();
    });
    return tip;
  }

  /** Roving tabindex: one tab stop; arrows, Home and End move between segments. Enter and Space click natively. */
  function roving(track) {
    track.addEventListener('keydown', event => {
      const buttons = [...track.querySelectorAll('button')], at = buttons.indexOf(document.activeElement);
      const to = {ArrowRight: at + 1, ArrowDown: at + 1, ArrowLeft: at - 1, ArrowUp: at - 1, Home: 0, End: buttons.length - 1}[event.key];
      if (at < 0 || to === undefined) return;
      event.preventDefault();
      const next = buttons[Math.min(Math.max(to, 0), buttons.length - 1)];
      for (const button of buttons) button.tabIndex = button === next ? 0 : -1;
      next.focus();
    });
  }

  /** `options`: onSelect(pageId, segment), selected (page id), compact (no section labels, shorter). Returns null with no journey. */
  SC.renderJourney = (detail, {onSelect, selected = null, compact = false} = {}) => {
    const segments = SC.journeyOf(detail);
    if (!segments.length) return null;
    const groups = sectionsOf(detail, segments), stop = segments.find(segment => segment.page_id === selected) || segments[0];
    const id = `journey-${++serial}`;
    const track = h('ol', {class: 'journey-track', 'aria-label': 'Screens in order'}, groups.map(group => h('li', {class: 'journey-section',
      style: `--sec:${sumSeconds(group.segments)};--label:${compact ? 0 : group.label.length};--count:${group.segments.length}`},
      compact ? null : h('span', {class: 'journey-label', 'aria-hidden': 'true'}, group.label),
      h('ol', {class: 'journey-segs'}, group.segments.map(segment => {
        const item = segmentButton(segment, group.label, {selected, stop, onSelect, focusKey: compact});
        item.dataset.tip = segment.tooltip;
        return item;
      })))));
    roving(track);
    const scroller = h('div', {class: 'journey-scroll'}, track);
    const more = h('p', {class: 'journey-more meta', hidden: true}, 'Scroll sideways to see every screen →');
    const root = h('div', {id, class: `journey${compact ? ' compact' : ''}`, role: 'group', 'aria-label': summaryOf(detail, segments)});
    root.append(scroller, more, tooltip(root));
    if (!compact) root.append(listAlternative(groups));
    // Show the sideways hint only when the strip really overflows, and bring the current screen into view.
    new ResizeObserver(() => {
      more.hidden = scroller.scrollWidth <= scroller.clientWidth + 1;
      const now = track.querySelector('[aria-current=step]');
      if (now && !scroller.dataset.centred) {
        scroller.dataset.centred = 'yes';
        scroller.scrollLeft = now.offsetLeft - (scroller.clientWidth - now.offsetWidth) / 2;
      }
    }).observe(scroller);
    return root;
  };

  /** The same journey as plain text, for anyone who cannot use the strip. */
  function listAlternative(groups) {
    return h('details', {class: 'journey-list'}, h('summary', null, 'Show the journey as a list'),
      h('ol', null, groups.flatMap(group => group.segments.map(segment => h('li', null,
        segment.state ? SC.stateIcon(segment.state) : null,
        h('span', null, `Screen ${segment.screen} · ${segment.tooltip} · ${group.label}`))))));
  }
})();
