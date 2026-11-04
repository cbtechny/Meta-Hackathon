'use strict';
(() => {
 const $=id=>document.getElementById(id),dialog=$('vin-photo-dialog');
 let photo=null,preview=null,scanController=null,scanVersion=0,reading=false,opener=null,chatBusy=false;
 let explanationVersion=0;const explanationControllers=new Set();
 const node=(tag,text,cls)=>{const value=document.createElement(tag);if(text!==undefined)value.textContent=text;if(cls)value.className=cls;return value;};
 function status(text){$('vin-photo-status').textContent=text;}
 function sync(){
  $('vin-read').disabled=!photo||reading;for(const id of ['vin-file','vin-camera'])$(id).disabled=reading;
  $('vin-confirm').disabled=reading||chatBusy||!$('vin-review').value.trim();
  $('scan-vin').disabled=chatBusy;
 }
 function cancelRead(){scanVersion++;scanController?.abort();scanController=null;reading=false;}
 function release(){cancelRead();photo=null;if(preview)URL.revokeObjectURL(preview);preview=null;$('vin-preview').removeAttribute('src');$('vin-preview').hidden=true;$('vin-file').value='';$('vin-camera').value='';$('vin-review').value='';$('vin-review').setCustomValidity('');$('vin-review-panel').hidden=true;status('');sync();}
 function open(event){if(chatBusy)return;window.CounterPilotChat?.closeDetails();opener=event.currentTarget;release();dialog.showModal();$('vin-file').focus();}
 $('scan-vin').onclick=open;$('vin-photo-close').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{release();opener?.focus({preventScroll:true});});
 for(const id of ['vin-file','vin-camera'])$(id).onchange=event=>{
  const file=event.target.files?.[0];release();if(!file)return;
  if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>4*1024*1024||!file.size){status('Choose a JPEG, PNG or WebP photo up to 4 MB. Convert HEIC photos first.');return;}
  photo=file;preview=URL.createObjectURL(file);$('vin-preview').src=preview;$('vin-preview').hidden=false;
  status('Photo selected. Choose Read VIN to send it to Meta.');sync();
 };
 $('vin-preview').onerror=()=>{release();status('That image cannot be displayed. Choose another photo.');};
 $('vin-read').onclick=async()=>{
  if(!photo||reading)return;cancelRead();const version=scanVersion,selected=photo;reading=true;sync();
  $('vin-review-panel').hidden=true;$('vin-review').value='';status('Reading the printed VIN…');
  const request=new AbortController();scanController=request;const timer=setTimeout(()=>request.abort(),35000);
  try{
   const image=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('file'));reader.readAsDataURL(selected);});
   if(version!==scanVersion)return;
   const response=await fetch('/api/vin-photo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image}),signal:request.signal});
   const result=await response.json();if(version!==scanVersion||!dialog.open)return;
   if(!response.ok)throw new Error(response.status===422||response.status===413?result.detail:'Photo reading is unavailable. Retry, choose another photo, or type the VIN.');
   status(result.message);$('vin-review').value=result.status==='readable'?(result.vin||''):'';$('vin-review-panel').hidden=false;$('vin-review').focus();
  }catch(error){if(version===scanVersion){status(error.name==='AbortError'?'Reading took too long. Retry or type the VIN.':error.message||'Photo reading failed. Retry or type the VIN.');$('vin-review-panel').hidden=false;}}
  finally{clearTimeout(timer);if(version===scanVersion){scanController=null;reading=false;sync();}}
 };
 $('vin-review').oninput=()=>{$('vin-review').setCustomValidity('');sync();};
 $('vin-manual').onclick=()=>{cancelRead();$('vin-review-panel').hidden=false;status('Type the VIN and check every character before continuing.');sync();$('vin-review').focus();};
 $('vin-review-form').onsubmit=event=>{
  event.preventDefault();if(reading||chatBusy)return;
  const input=$('vin-review'),vin=input.value.replace(/[\s-]+/g,'').toUpperCase();
  input.setCustomValidity(/^[A-HJ-NPR-Z0-9]{17}$/.test(vin)?'':'Enter 17 VIN characters. Letters I, O and Q are not used.');
  if(!input.reportValidity())return;
  if(window.CounterPilotChat?.sendVIN(vin)){dialog.close();}else status('Finish or edit the pending chat request first. Your VIN is kept here.');
 };
 function invalidate(){explanationVersion++;for(const request of explanationControllers)request.abort();explanationControllers.clear();
  for(const el of document.querySelectorAll('.why-summary')){el.replaceChildren(node('p','This explanation belongs to earlier lookup details. Run Why this result? on a current card.'));el.classList.add('historical-explanation');}
 }
 function explainButton(part,snapshot,card){
  const button=node('button','Why this result?','why-result');button.type='button';button.disabled=!!snapshot.previous;
  let cached=null,loading=false;const host=node('section',undefined,'why-summary');host.hidden=true;host.setAttribute('aria-label','Explanation of retrieved record');host.setAttribute('aria-live','polite');card.append(host);
  button.onclick=async()=>{
   if(loading||chatBusy||snapshot.previous||card.closest('.previous-result'))return;
   if(cached){host.hidden=!host.hidden;button.setAttribute('aria-expanded',String(!host.hidden));return;}
   const current=window.CounterPilotChat?.current();
   if(!current?.session_id||!snapshot.result.revision||current.revision!==snapshot.result.revision){host.hidden=false;host.replaceChildren(node('p','Run a fresh lookup to explain a current result.'));return;}
   const version=explanationVersion,request=new AbortController();explanationControllers.add(request);loading=true;button.disabled=true;host.hidden=false;button.setAttribute('aria-expanded','true');host.replaceChildren(node('p','Choosing the relevant catalog evidence…'));
   const timer=setTimeout(()=>request.abort(),35000);
   try{
    const response=await fetch('/api/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:current.session_id,revision:current.revision,part_id:part.id}),signal:request.signal});
    const result=await response.json();if(version!==explanationVersion||!card.isConnected)return;
    if(!response.ok)throw new Error(response.status===409?'This lookup changed. Use a current result.':'Explanation unavailable. Your source evidence remains below.');
    cached=result;host.replaceChildren(node('p',result.label,'explanation-label'),node('p',result.disclosure,'explanation-disclosure'));
    const list=node('ul');for(const fact of result.focus||[])list.append(node('li',`${fact.field}: ${fact.value} · ${fact.source}`));host.append(list);
    if(result.other_details?.length){const rest=node('details');rest.append(node('summary','Other supplied details'));for(const fact of result.other_details)rest.append(node('p',`${fact.field}: ${fact.value} · ${fact.source}`));host.append(rest);}
    if(result.application){const app=result.application;host.append(node('p',`Retrieved catalog application: ${[app.year,app.make,app.model,app.engine,app.trim,app.drivetrain].filter(v=>v!=null&&v!=='').join(' · ')}. Part type: ${result.part_type.replaceAll('_',' ')}.`));}
    const record=result.record;host.append(node('p',`Catalog: ${record.name} · ${record.part_number} · ${record.brand}`));
    host.append(node('p',`Source: ${record.source_reference||record.source||'Not supplied'}${record.verification_date?' · Checked '+record.verification_date:''}`));
    host.append(node('p','Application notes: '+(record.fitment_notes||'Not supplied.')));
    for(const restriction of result.restrictions||[])host.append(node('p',restriction));
    if(result.unknown_fields?.length)host.append(node('p','Unknown: '+result.unknown_fields.join(', ')+'.'));
    if(result.unconfirmed_vehicle_details?.length)host.append(node('p','Vehicle details not confirmed by the customer: '+result.unconfirmed_vehicle_details.join(', ')+'.'));
    host.append(node('p',result.next_check),node('p',result.identity_note,'hint'));
   }catch(error){if(version===explanationVersion)host.replaceChildren(node('p',error.name==='AbortError'?'Explanation took too long. Retry or inspect Source and restrictions.':error.message));}
   finally{clearTimeout(timer);explanationControllers.delete(request);loading=false;button.disabled=chatBusy||!!snapshot.previous||!!card.closest('.previous-result');}
  };
  button.setAttribute('aria-expanded','false');return button;
 }
 window.CounterPilotAssist={explainButton,invalidate,setBusy(value){chatBusy=value;sync();document.querySelectorAll('.why-result').forEach(button=>button.disabled=value||!!button.closest('.previous-result'));},reset(){invalidate();if(dialog.open)dialog.close();else release();}};
})();
