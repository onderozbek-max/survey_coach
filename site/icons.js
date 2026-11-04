/* Decorative, stroke-only icons. All SVG nodes use the SVG namespace. */
(() => {
  'use strict';
  const SC = window.SC;
  const shapes = {
    check: [['path', {d:'M5 12l4 4L19 6'}]],
    alert: [['path', {d:'M12 3L2 21h20L12 3zM12 9v5M12 17v.5'}]],
    clock: [['circle', {cx:12, cy:12, r:9}], ['path', {d:'M12 7v5l3 2'}]],
    sparkle: [['path', {d:'M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3z'}]],
    lock: [['rect', {x:5, y:11, width:14, height:10, rx:2}],
      ['path', {d:'M8 11V8a4 4 0 0 1 8 0v3'}]],
    copy: [['rect', {x:8, y:8, width:13, height:13, rx:2}],
      ['path', {d:'M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3'}]],
    undo: [['path', {d:'M8 4L3 9l5 5M3 9h11a7 7 0 0 1 0 14'}]],
    'arrow-right': [['path', {d:'M5 12h14M13 6l6 6-6 6'}]],
    eye: [['path', {d:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z'}],
      ['circle', {cx:12, cy:12, r:3}]],
    play: [['path', {d:'M7 4l14 8-14 8V4z'}]],
    pause: [['path', {d:'M8 5v14M16 5v14'}]],
    'chevron-down': [['path', {d:'M6 9l6 6 6-6'}]],
    list: [['path', {d:'M9 6h12M9 12h12M9 18h12M3 6h1M3 12h1M3 18h1'}]],
    share: [['circle', {cx:18, cy:5, r:3}], ['circle', {cx:6, cy:12, r:3}],
      ['circle', {cx:18, cy:19, r:3}], ['path', {d:'M8.6 10.5l6.8-4M8.6 13.5l6.8 4'}]],
    download: [['path', {d:'M12 3v12M7 10l5 5 5-5M4 16v5h16v-5'}]],
    'text-size': [['path', {d:'M3 5h12M9 5v15M17 11h6M20 11v9'}]],
    dot: [['circle', {cx:12, cy:12, r:2}]],
    minus: [['path', {d:'M5 12h14'}]],
  };
  const svgNode = (tag, attrs) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
    return node;
  };

  SC.icon = (name, {size = 18} = {}) => {
    const svg = svgNode('svg', {
      viewBox:'0 0 24 24', width:size, height:size, fill:'none', stroke:'currentColor',
      'stroke-width':1.75, 'stroke-linecap':'round', 'stroke-linejoin':'round',
      'aria-hidden':'true', focusable:'false',
    });
    for (const [tag, attrs] of shapes[name] || []) svg.append(svgNode(tag, attrs));
    return svg;
  };
})();
