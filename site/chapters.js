/* The hash is the route. History and ordinary hash links share one render path. */
(() => {
  'use strict';
  const SC = window.SC;
  SC.CHAPTERS = Object.freeze(['overview', 'improve', 'share']);
  let shown = null;
  SC.currentChapter = () => {
    const name = location.hash.slice(1);
    return SC.CHAPTERS.includes(name) ? name : 'overview';
  };
  SC.showChapter = (name, options = {}) => {
    if (!SC.CHAPTERS.includes(name) || shown === name) return;
    shown = name;
    for (const chapter of SC.CHAPTERS) {
      document.getElementById(`chapter-${chapter}`).hidden = chapter !== name;
      const link = document.querySelector(`#chapter-nav [data-chapter="${chapter}"]`);
      if (chapter === name) link.setAttribute('aria-current', 'step');
      else link.removeAttribute('aria-current');
    }
    // Render listeners run synchronously before focus, including a lazy first render.
    window.dispatchEvent(new CustomEvent('surveycoach-chapter', {detail: {name, options}}));
    document.querySelector(`#chapter-${name} h2`)?.focus({preventScroll: true});
    window.scrollTo({top: 0, left: 0,
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  };
  SC.goChapter = (name, options = {}) => {
    if (!SC.CHAPTERS.includes(name)) return;
    if (SC.currentChapter() !== name) {
      const url = new URL(location.href);
      url.hash = name;
      history.pushState(null, '', url);
    }
    SC.showChapter(name, options);
  };
  document.getElementById('chapter-nav').addEventListener('click', event => {
    const link = event.target.closest('a[data-chapter]');
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    SC.goChapter(link.dataset.chapter);
  });
  const sync = () => SC.showChapter(SC.currentChapter());
  window.addEventListener('popstate', sync);
  window.addEventListener('hashchange', sync);
  window.addEventListener('surveycoach-focus-finding', () => SC.goChapter('improve'));
  sync();
})();
