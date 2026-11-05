/* Home extras: the logo mark, the three-step "How it works" row with small real micro-visuals (a phone, a fix card,
   a Slack post), and the interactive example. Nothing here reads or stores survey data. */
(() => {
  'use strict';
  const SC = window.SC, {h, mount, $} = SC;

  $('home-logo')?.replaceWith(SC.logoMark({size: 32}));

  const phone = () => h('div', {class: 'mv mv-phone'},
    h('span', {class: 'mv-line mv-title'}), h('span', {class: 'mv-line'}), h('span', {class: 'mv-line mv-short'}),
    h('span', {class: 'mv-option'}), h('span', {class: 'mv-option mv-picked'}), h('span', {class: 'mv-pin'}, '1'));
  const fixCard = () => h('div', {class: 'mv mv-fix'}, SC.stateChip('fix_before_launch'),
    h('span', {class: 'mv-old'}, 'Taste and price?'), h('span', {class: 'mv-new'}, 'How is the taste?'));
  const slack = () => h('div', {class: 'mv mv-slack'},
    h('span', null, 'Survey review: Holiday Snacks (v2)'), h('span', null, 'Verdict: Ready for sign-off · ~6 min'), h('span', null, 'Checked by hand: images load'));

  const STEPS = [
    ['See it like a member', 'Paste a test link. Play your survey on a phone and see where members may stumble.', phone],
    ['Fix what matters', 'Get paste-ready wording for each problem. Add the changes you want to your list.', fixCard],
    ['Sign off and share', 'Copy a Slack post, sign off with your name, and keep a record of what you checked.', slack],
  ];
  mount($('how-steps'), STEPS.map(([title, text, visual], index) => h('li', {class: 'how-step'},
    h('div', {class: 'mv-frame', 'aria-hidden': 'true'}, visual()),
    h('h3', null, h('span', {class: 'how-n', 'aria-hidden': 'true'}, String(index + 1)), title), h('p', null, text))));

  // The example: Use swaps the struck-through question for the new wording; Reset puts it back.
  const NEW = 'How satisfied are you with the taste?', OLD = 'How satisfied are you with the taste and price?';
  const question = $('demo-question'), chip = $('demo-chip');
  function demo(used) {
    question.textContent = used ? NEW : OLD;
    question.className = used ? 'now' : 'before';
    chip.textContent = used ? '1 thing to fix before launch' : '2 things to fix before launch';
    $('demo-suggestion').hidden = used;
    $('demo-done').hidden = !used;
    $('demo-status').textContent = used ? `Question 4 now reads: ${NEW}` : `Question 4 is back to: ${OLD}`;
    (used ? $('demo-reset') : $('demo-use')).focus({preventScroll: true});
  }
  $('demo-use').addEventListener('click', () => demo(true));
  $('demo-reset').addEventListener('click', () => demo(false));
})();
