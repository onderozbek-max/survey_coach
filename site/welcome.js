/* The landing page's "check your own survey" line: a safe link to the team tool when its address is configured
   (environment.js), otherwise a plain sentence saying how to get access. Never a dead link. */
(() => {
  'use strict';
  const {h, mount, $} = window.SC;
  const team = window.SC.teamAddress(window.SURVEYCOACH_TEAM_URL);
  mount($('own-survey'), team
    ? ['Want your own survey checked? ', h('a', {href: team, rel: 'noopener noreferrer'}, 'Check your own survey')]
    : 'To check your own survey, ask the SurveyCoach owner for the team link.');
})();
