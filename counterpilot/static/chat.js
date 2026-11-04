'use strict';
(() => {
 const $=id=>document.getElementById(id);
 const fields=['year','make','model','engine','part','position','side','trim','drivetrain','hybrid','symptoms'];
 const storageKey='counterpilot-chat-v3';
 let history=[],snapshots=[],details={},lastResult=null,pending=null,controller=null,version=0,busy=false;
 let registered={vehicles:[],part_types:[],part_aliases:[]},catalogLoaded=false,panelDismissed=false,lastKnownCount=0;
 let openCombo=null,comboValues=[],comboIndex=-1,exampleIndex=0,exampleTimer=null,examples=[];
 const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
 const narrowPanel=window.matchMedia('(max-width: 1239px)');
 let hintTimer=null,hintFadeTimer=null,carTimer=null;
 const seenHints=new Set();
 const compared=new Map();
 function clearComparison(){compared.clear();document.querySelectorAll('.compare-choice input').forEach(input=>input.checked=false);if($('compare-dialog').open)$('compare-dialog').close();$('compare-items').replaceChildren();syncComparison();}
 function syncComparison(){
  document.querySelectorAll('.compare-choice input').forEach(input=>{input.disabled=busy||!!pending||input.closest('.previous-result')!==null||(!input.checked&&compared.size>=3);});
  document.querySelectorAll('.compare-open').forEach(button=>button.disabled=busy||!!pending||!!button.closest('.previous-result')||compared.size<2);
  document.querySelectorAll('.compare-status').forEach(node=>node.textContent=node.closest('.previous-result')?'Previous results cannot be compared.':compared.size?`${compared.size} selected · choose up to 3`:'Select 2 or 3 records to compare.');
 }
 function productPhoto(part){
  const figure=el('figure',undefined,'product-photo'),fallback=el('div',part.name||'Part photo','photo-fallback');figure.append(fallback);
  const image=part.image;
  if(image&&/^\/static\/parts\/[a-z_]+\.jpg$/.test(image.url)){
   const img=el('img');img.width=320;img.height=240;img.alt=typeof image.alt==='string'?image.alt:'Generic part illustration';img.decoding='async';img.loading='lazy';
   fallback.hidden=true;img.onerror=()=>{img.hidden=true;fallback.hidden=false;};img.src=image.url;figure.prepend(img);
  }
  figure.append(el('figcaption','Illustrative photo'));return figure;
 }
 function priceText(part){
  const p=part.price;
  if(!p||p.currency!=='USD'||!['each','pair','axle set'].includes(p.unit)||!/^\d{1,6}(\.\d{1,2})?$/.test(String(p.amount))||Number(p.amount)<=0)return 'Price unavailable';
  return `${part.data_status==='sample'?'Demo price':'Listed price'} · ${new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(p.amount))} / ${p.unit}`;
 }
 function profileText(profile){return profile?`Catalog configuration: ${profile.year} ${profile.make} ${profile.model} · ${profile.description}`:'';}
 function openComparison(){
  if(compared.size<2||busy||pending)return;const host=$('compare-items');host.replaceChildren();host.classList.toggle('three-items',compared.size===3);
  for(const {part,profile} of compared.values()){
   const item=el('article',undefined,'comparison-item');item.append(productPhoto(part),el('span',part.display_label,'badge'),el('h3',part.name),el('p',part.part_number,'part-number'),el('p',priceText(part),'part-price'),el('p','Brand: '+part.brand,'candidate-brand'),el('p',profileText(profile),'candidate-vehicle'));
   for(const restriction of part.restrictions||[])item.append(el('p',restriction,'hint'));
   for(const evidence of part.evidence||[])item.append(el('p',evidence.statement,'hint'),el('p','Source: '+evidence.source,'hint'));
   host.append(item);
  }
  $('compare-dialog').showModal();$('close-compare').focus();
 }
 function hideHint(){clearTimeout(hintTimer);clearTimeout(hintFadeTimer);$('chat-hint').classList.remove('hint-visible');hintFadeTimer=setTimeout(()=>{$('chat-hint').hidden=true;},reducedMotion.matches?0:180);}
 function showHint(key,text){
  if(seenHints.has(key))return;seenHints.add(key);clearTimeout(hintTimer);clearTimeout(hintFadeTimer);
  $('chat-hint-text').textContent=text;$('chat-hint').hidden=false;
  // A separate frame lets the small popover fade in without moving keyboard focus.
  requestAnimationFrame(()=>$('chat-hint').classList.add('hint-visible'));
  hintTimer=setTimeout(hideHint,8000);
 }
 function startCar(){
  clearTimeout(carTimer);const track=$('composer-track');track.classList.remove('is-driving');
  if(reducedMotion.matches)return;
  void track.offsetWidth;track.classList.add('is-driving');
  carTimer=setTimeout(()=>track.classList.remove('is-driving'),1500);
 }
 function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
 function save(){
  if(history.length>60){const removed=history.length-60;history=history.slice(removed);snapshots=snapshots.filter(s=>s.messageIndex>=removed).map(s=>({...s,messageIndex:s.messageIndex-removed}));}
  try{sessionStorage.setItem(storageKey,JSON.stringify({history,snapshots,details,lastResult,panelDismissed,pending:pending?{text:pending.text,payload:pending.payload}:null,draft:$('chat-input').value}));}catch{if($('storage-status'))$('storage-status').hidden=false;}
 }
 function bubble(role,text,welcome=false){const node=el('div',undefined,'chat-message '+role+(welcome?' welcome':''));node.append(el('span',role==='user'?'YOU':'COUNTERPILOT','chat-speaker'),el('div',text,'chat-bubble'));$('chat-messages').append(node);return node;}
 function scroll(target){const log=$('chat-messages');if(target){log.scrollTop+=target.getBoundingClientRect().top-log.getBoundingClientRect().top-10;}else log.scrollTop=log.scrollHeight;}
 function context(){const items=history.slice(-20).map(({role,content})=>({role,content}));while(items.length&&(items.reduce((sum,m)=>sum+m.content.length,0)>20000||new TextEncoder().encode(JSON.stringify(items)).length>32000))items.shift();return items;}
 function normalizeEngine(value){
  if(value==null)return null;
  const text=String(value).trim().replace(/\b(?:liters?|litres?)\b/gi,'L');
  return /^\d+(?:\.\d+)?\s*[lL]?$/.test(text)?`${Number.parseFloat(text)}L`:text;
 }
 function fieldValue(field){
  const raw=$('chat-'+field).value.trim();if(!raw)return null;
  if(field==='year')return Number(raw);
  if(field==='engine')return normalizeEngine(raw);
  if(field==='hybrid'){const normalized=raw.toLowerCase();if(['hybrid','yes','true'].includes(normalized))return true;if(['non-hybrid','non hybrid','no','false'].includes(normalized))return false;return raw;}
  return ['position','side'].includes(field)?raw.toLowerCase():raw;
 }
 function fieldText(field,value){return value==null?'':field==='hybrid'?(value?'Hybrid':'Non-hybrid'):String(value);}
 function readEdits(){const edits={};for(const f of fields){const value=fieldValue(f),previous=f==='engine'?normalizeEngine(details[f]):(details[f]??null);if(value!==previous)edits[f]=value;}return edits;}
 function validateEdits(){
  for(const f of fields){const input=$('chat-'+f),value=fieldValue(f);input.setCustomValidity('');if(value==null)continue;
   if(f==='year'&&(!/^\d{4}$/.test(input.value.trim())||value<1980||value>2100))input.setCustomValidity('Enter a four-digit year from 1980 to 2100.');
   if(f==='position'&&!['front','rear'].includes(value))input.setCustomValidity('Enter Front or Rear, or leave blank.');
   if(f==='side'&&!['left','right'].includes(value))input.setCustomValidity('Enter Left or Right, or leave blank.');
   if(f==='hybrid'&&typeof value!=='boolean')input.setCustomValidity('Enter Hybrid or Non-hybrid, or leave blank.');
  }
  return $('chat-details-form').reportValidity();
 }
 function setDetailsOpen(open,user=false){
  $('lookup-panel').hidden=!open;$('details-toggle').setAttribute('aria-expanded',String(open));
  document.body.classList.toggle('details-open',open);$('details-dismiss').hidden=!open||!narrowPanel.matches;
  if(!open)closeCombo();
  const modal=open&&narrowPanel.matches;$('lookup-panel').setAttribute('role',modal?'dialog':'complementary');
  if(modal)$('lookup-panel').setAttribute('aria-modal','true');else $('lookup-panel').removeAttribute('aria-modal');
  document.querySelector('.app-main').inert=modal;document.querySelector('.app-bar').inert=modal;
  if(user){panelDismissed=!open;save();if(open&&modal)$('close-details').focus({preventScroll:true});}
 }
 function updateLayout(){
  const active=history.length>0||!!pending;
  $('active-title').hidden=!active;document.body.classList.toggle('is-empty',!active);document.body.classList.toggle('chat-active',active);
  $('header-brand').hidden=!active;$('search-intro').hidden=active;$('new-conversation').hidden=!active;
  $('lookup-examples').hidden=active;$('chat-send').replaceChildren(document.createTextNode(active?'Send ':'Chat '),el('span','\u2191'));
  scheduleExamples();
 }
 function optionsFor(field){
  const value=f=>fieldValue(f),byYear=registered.vehicles.filter(v=>value('year')==null||v.year===value('year'));
  const byMake=byYear.filter(v=>!value('make')||v.make.toLowerCase()===String(value('make')).toLowerCase());
  const profiles=byMake.filter(v=>!value('model')||v.model.toLowerCase()===String(value('model')).toLowerCase());
  let values=[];
  if(field==='year')values=registered.vehicles.map(v=>String(v.year));
  else if(field==='make')values=byYear.map(v=>v.make);
  else if(field==='model')values=byMake.map(v=>v.model);
  else if(['engine','trim','drivetrain'].includes(field))values=profiles.map(v=>v[field]);
  else if(field==='hybrid')values=profiles.map(v=>v.fuel_type?.includes('hybrid')?'Hybrid':['gasoline','diesel'].includes(v.fuel_type)?'Non-hybrid':null);
  else if(field==='part')values=registered.part_types.map(p=>p.name);
  else if(['position','side'].includes(field)){
   const normalize=text=>String(text||'').toLowerCase().replace(/[_-]/g,' ').trim();
   const part=normalize(value('part'));
   const type=registered.part_types.find(p=>[normalize(p.name),normalize(p.id)].includes(part))?.id||registered.part_aliases.find(a=>normalize(a.alias)===part)?.part_type;
   const kinds=registered.part_types.filter(p=>!type||p.id===type);
   values=kinds.flatMap(p=>p[field==='position'?'positions':'sides']||[]).map(s=>s[0].toUpperCase()+s.slice(1));
  }
  values=[...new Set(values.filter(v=>v!=null&&v!==''&&v!=='unknown'))];
  return field==='year'?values.sort((a,b)=>Number(b)-Number(a)):values.sort((a,b)=>a.localeCompare(b));
 }
 function closeCombo(){if(!openCombo)return;const input=$('chat-'+openCombo);input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');$('options-'+openCombo).hidden=true;openCombo=null;comboValues=[];comboIndex=-1;}
 function showCombo(field,all=false){
  if($('chat-'+field).disabled)return;
  if(openCombo&&openCombo!==field)closeCombo();openCombo=field;comboIndex=-1;
  const input=$('chat-'+field),list=$('options-'+field),query=all?'':input.value.trim().toLowerCase();
  const engineQuery=field==='engine'?normalizeEngine(query):null;
  const choices=optionsFor(field).filter(v=>!query||v.toLowerCase().includes(query)||(engineQuery&&/^\d+(?:\.\d+)?L$/.test(engineQuery)&&Number.parseFloat(v)===Number.parseFloat(engineQuery)));
  comboValues=choices.slice(0,10).map(value=>({label:value,value}));comboValues.push({label:'Unknown / leave blank',value:''});
  list.replaceChildren();
  if(!choices.length)list.append(el('div',catalogLoaded?'No registered match. You can still type.':'Suggestions unavailable. You can still type.','combo-empty'));
  for(const [index,choice] of comboValues.entries()){
   const option=el('div',choice.label);option.id=`option-${field}-${index}`;option.setAttribute('role','option');option.setAttribute('aria-selected','false');
   option.onpointerdown=event=>event.preventDefault();option.onclick=()=>chooseCombo(index);list.append(option);
  }
  const available=Math.min(innerHeight,$('lookup-panel').getBoundingClientRect().bottom)-input.getBoundingClientRect().bottom;
  list.classList.toggle('open-above',available<Math.min(170,comboValues.length*34+12));
  list.hidden=false;input.setAttribute('aria-expanded','true');input.removeAttribute('aria-activedescendant');
 }
 function chooseCombo(index){
  const field=openCombo,choice=comboValues[index];if(!field||!choice)return;
  const input=$('chat-'+field);input.value=choice.value;input.setCustomValidity('');closeCombo();input.focus({preventScroll:true});input.dispatchEvent(new Event('input',{bubbles:true}));closeCombo();
 }
 function initializeComboboxes(){
  for(const field of fields){
   const input=$('chat-'+field),label=input.closest('label'),name=label.firstChild.textContent.trim();
   const wrapper=el('div',undefined,'combobox'),toggle=el('button','\u25be','combo-toggle'),list=el('div',undefined,'combo-list');
   input.before(wrapper);wrapper.append(input);toggle.type='button';toggle.tabIndex=-1;toggle.setAttribute('aria-label','Show '+name+' suggestions');wrapper.append(toggle);
   list.id='options-'+field;list.hidden=true;list.setAttribute('role','listbox');list.setAttribute('aria-label',name+' suggestions');label.append(list);
   input.setAttribute('role','combobox');input.setAttribute('aria-label',name);input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-haspopup','listbox');input.setAttribute('aria-expanded','false');input.setAttribute('aria-controls',list.id);
   toggle.onclick=()=>{if(openCombo===field)closeCombo();else{input.focus({preventScroll:true});showCombo(field,true);}};
   input.addEventListener('focus',()=>showCombo(field,true));
   input.addEventListener('input',()=>{input.setCustomValidity('');showCombo(field);});
   input.addEventListener('blur',()=>setTimeout(()=>{if(openCombo===field&&!wrapper.contains(document.activeElement))closeCombo();},0));
   input.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&openCombo){event.preventDefault();event.stopPropagation();closeCombo();return;}
    if(event.key==='Tab'){closeCombo();return;}
    if(event.key==='Enter'&&openCombo===field&&comboIndex>=0){event.preventDefault();chooseCombo(comboIndex);return;}
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){
     event.preventDefault();if(openCombo!==field)showCombo(field,true);
     comboIndex=event.key==='ArrowDown'?(comboIndex+1)%comboValues.length:(comboIndex<=0?comboValues.length-1:comboIndex-1);
     const items=$('options-'+field).querySelectorAll('[role="option"]');items.forEach((node,index)=>node.setAttribute('aria-selected',String(index===comboIndex)));
     input.setAttribute('aria-activedescendant',items[comboIndex].id);items[comboIndex].scrollIntoView({block:'nearest'});
    }
   });
  }
 }
 function scheduleExamples(){
  clearTimeout(exampleTimer);exampleTimer=null;
  if(history.length||pending||document.hidden||reducedMotion.matches||!examples.length)return;
  exampleTimer=setTimeout(()=>{
   if(document.activeElement?.closest('#chat-form,#try-example')||$('chat-input').value){scheduleExamples();return;}
   const text=$('example-text');text.classList.add('example-changing');
   exampleTimer=setTimeout(()=>{exampleIndex=(exampleIndex+1)%examples.length;text.textContent=examples[exampleIndex];$('try-example').setAttribute('aria-label','Use example: '+examples[exampleIndex]);text.classList.remove('example-changing');scheduleExamples();},220);
  },4800);
 }
 async function loadRegisteredData(){
  try{
   const response=await fetch('/api/catalog');if(!response.ok)throw new Error('catalog');const data=await response.json();
   registered={vehicles:data.vehicles||[],part_types:data.part_types||[],part_aliases:data.part_aliases||[]};catalogLoaded=true;window.dispatchEvent(new CustomEvent('counterpilot:catalog',{detail:data}));
   const vehicle=registered.vehicles.find(v=>v.featured)||registered.vehicles[0],other=registered.vehicles.find(v=>v.id!==vehicle?.id)||vehicle;
   if(vehicle){examples=[`Oil filter for a ${vehicle.year} ${vehicle.make} ${vehicle.model}`,`Front brake pads for a ${other.year} ${other.make} ${other.model}`,`Wipers for a ${vehicle.year} ${vehicle.make} ${vehicle.model}`];$('example-text').textContent=examples[0];$('try-example').setAttribute('aria-label','Use example: '+examples[0]);}
   if(openCombo)showCombo(openCombo);scheduleExamples();
  }catch{$('suggestions-status').textContent='Suggestions are unavailable. You can still type any details.';}
 }
 function syncControls(){for(const button of document.querySelectorAll('.chat-follow-up button,.lookup-recovery button'))button.disabled=busy||!!pending||button.closest('.chat-message').classList.contains('previous-result');syncComparison();}
 function setBusy(value){busy=value;window.CounterPilotAssist?.setBusy(value||!!pending);window.CounterPilotUI?.setBusy(value||!!pending);$('edit-failed').disabled=value;$('resume-chat').disabled=value;$('chat-send').disabled=value||!!pending;$('chat-input').disabled=value||!!pending;$('retry').disabled=value;for(const f of fields)$('chat-'+f).disabled=value||!!pending;for(const toggle of document.querySelectorAll('.combo-toggle'))toggle.disabled=value||!!pending;$('apply-details').disabled=value||!!pending||!Object.keys(readEdits()).length;$('typing').hidden=!value;$('chat-messages').setAttribute('aria-busy',String(value));syncControls();}
 function showDetails(){
  const known=Object.values(details).filter(v=>v!=null&&v!=='').length;
  const active=known>0;
  $('details-empty').hidden=active;$('apply-details').hidden=!active;
  const positioned=/brake|rotor|disc|disk|pad|shoe|caliper|shock|strut|control arm|tie rod|axle|hub|bearing|wiper/i.test(details.part||'');
  for(const f of fields){const node=$('chat-'+f),next=fieldText(f,details[f]);if(node.value!==next){node.value=next;node.classList.remove('changed');void node.offsetWidth;node.classList.add('changed');}
   const relevant=['engine','trim','drivetrain','hybrid'].includes(f)?!!details.model||details[f]!=null||lastResult?.question?.field===f:f==='position'?positioned:f==='side'?!!details.side||lastResult?.question?.field==='side':f==='symptoms'?!!details.symptoms:active;
   node.closest('label').hidden=!relevant;
   const source=lastResult?.state?.sources?.[f];node.title=source?'Source: '+source:'Unknown';
  }
  const state=lastResult?.state;
  $('vehicle-source').textContent=state?.vin?`VIN ${state.vin} \u00b7 ${state.confirmed?'identity confirmed':'identity unconfirmed'}`:state?.decoded?'VIN detached from edited vehicle; original decode retained.':'';
  $('vehicle-source').hidden=!$('vehicle-source').textContent;$('details-toggle').hidden=!active;$('details-count').textContent=String(known);
  if(!active)setDetailsOpen(false);else if(lastKnownCount===0&&!panelDismissed&&!narrowPanel.matches)setDetailsOpen(true);
  lastKnownCount=known;updateLayout();
  setBusy(busy);
 }
 function retireResults(){
  window.CounterPilotAssist?.invalidate();
  clearComparison();
  for(const snapshot of snapshots)snapshot.previous=true;
  for(const node of document.querySelectorAll('.chat-message[data-snapshot]')){
   node.classList.add('previous-result');const marker=node.querySelector('.result-age');if(marker)marker.hidden=!node.classList.contains('has-results');
  }
  syncControls();
 }
 function renderProgress(lookup,host){
  const value=lookup.detail_progress;
  const block=el('div',undefined,'detail-progress');
  if(value&&Number.isInteger(value.confirmed)&&value.confirmed>=0&&value.confirmed<=6&&value.total===6){
   block.append(el('strong',`Vehicle details confirmed: ${value.confirmed} of 6`));
   const meter=el('progress');meter.max=6;meter.value=value.confirmed;meter.setAttribute('aria-label',`Vehicle details confirmed: ${value.confirmed} of 6`);block.append(meter);
   if(value.unconfirmed_fields?.length)block.append(el('p','Unconfirmed: '+value.unconfirmed_fields.join(', ')+'.','unconfirmed-details'));
  }else block.append(el('p','Confirmed-detail count will update with your next lookup.','hint'));
  const scoredFields=[...(value?.confirmed_fields||[]),...(value?.unconfirmed_fields||[])];
  const otherUnknown=(lookup.unconfirmed_fields||[]).filter(field=>!scoredFields.includes(field));
  if(otherUnknown.length)block.append(el('p','Other unconfirmed options: '+otherUnknown.join(', ')+'.','unconfirmed-details'));
  block.append(el('p','Detail completeness, not fitment probability. Even 6 of 6 does not establish compatibility or availability.','progress-meaning'));
  host.append(block);
 }
 function renderSnapshot(snapshot,node){
  const result=snapshot.result,lookup=result.lookup;
  node.dataset.snapshot=String(snapshot.messageIndex);node.classList.toggle('previous-result',!!snapshot.previous);
  const age=el('p','Previous result. For the details supplied at that time.','result-age');age.hidden=!snapshot.previous||!lookup.candidates?.length;node.append(age);
  if(lookup.candidates?.length){
   node.classList.add('has-results');
   const host=el('section',undefined,'inline-results');host.setAttribute('aria-label','Retrieved part records');host.append(el('div',`${lookup.candidates.length} catalog ${lookup.candidates.length===1?'application':'applications'} · review the configuration`,'results-heading'));
   for(const [index,part] of lookup.candidates.entries()){
    const card=el('article',undefined,'candidate');
    card.append(productPhoto(part),el('span',part.display_label,'badge'),el('h3',part.name),el('p',part.part_number,'part-number'),el('p',priceText(part),'part-price'),el('p','Brand: '+part.brand,'candidate-brand'));
    const profile=(lookup.applications||[]).find(v=>v.id===part.vehicle_id)||lookup.vehicle;
    if(profile)card.append(el('p',profileText(profile),'candidate-vehicle'));
    if(part.price)card.append(el('p',part.data_status==='sample'?'Sample price only · excludes tax and shipping · not an offer to sell.':'Informational price · confirm current price, tax and shipping with the seller.','price-note'));
    if(part.verification_date)card.append(el('p','Verified: '+part.verification_date,'hint'));
    const evidence=el('details',undefined,'part-evidence');evidence.append(el('summary','Source and restrictions'));
    for(const source of part.evidence||[])evidence.append(el('p',source.statement),el('p','Source: '+source.source,'hint'));
    for(const restriction of part.restrictions||[])evidence.append(el('p',restriction,'hint'));
    const tools=el('div',undefined,'record-actions');if(window.CounterPilotUI)tools.append(window.CounterPilotUI.copyButton(part.part_number));card.append(evidence,tools);if(window.CounterPilotAssist)tools.append(window.CounterPilotAssist.explainButton(part,snapshot,card));
    if(profile&&window.CounterPilotGarage)tools.prepend(window.CounterPilotGarage.saveButton(profile,part));
    if(lookup.candidates.length>1){
     const label=el('label',undefined,'compare-choice'),input=el('input');input.type='checkbox';input.setAttribute('aria-label','Compare '+part.name+' '+part.part_number);const key=`${snapshot.messageIndex}:${index}`;
     input.onchange=()=>{if(input.checked&&compared.size<3)compared.set(key,{part,profile});else{compared.delete(key);input.checked=false;}syncComparison();};label.append(input,document.createTextNode('Compare'));card.append(label);
    }
    host.append(card);
   }
   if(lookup.candidates.length>1){const tools=el('div',undefined,'compare-toolbar'),status=el('p','Select 2 or 3 records to compare.','compare-status'),button=el('button','Compare selected','compare-open');status.setAttribute('role','status');button.type='button';button.disabled=true;button.onclick=openComparison;tools.append(status,button);host.append(tools);}
   renderProgress(lookup,host);node.append(host);
  }
  if(lookup.status==='outside_coverage'){
   const recovery=el('section',undefined,'lookup-recovery');recovery.append(el('span','CATALOG COVERAGE','recovery-label'),el('h3','No application loaded'),el('p','Your details are kept. Edit the request or explore a configuration in the demo catalog.'));
   const browse=el('button','Browse demo vehicles');browse.type='button';browse.onclick=()=>window.CounterPilotUI?.openVehicles();
   const edit=el('button','Edit vehicle details');edit.type='button';edit.onclick=()=>setDetailsOpen(true,true);recovery.append(browse,edit);node.append(recovery);
  }
  const q=result.question;
  if(q){
   const follow=el('div',undefined,'chat-follow-up');
   if(lookup.candidates?.length||result.reply!==q.label)follow.append(el('p',q.label,'chat-question'));
   const choices=el('div',undefined,'chat-options');
   for(const value of q.options||[]){const button=el('button',value);button.type='button';button.onclick=()=>sendText(value);choices.append(button);}
   if(q.optional){const skip=el('button',"I don't know / skip");skip.type='button';skip.className='skip-detail';skip.onclick=()=>sendText("I don't know the "+q.field);choices.append(skip);}
   follow.append(choices);node.append(follow);
  }
  syncControls();
 }
 function snapshotOf(result,messageIndex){return {messageIndex,previous:false,result:{reply:result.reply,details:result.details,lookup:result.lookup,question:result.question,session_id:result.session_id,revision:result.revision}};}
 async function deliver(){
  if(busy||!pending)return;
  const token=++version;controller=new AbortController();const request=controller;
  let reveal=null;
  setBusy(true);$('chat-error').hidden=true;$('typing-text').textContent='Checking the details';scroll();
  const timeout=setTimeout(()=>request.abort(),35000);const slow=setTimeout(()=>{if(token===version)$('typing-text').textContent='Still checking. Your request is safely queued.';},6500);
  try{
   const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pending.payload),signal:request.signal});
   if(!response.ok){const error=new Error('unavailable');error.status=response.status;throw error;}
   const data=await response.json();if(token!==version)return;
   if(!data.details||typeof data.reply!=='string'||!Array.isArray(data.lookup?.candidates))throw new Error('invalid');
   retireResults();document.querySelector('.pending-message')?.classList.remove('pending-message');
   history.push({role:'user',content:pending.text},{role:'assistant',content:data.reply});
   details=data.details;lastResult=data;pending=null;
   const node=bubble('assistant',data.reply),snapshot=snapshotOf(data,history.length-1);snapshots.push(snapshot);renderSnapshot(snapshot,node);showDetails();save();
   if(data.lookup.candidates.length)showHint('parts','Your part number is in the card. Open Source and restrictions for the evidence.');
   else if(Object.values(details).some(v=>v!=null&&v!==''))showHint('details','Details fill in as you chat. Open Details to edit or choose a registered value.');
   reveal=node.querySelector('.inline-results')||node;
  }catch(error){
   if(token!==version)return;
   const expired=error.status===409;
   $('chat-error-text').textContent=expired?'This chat is no longer synchronized with the server. Continue in a fresh session with your current lookup details, or edit your message.':error.name==='AbortError'?'The request took too long. Your message and details are kept. Retry, or edit the message.':!navigator.onLine?'You are offline. Your message and details are kept. Reconnect, then retry.':error.status===422?'Check your lookup details and message, then try again. Your current information is kept.':"We couldn't complete that request. Your message and details are kept. Retry shortly, or edit your message.";
   $('resume-chat').hidden=!expired;$('retry').hidden=expired;$('edit-failed').hidden=false;$('edit-failed').textContent=pending?.payload.edits?'Review changes':'Edit message';
   $('chat-error').hidden=false;save();
  }finally{
   clearTimeout(timeout);clearTimeout(slow);if(token===version){controller=null;setBusy(false);if(reveal)scroll(reveal);else scroll();if(!pending)$('chat-input').focus({preventScroll:true});}
  }
 }
 function begin(text,extra){if(busy||pending)return;const starting=history.length===0;closeCombo();hideHint();pending={text,payload:{message:'',history:context(),details,session_id:lastResult?.session_id??null,revision:lastResult?.revision??0,request_id:crypto.randomUUID().replaceAll('-',''),...extra}};updateLayout();if(starting)startCar();bubble('user',text).classList.add('pending-message');$('chat-input').value='';resizeComposer();save();deliver();}
 function sendText(text){text=text.trim();if(!text||text.length>2000)return;begin(text,{message:text});}
 window.CounterPilotChat={current:()=>lastResult,closeDetails:()=>setDetailsOpen(false),sendVIN(vin){if(busy||pending)return false;sendText('VIN '+vin);return true;}};
 $('chat-form').onsubmit=event=>{event.preventDefault();sendText($('chat-input').value);};
 $('chat-input').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!busy&&!pending)$('chat-form').requestSubmit();}};
 function resizeComposer(){const input=$('chat-input');input.style.height='auto';input.style.height=Math.min(140,Math.max(44,input.scrollHeight))+'px';$('character-count').hidden=input.value.length<1800;$('character-count').textContent=input.value.length+' / 2000';}
 $('chat-input').oninput=()=>{resizeComposer();save();};
 $('retry').onclick=deliver;
 $('edit-failed').onclick=()=>{if(busy||!pending)return;const text=pending.payload.message,edits=pending.payload.edits;document.querySelector('.pending-message')?.remove();pending=null;$('chat-error').hidden=true;updateLayout();if(edits){showDetails();for(const [field,value] of Object.entries(edits))if(fields.includes(field))$('chat-'+field).value=fieldText(field,value);setBusy(false);setDetailsOpen(true,true);window.CounterPilotUI?.announce('Review your unapplied changes, then update the lookup.');}else{$('chat-input').value=text;setBusy(false);resizeComposer();$('chat-input').focus({preventScroll:true});}save();};
 $('resume-chat').onclick=()=>{if(busy||!pending)return;pending.payload={...pending.payload,session_id:null,revision:0,request_id:crypto.randomUUID().replaceAll('-',''),details,history:[...context(),...(lastResult?.question?[{role:'assistant',content:lastResult.question.label}]:[])].slice(-20)};save();deliver();};
 window.addEventListener('counterpilot:use-vehicle',event=>{
  if(busy||pending){event.preventDefault();window.CounterPilotUI?.announce('Finish or edit the pending request before changing vehicles.');return;}
  const vehicle=registered.vehicles.find(v=>v.id===event.detail?.id)||event.detail;if(!vehicle||typeof vehicle.id!=='string'||!/^[A-Za-z0-9._-]{1,80}$/.test(vehicle.id)||!Number.isInteger(vehicle.year)||typeof vehicle.make!=='string'||typeof vehicle.model!=='string'){event.preventDefault();window.CounterPilotUI?.announce('That vehicle could not be loaded. Try the catalog again.');return;}
  setDetailsOpen(false);begin(`Use the ${vehicle.year} ${vehicle.make} ${vehicle.model} demo configuration`,{message:'Demo '+vehicle.id});
 });
 $('chat-details-form').oninput=()=>{const changed=Object.keys(readEdits()).length>0;$('apply-details').disabled=busy||!!pending||!changed;if(changed)retireResults();save();};
 $('chat-details-form').onsubmit=event=>{event.preventDefault();if(!validateEdits())return;const edits=readEdits();if(!Object.keys(edits).length)return;closeCombo();const text='Corrected lookup details: '+Object.entries(edits).map(([f,v])=>f.replaceAll('_',' ')+': '+(v??'unknown')).join(', ')+'.';if(narrowPanel.matches)setDetailsOpen(false);begin(text,{edits});};
 $('new-conversation').onclick=()=>{window.CounterPilotAssist?.reset();clearComparison();$('how-it-works').hidden=true;$('how-toggle').setAttribute('aria-expanded','false');version++;controller?.abort();controller=null;pending=null;history=[];snapshots=[];details={};lastResult=null;busy=false;panelDismissed=false;lastKnownCount=0;clearTimeout(carTimer);$('composer-track').classList.remove('is-driving');hideHint();seenHints.clear();setDetailsOpen(false);$('chat-messages').replaceChildren();$('chat-error').hidden=true;$('chat-input').value='';resizeComposer();showDetails();try{sessionStorage.removeItem(storageKey);}catch{}$('chat-input').focus({preventScroll:true});showHint('start','Start with the part and vehicle. A VIN works too.');};
 $('dismiss-hint').onclick=hideHint;
 $('close-compare').onclick=()=>$('compare-dialog').close();
 $('compare-dialog').addEventListener('click',event=>{if(event.target===$('compare-dialog')){const rect=event.target.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)event.target.close();}});
 $('start-example').onclick=()=>$('try-example').click();
 $('use-vin').onclick=()=>{$('chat-input').value='VIN ';save();$('chat-input').focus({preventScroll:true});};
 $('how-toggle').onclick=()=>{const open=$('how-it-works').hidden;$('how-it-works').hidden=!open;$('how-toggle').setAttribute('aria-expanded',String(open));};
 $('chat-hint').addEventListener('pointerenter',()=>clearTimeout(hintTimer));
 $('chat-hint').addEventListener('focusin',()=>clearTimeout(hintTimer));
 $('chat-hint').addEventListener('pointerleave',()=>{hintTimer=setTimeout(hideHint,8000);});
 $('chat-hint').addEventListener('focusout',()=>{hintTimer=setTimeout(hideHint,8000);});
 $('details-toggle').onclick=()=>setDetailsOpen($('lookup-panel').hidden,true);
 $('close-details').onclick=()=>{setDetailsOpen(false,true);$('details-toggle').focus({preventScroll:true});};
 $('details-dismiss').onclick=()=>{setDetailsOpen(false,true);$('details-toggle').focus({preventScroll:true});};
 $('try-example').onclick=()=>{const text=$('example-text').textContent;$('chat-input').value=text;resizeComposer();save();$('chat-input').focus({preventScroll:true});};
 document.addEventListener('pointerdown',event=>{if(!event.target.closest('.combobox,.combo-list'))closeCombo();});
 document.addEventListener('keydown',event=>{
  if(event.key==='Tab'&&narrowPanel.matches&&!$('lookup-panel').hidden){const focusable=[...$('lookup-panel').querySelectorAll('button:not(:disabled),input:not(:disabled),summary')].filter(node=>node.getClientRects().length&&node.tabIndex>=0);const first=focusable[0],last=focusable.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
  if(event.key==='Escape'&&!$('lookup-panel').hidden){setDetailsOpen(false,true);$('details-toggle').focus({preventScroll:true});}});
 document.addEventListener('visibilitychange',scheduleExamples);reducedMotion.addEventListener('change',scheduleExamples);
 narrowPanel.addEventListener('change',()=>{const hadFocus=$('lookup-panel').contains(document.activeElement);setDetailsOpen(narrowPanel.matches?false:!$('lookup-panel').hidden);if(narrowPanel.matches&&hadFocus)$('details-toggle').focus({preventScroll:true});});
 initializeComboboxes();
 try{
  const stored=JSON.parse(sessionStorage.getItem(storageKey));
  if(stored&&Array.isArray(stored.history)&&stored.history.length<=60&&stored.history.every(m=>['user','assistant'].includes(m.role)&&typeof m.content==='string'&&m.content.length<=2000)){
   history=stored.history.map(({role,content})=>({role,content}));details=stored.details&&typeof stored.details==='object'?Object.fromEntries(fields.map(f=>[f,stored.details[f]??null])):{};
   lastResult=stored.lastResult;
   panelDismissed=!!stored.panelDismissed;
   snapshots=Array.isArray(stored.snapshots)?stored.snapshots.filter(s=>Number.isInteger(s.messageIndex)&&history[s.messageIndex]?.role==='assistant'&&Array.isArray(s.result?.lookup?.candidates)):[];
   if(!snapshots.length&&lastResult?.lookup&&Array.isArray(lastResult.lookup.candidates)){
    const index=history.map(m=>m.role).lastIndexOf('assistant');if(index>=0)snapshots.push(snapshotOf(lastResult,index));
   }
   for(const [index,message] of history.entries()){const node=bubble(message.role,message.content);const snapshot=snapshots.find(s=>s.messageIndex===index);if(snapshot)renderSnapshot(snapshot,node);}
   if(stored.pending?.payload&&typeof stored.pending.text==='string'&&stored.pending.text.length<=2000){pending=stored.pending;bubble('user',pending.text).classList.add('pending-message');$('edit-failed').hidden=false;$('edit-failed').textContent=pending.payload.edits?'Review changes':'Edit message';$('chat-error-text').textContent='Your last message has not completed. Retry to continue.';$('chat-error').hidden=false;}
   $('chat-input').value=typeof stored.draft==='string'?stored.draft.slice(0,2000):'';
  }
 }catch{/* Start clean when saved state is unavailable. */}
 showDetails();resizeComposer();
 if(!history.length&&!pending)hintTimer=setTimeout(()=>showHint('start','Start with the part and vehicle. A VIN works too.'),1800);
 window.addEventListener('counterpilot:reload-catalog',loadRegisteredData);
 loadRegisteredData();
 const latest=document.querySelector('.has-results:not(.previous-result) .inline-results');if(latest&&!pending)scroll(latest);else scroll();
})();
