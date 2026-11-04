/* Word-level before/after, shared by the decision panel and the change list. */
(() => {
  'use strict';
  const SC = window.SC, {h} = SC;

  SC.wordDiff = (before, after) => {
    const tokens = s => (s || '').split(/(\s+|[.,!?;:]+(?=\s|$))/).filter(Boolean);
    const a = tokens(before), b = tokens(after), n = a.length, m = b.length;
    if (n * m > 40000) return [{type:'del', text:before}, {type:'ins', text:after}];
    const dp = Array.from({length:n + 1}, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const out = [], push = (type, text) => {
      const last = out[out.length - 1];
      if (last && last.type === type) last.text += text;
      else out.push({type, text});
    };
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { push('same', a[i]); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) push('del', a[i++]);
      else push('ins', b[j++]);
    }
    while (i < n) push('del', a[i++]);
    while (j < m) push('ins', b[j++]);
    return out;
  };

  SC.renderDiff = (before, after) => h('p', {class:'diff'}, SC.wordDiff(before, after).map(segment =>
    segment.type === 'same' ? segment.text : h(segment.type, null, segment.text)));
})();
