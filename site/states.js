/* The four-state language (brief 4.2): one table, one chip. The icon shape and the words carry the state;
   colour only reinforces them. Server payloads supply the state id; this file owns how it looks and reads. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;
  SC.STATES = Object.freeze({
    fix_before_launch: {label: 'Fix before launch', icon: 'alert-filled'},
    worth_improving: {label: 'Worth improving', icon: 'ring'},
    you_check: {label: 'You check', icon: 'eye'},
    looks_good: {label: 'Looks good', icon: 'check-circle'},
  });
  SC.NO_STATE = Object.freeze({label: 'Not checked automatically', icon: 'minus'});

  /** Icon plus words, never colour alone. A null or unknown state reads as "not checked", never as good. */
  SC.stateChip = (state, {label, className = ''} = {}) => {
    const known = SC.STATES[state] || SC.NO_STATE;
    return h('span', {class: `state-chip ${className}`.trim(), 'data-state': SC.STATES[state] ? state : 'none'},
      SC.icon(known.icon, {size: 16}), h('span', null, label || known.label));
  };

  /** A bare state icon for lists and tiles. Pair it with text; it is decorative on its own. */
  SC.stateIcon = state => h('span', {class: 'state-icon', 'data-state': SC.STATES[state] ? state : 'none'},
    SC.icon((SC.STATES[state] || SC.NO_STATE).icon, {size: 16}));

  /** One verdict -> one state chip: the same mapping on the Verdict page and on every Home card. */
  SC.verdictState = verdict => {
    if (!verdict) return {state: null, label: 'Not checked yet'};
    if (verdict.kind === 'fix_before_launch') return {state: 'fix_before_launch', label: 'Fix before launch'};
    if (verdict.kind === 'ready_for_signoff') return {state: 'looks_good', label: 'Ready for sign-off'};
    return {state: verdict.tiles?.improve > 0 ? 'worth_improving' : 'you_check', label: 'Almost ready'};
  };

  /** Everything still open, from the same tiles the verdict shows. */
  SC.openCount = tiles => (tiles ? tiles.fix + tiles.improve + tiles.you_check : 0);
})();
