/* The public sample says what it is. Shown only on the static build (SURVEYCOACH_LOCAL === false), never on the
   private server. The team's real address comes from environment.js (the private server overrides that file) and is
   linked only when it is a plain https URL; otherwise the banner says how to get access and never offers a dead link. */
(() => {
  'use strict';
  const {h} = window.SC;

  /** The configured team address as a safe absolute https URL, or null. */
  const teamAddress = value => {
    if (typeof value !== 'string') return null;
    try {
      const url = new URL(value.trim());
      return url.protocol === 'https:' && url.hostname ? url.href : null;
    } catch { return null; }
  };

  const banner = () => {
    const team = teamAddress(window.SURVEYCOACH_TEAM_URL);
    return h('aside', {id: 'sample-banner', class: 'sample-banner', role: 'note', 'aria-label': 'About this sample'},
      h('p', null,
        h('strong', null, 'Sample review'), ' · a fictional survey with made-up data. Nothing here is saved or sent. ',
        team
          ? h('a', {href: team, rel: 'noopener noreferrer', class: 'sample-banner-link'}, 'Check your own survey')
          : 'To check your own survey, ask the SurveyCoach owner for the team link.'));
  };

  if (window.SURVEYCOACH_LOCAL === false) {
    // Verdict only: in Fix and Sign off the phone has to stay the hero, and the visitor has already read this.
    const chapterOf = hash => (hash || '').replace('#', '') || 'overview';
    const place = () => {
      const note = banner();
      note.hidden = chapterOf(location.hash) !== 'overview';
      document.body.insertBefore(note, document.getElementById('app-header') || document.body.firstChild);
      window.addEventListener('surveycoach-chapter', event => { note.hidden = event.detail.name !== 'overview'; });
    };
    document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', place) : place();
  }
})();
