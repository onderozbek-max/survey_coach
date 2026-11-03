"""Small deterministic DOM adapter, not a guessed RedJade definition parser."""
OBSERVE = r"""() => {
  const visible = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e);
    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };
  const text = e => e ? e.innerText.trim() : '';
  const answerRole = '[role=radio],[role=checkbox]';
  const controls = [...document.querySelectorAll('input:not([type=hidden]),textarea,select,' + answerRole)].filter(visible);
  // RedJade's field-local Clear control is not a navigation action. Require
  // its exact ID convention and a corresponding text field; unknown buttons still stop.
  const fieldClear = e => e.tagName==='BUTTON' && e.type==='button' &&
    e.id.startsWith('input-clear-') &&
    document.getElementById(e.id.slice('input-clear-'.length))?.matches('textarea,input[type=text]');
  // ARIA answer controls may be <button>s (RedJade); they are answers, never navigation.
  const buttons = [...document.querySelectorAll('button,input[type=submit],input[type=button],a[href],[role=button]')]
    .filter(e => visible(e) && !e.matches(answerRole) && !fieldClear(e));
  const tag = (e,id) => {e.setAttribute('data-surveycoach-id',id); return id;};
  const label = e => e.getAttribute('aria-label') || (e.labels?.length ? text(e.labels[0]) : text(e));
  const nav = buttons.map((e,i)=>({id:tag(e,'nav-'+i), label:label(e)||e.value||'',
    disabled:e.disabled || e.getAttribute('aria-disabled')==='true'}));
  let unsupported = [...document.querySelectorAll('canvas,iframe,video,[role=slider],[draggable=true],input[type=password],input[type=file],input[type=range]')].some(visible);
  // Only next/final buttons and explicit ARIA options are understood. Guessing is unsafe.
  unsupported ||= buttons.some(e => !/^(next|continue|begin|start|submit\b.*|finish\b.*|complete\b.*|done\b.*)$/i.test(label(e)||e.value||''));
  const answer = controls.filter(e=>e.matches(answerRole) || !['submit','button'].includes(e.type));
  const grouped = new Map();
  for (const e of answer) {
    // RedJade groups a question as title + .taker-question-slot-container, without fieldsets.
    const container = e.closest('fieldset,[role=radiogroup],[role=group]') ||
      e.closest('.taker-question-slot-container')?.parentElement || null;
    const key = container || (e.name && ['radio','checkbox'].includes(e.type) ? e.name : e);
    if (!grouped.has(key)) grouped.set(key,{container,els:[]});
    grouped.get(key).els.push(e);
  }
  const groups=[];
  for (const {container,els} of grouped.values()) {
    const first=els[0], table=first.closest('table');
    const types = [...new Set(els.map(e=>e.getAttribute('role')||e.type||e.tagName.toLowerCase()))];
    let kind='unknown';
    if(types.length===1) {
      const t=types[0];
      kind=({radio:'single_choice',checkbox:'multi_choice',textarea:'text_long',
        text:'text_short',number:'numeric','select-one':'dropdown'})[t]||'unknown';
    }
    if(table && ['single_choice','multi_choice'].includes(kind)) kind=kind==='single_choice'?'grid_single':'grid_multi';
    const legend=container?.querySelector(':scope > legend');
    const named=container?.getAttribute('aria-label');
    const ref=container?.getAttribute('aria-labelledby');
    const prompt=text(legend)||named||(ref ? text(document.getElementById(ref)) : '')||
      (table ? text(table.querySelector('caption')) : '')||text(container?.querySelector('.taker-title'))||
      (!['single_choice','multi_choice'].includes(kind) ? label(first) : '');
    if(!prompt || kind==='unknown') unsupported=true;
    const groupIndex=groups.length;
    const items=els.map((e,i)=>{
      const row=e.closest('tr');
      const col=row ? [...row.children].indexOf(e.closest('td,th')) : -1;
      const header=table && col>=0 ? table.querySelector('tr')?.children[col] : null;
      return {id:tag(e,'answer-'+groupIndex+'-'+i),label:label(e)||text(header),
        row:row ? text(row.querySelector('th')) : '',name:e.name||'',type:e.type||e.getAttribute('role'),
        checked:!!e.checked||e.getAttribute('aria-checked')==='true'||!!e.querySelector?.('input:checked'),value:e.value||'',disabled:!!e.disabled,
        min:e.min||'',max:e.max||'',required:!!e.required||e.getAttribute('aria-required')==='true',
        options:e.tagName==='SELECT'?[...e.options].map(o=>({label:o.text,value:o.value,disabled:o.disabled})):[]};
    });
    const sourceId=container?.getAttribute('data-question-id') || container?.getAttribute('data-question-cid') || null;
    groups.push({prompt,kind,items,source_id:sourceId,required:items.some(i=>i.required)});
  }
  const media=[...document.images].filter(visible).map((e,i)=>{
    const r=e.getBoundingClientRect();
    return {element_id:tag(e,'image-'+i),alt:e.getAttribute('alt'),natural_w:e.naturalWidth,
      natural_h:e.naturalHeight,rendered_w:Math.round(r.width),rendered_h:Math.round(r.height),
      loaded:e.complete && e.naturalWidth>0,object_fit:getComputedStyle(e).objectFit};
  });
  const pageText=text(document.body);
  const sourcePages=[...document.querySelectorAll('[data-page-id]')].filter(visible);
  const source_page_id=sourcePages.length===1 ? sourcePages[0].getAttribute('data-page-id') : null;
  return {title:document.title,text:pageText,groups,nav,media,unsupported,source_page_id,
    screenout:/do not qualify|not eligible|screened out|not qualified/i.test(pageText)};
}"""
