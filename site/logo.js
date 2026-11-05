/* The SurveyCoach mark: a phone (the member's view) with a chat bubble and a check on its screen
   (the coach's verdict). Shapes only; colours come from logo.css tokens. One builder for every page. */
(() => {
  'use strict';
  const SC = window.SC;
  const NS = 'http://www.w3.org/2000/svg';
  const SHAPES = [
    ['rect', 'lm-phone', {x: 5, y: 1.5, width: 22, height: 29, rx: 6}],
    ['rect', 'lm-screen', {x: 8.5, y: 5, width: 15, height: 20, rx: 3}],
    ['path', 'lm-bubble', {d: 'M11.5 9h9a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5H17l-3 2.6V18h-2.5A1.5 1.5 0 0 1 10 16.5v-6A1.5 1.5 0 0 1 11.5 9z'}],
    ['path', 'lm-check', {d: 'M12.8 13.6l2.2 2.2 4-4.4'}],
    ['rect', 'lm-home', {x: 13, y: 27, width: 6, height: 1.6, rx: .8}],
  ];

  /** Accessible name SurveyCoach. Pass {decorative: true} where the wordmark sits next to it. */
  SC.logoMark = ({size = 32, decorative = false} = {}) => {
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 32 32');
    svg.setAttribute('width', size);
    svg.setAttribute('height', size);
    svg.setAttribute('class', 'logo-mark');
    svg.setAttribute('focusable', 'false');
    if (decorative) svg.setAttribute('aria-hidden', 'true');
    else { svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'SurveyCoach'); }
    for (const [tag, name, attrs] of SHAPES) {
      const node = document.createElementNS(NS, tag);
      node.setAttribute('class', name);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      svg.append(node);
    }
    return svg;
  };
})();
