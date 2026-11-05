/* The two quiet end states of the fix flow: a screen with nothing to fix, and everything handled. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  const checkAgain = () => document.getElementById('check-again')?.click();

  /** D13: a compact row, never a dead end. "Next item" is the server's next open item after the user's place. */
  SC.renderNothingHere = (queue, next) => h('section', {class:'nothing-here', 'aria-labelledby':'coach-h'},
    h('span', {class:'nothing-icon'}, SC.icon('check-circle', {size:24})),
    h('h3', {id:'coach-h', tabindex:'-1'}, 'Nothing to fix on this screen'),
    next ? h('button', {type:'button', id:'next-item', class:'btn btn-primary', onclick:() => queue.select(next)}, `Next item: ${next.title} →`)
      : h('button', {type:'button', id:'go-signoff', class:'btn btn-primary', onclick:() => SC.goChapter('share')}, 'Go to Sign off'));

  /** The one celebration: a warm check and a short burst of dots, only when the last item is handled. */
  SC.renderCompletion = queue => h('section', {class:'completion', 'aria-labelledby':'coach-h'},
    h('div', {class:'celebrate-mark', 'aria-hidden':'true'},
      Array.from({length:8}, (_, i) => h('span', {class:'celebrate-dot', style:`--i:${i}`})), SC.icon('check', {size:36})),
    h('h3', {id:'coach-h', tabindex:'-1'}, `All ${queue.progress().total} handled. Check your updated survey to confirm.`),
    h('div', {class:'decision-actions'},
      h('button', {type:'button', id:'check-again-done', class:'btn btn-primary', onclick:checkAgain}, 'Check again'),
      h('button', {type:'button', id:'go-signoff', class:'btn', onclick:() => SC.goChapter('share')}, 'Go to Sign off')));
})();
