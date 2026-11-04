/* Plain-language reader disclosure and actual captured progress, never simulated progress. */
(() => {
  'use strict';
  const SC=window.SC, {h}=SC;
  fetch('/api/reader/mode').then(response=>response.ok?response.json():null).then(mode=>{
    if(mode && document.getElementById('reader-mode')) document.getElementById('reader-mode').textContent=mode.notice;
  }).catch(()=>{});
  // Rechecks retain their existing captured preview; Task 8 changes Home only.
  function recheckPreview(job, jobId, output) {
    if (!job.pages_captured) return;
    let preview=document.getElementById('reading-preview');
    if (!preview) {
      preview=h('figure',{id:'reading-preview',class:'reading-preview'},h('figcaption'),
        h('img',{alt:'Latest captured survey screen. Not an interactive survey.'}));
      output.after(preview);
    }
    const image=preview.querySelector('img');
    const source=`/api/reader/jobs/${encodeURIComponent(jobId)}/preview/${job.pages_captured-1}`;
    if(image.getAttribute('src')!==source) image.src=source;
    preview.querySelector('figcaption').textContent=job.stage==='checking'
      ? `${job.pages_captured} screens captured · checking wording and flow…`
      : `Reading screen ${job.pages_captured} · only the visited path is checked`;
  }
  SC.renderReadProgress=(job,jobId)=>{
    const output=document.getElementById('import-status');
    if(!output) return;
    if(!document.body.classList.contains('home')) return recheckPreview(job,jobId,output);
    let preview=document.getElementById('reading-preview');
    if(!preview) {
      preview=h('figure',{id:'reading-preview',class:'reading-preview'},
        h('div',{class:'reading-phone', 'aria-label':'Survey capture preview'}, SC.icon('eye')),
        h('figcaption',{id:'reading-progress',role:'status','aria-live':'polite'}),
        h('ol',{id:'reading-steps'}));
      output.after(preview);
    }
    const completed=job.status==='completed', checking=job.stage==='checking';
    const count=Number(job.pages_captured) || 0;
    if(count) {
      let image=preview.querySelector('img');
      if(!image) {
        image=h('img',{alt:'Latest captured survey screen. Not an interactive survey.'});
        SC.mount(preview.querySelector('.reading-phone'),image);
      }
      const source=`/api/reader/jobs/${encodeURIComponent(jobId)}/preview/${count-1}`;
      if(image.getAttribute('src')!==source) image.src=source;
    }
    preview.querySelector('figcaption').textContent=job.status==='failed' ? job.error || 'Review did not finish.'
      : completed ? 'Review saved.'
      : checking ? `${count} screens captured. Checking wording and flow…`
      : job.stage==='reading' ? count ? `Reading screen ${count}…` : 'Opening the test survey…'
      : job.status==='queued' ? 'Review queued…' : 'Checking survey wording and flow…';
    SC.mount(preview.querySelector('ol'), ['Read captured screens','Check wording and flow','Save review'].map((label,index)=>{
      const done=completed || (index===0 && checking);
      return h('li',{'data-complete':String(done)},SC.icon(done?'check':'clock'),label);
    }));
  };
})();
