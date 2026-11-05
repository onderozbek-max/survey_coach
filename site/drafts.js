/* The alternative a researcher is trying on a finding, before any Use. One store feeds coach, comparison and phone,
   so they cannot disagree. Never persisted: only Use saves a decision. */
(() => {
  'use strict';
  const SC = window.SC;
  const picked = new Map();
  // A draft means "this candidate of this candidate set in this version"; any change to the set invalidates it.
  const signature = f => JSON.stringify(SC.choicesOf(f).map(c => [c.value, c.text]));
  SC.drafts = {
    get(f, scope) {
      const draft = f && picked.get(f.fingerprint);
      if (!draft) return undefined;
      if (draft.scope === scope && draft.signature === signature(f)) return draft.value;
      picked.delete(f.fingerprint);
      return undefined;
    },
    set: (f, scope, value) => { picked.set(f.fingerprint, {scope, signature: signature(f), value}); },
    clear: fingerprint => { picked.delete(fingerprint); },
  };
})();
