/* Plain-language reader disclosure and actual captured progress, never simulated progress. */
(() => {
  'use strict';
  const SC=window.SC, {h}=SC;
  fetch('/api/reader/mode').then(response=>response.ok?response.json():null).then(mode=>{
    if(mode && document.getElementById('reader-mode')) document.getElementById('reader-mode').textContent=mode.notice;
  }).catch(()=>{});
  SC.renderReadProgress=(job,jobId)=>{
    const output=document.getElementById('import-status');
    if(!output || !job.pages_captured) return;
    let preview=document.getElementById('reading-preview');
    if(!preview) {
      preview=h('figure',{id:'reading-preview',class:'reading-preview'},h('figcaption',null,'Watch the captured path unfold'),
        h('img',{alt:'Latest captured survey screen. Not an interactive survey.'}));
      output.after(preview);
    }
    const image=preview.querySelector('img');
    const source=`/api/reader/jobs/${encodeURIComponent(jobId)}/preview/${job.pages_captured-1}`;
    if(image.getAttribute('src')!==source) image.src=source;
    preview.querySelector('figcaption').textContent=job.stage==='checking'
      ? `${job.pages_captured} screens captured · checking wording and flow…`
      : `Reading screen ${job.pages_captured} · only the visited path is checked`;
  };
})();
