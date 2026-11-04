'use strict';
(() => {
 const name='counterpilot_garage_v1',limit=20,budget=3800;
 const $=id=>document.getElementById(id);
 let version=0,toastTimer,requestController=null,undoItems=null;
 const node=(tag,text,cls)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;if(cls)item.className=cls;return item;};
 function read(){
  try{
   const raw=document.cookie.split(';').map(value=>value.trim()).find(value=>value.startsWith(name+'='))?.slice(name.length+1);
   if(raw===undefined)return {items:[],invalid:false};
   if(new TextEncoder().encode(raw).length>budget)throw new Error('size');
   const items=JSON.parse(decodeURIComponent(raw));
   if(!Array.isArray(items)||items.length>limit||items.some(item=>!Array.isArray(item)||item.length!==2||item.some(value=>typeof value!=='string'||!/^[A-Za-z0-9._-]{1,80}$/.test(value))))throw new Error('format');
   const unique=new Map(items.map(item=>[JSON.stringify(item),item]));return {items:[...unique.values()],invalid:false};
  }catch{return {items:[],invalid:true};}
 }
 function contains(items,vehicle,part){return items.some(item=>item[0]===vehicle&&item[1]===part);}
 function sync(){
  const {items,invalid}=read();$('garage-count').textContent=String(items.length);$('garage-clear').disabled=!invalid&&!items.length;
  document.querySelectorAll('.garage-save').forEach(button=>{const saved=contains(items,button.dataset.vehicle,button.dataset.part);button.textContent=saved?'Saved to garage':'Add to garage';button.disabled=saved;button.setAttribute('aria-label',(saved?'Saved to garage: ':'Add to garage: ')+button.dataset.label);});
  document.querySelectorAll('.garage-save-all').forEach(button=>{const entries=JSON.parse(button.dataset.entries),saved=entries.every(([vehicle,part])=>contains(items,vehicle,part));button.textContent=saved?'Saved to Garage':entries.length===1?'Save this result to Garage':`Save all ${entries.length} displayed records`;button.disabled=saved;});
 }
 function notify(text){
  clearTimeout(toastTimer);$('garage-toast').textContent=text;$('garage-toast').hidden=false;
  if($('garage-dialog').open)$('garage-status').textContent=text;
  toastTimer=setTimeout(()=>$('garage-toast').hidden=true,4500);
 }
 function persist(items){
  const value=encodeURIComponent(JSON.stringify(items));
  if(new TextEncoder().encode(name+'='+value).length>budget){notify('This garage is full. Remove an application to make room.');return false;}
  try{
   document.cookie=items.length?`${name}=${value}; Max-Age=31536000; Path=/; SameSite=Lax${location.protocol==='https:'?'; Secure':''}`:`${name}=; Max-Age=0; Path=/; SameSite=Lax`;
   const stored=read();if(stored.invalid||JSON.stringify(stored.items)!==JSON.stringify(items))throw new Error('blocked');
  }catch{notify('Your browser could not save the garage cookie. Allow cookies for this site and try again.');return false;}
  version++;sync();return true;
 }
 function add(vehicle,part){
  const {items,invalid}=read();
  if(invalid){notify('The saved garage could not be read. Open Garage and clear it to start again.');return;}
  if(contains(items,vehicle,part)){sync();notify('This application is already in your garage.');return;}
  if(items.length>=limit){notify('Your garage has 20 applications. Remove one to save another.');return;}
  if(persist([...items,[vehicle,part]])){undoItems=null;$('garage-undo').hidden=true;notify('Application added to your garage.');if($('garage-dialog').open)load();}
 }
 function remove(vehicle,part){
  const {items}=read();if(persist(items.filter(item=>item[0]!==vehicle||item[1]!==part))){undoItems=items;$('garage-undo').hidden=false;load(true);}
 }
 function price(part){
  const p=part.price;
  if(!p||p.currency!=='USD'||!['each','pair','axle set'].includes(p.unit)||!/^\d{1,6}(\.\d{1,2})?$/.test(String(p.amount))||Number(p.amount)<=0)return null;
  return `${part.data_status==='sample'?'Demo price':'Listed price'} · ${new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(p.amount))} / ${p.unit}`;
 }
 function render(data){
  const host=$('garage-items');host.replaceChildren();
  if(data.invalid_cookie){$('garage-status').textContent='The saved garage could not be read. Clear it to start again.';return;}
  $('garage-status').textContent=data.applications.length?`${data.applications.length} saved application${data.applications.length===1?'':'s'}`:'Your garage is empty. Use Add to garage on a part card to save its vehicle application.';
  if(!data.applications.length){const empty=node('div',undefined,'garage-empty');empty.append(node('span','↗','empty-mark'),node('h3','A home for your next lookup'),node('p','Save a part application and its vehicle configuration. It will be here when you come back.'));host.append(empty);}
  const groups=new Map();
  for(const item of data.applications){
   if(!item.available){
    const row=node('article',undefined,'garage-record garage-unavailable');row.append(node('p','This saved application is no longer in the catalog.'));
    const removeButton=node('button','Remove');removeButton.type='button';removeButton.onclick=()=>remove(item.vehicle_id,item.part_id);row.append(removeButton);host.append(row);continue;
   }
   const {vehicle,part}=item;
   let section=groups.get(vehicle.id);
   if(!section){section=node('section',undefined,'garage-vehicle');section.append(node('h3',`${vehicle.year} ${vehicle.make} ${vehicle.model}`),node('p',vehicle.description,'garage-configuration'));if(window.CounterPilotUI){const reuse=node('button','Use vehicle','garage-use');reuse.type='button';reuse.disabled=window.CounterPilotUI.isBusy();reuse.setAttribute('aria-label','Use saved '+vehicle.year+' '+vehicle.make+' '+vehicle.model);reuse.onclick=()=>window.CounterPilotUI.chooseVehicle(vehicle);section.append(reuse);}groups.set(vehicle.id,section);host.append(section);}
   const row=node('article',undefined,'garage-record');row.append(node('span',part.display_label,'badge'),node('h4',part.name),node('p',part.part_number,'garage-part-number'),node('p','Brand: '+part.brand,'hint'));
   const amount=price(part);if(amount)row.append(node('p',amount,'hint'));
   const evidence=node('details',undefined,'garage-evidence');evidence.append(node('summary','Source and restrictions'));
   for(const source of part.evidence||[])evidence.append(node('p',source.statement),node('p','Source: '+source.source));
   for(const restriction of part.restrictions||[])evidence.append(node('p',restriction));row.append(evidence);
   const removeButton=node('button','Remove');removeButton.type='button';removeButton.setAttribute('aria-label','Remove '+part.name+' '+part.part_number);removeButton.onclick=()=>remove(item.vehicle_id,item.part_id);row.append(removeButton);section.append(row);
  }
 }
 async function load(focusUndo=false){
  requestController?.abort();requestController=new AbortController();const request=requestController;const timeout=setTimeout(()=>request.abort(),12000);
  const token=++version;sync();$('garage-status').textContent='Loading saved applications…';$('garage-items').replaceChildren();
  try{const response=await fetch('/api/garage',{cache:'no-store',signal:request.signal});if(!response.ok)throw new Error('unavailable');const data=await response.json();if(token!==version)return;if(!Array.isArray(data.applications))throw new Error('invalid');render(data);if(focusUndo&&!$('garage-undo').hidden)$('garage-undo').focus();}
  catch{if(token!==version)return;$('garage-status').textContent='Could not load your saved applications. Your garage cookie is kept.';const retry=node('button','Retry garage');retry.type='button';retry.onclick=()=>load();$('garage-items').append(retry);}
  finally{clearTimeout(timeout);}
 }
 window.CounterPilotGarage={saveAllButton(records){
  const entries=[...new Map(records.map(({vehicle,part})=>[JSON.stringify([vehicle.id,part.id]),[vehicle.id,part.id]])).values()];
  const button=node('button',undefined,'garage-save-all');button.type='button';button.dataset.entries=JSON.stringify(entries);
  const saved=entries.every(([vehicle,part])=>contains(read().items,vehicle,part));button.textContent=saved?'Saved to Garage':entries.length===1?'Save this result to Garage':`Save all ${entries.length} displayed records`;button.disabled=saved;
  button.onclick=()=>{
   const {items,invalid}=read();if(invalid){notify('The saved garage could not be read. Open Garage and clear it to start again.');return;}
   const additions=entries.filter(([vehicle,part])=>!contains(items,vehicle,part));
   if(items.length+additions.length>limit){notify('There is not enough room to save every displayed record. Save individual cards or remove an application from Garage.');return;}
   if(persist([...items,...additions])){undoItems=null;$('garage-undo').hidden=true;notify(`${additions.length} application${additions.length===1?'':'s'} added to your garage.`);}
  };
  return button;
 },saveButton(vehicle,part){
  const button=node('button',undefined,'garage-save');button.type='button';button.dataset.vehicle=vehicle.id;button.dataset.part=part.id;button.dataset.label=`${part.name} for ${vehicle.year} ${vehicle.make} ${vehicle.model}`;
  const saved=contains(read().items,vehicle.id,part.id);button.textContent=saved?'Saved to garage':'Add to garage';button.disabled=saved;button.setAttribute('aria-label',(saved?'Saved to garage: ':'Add to garage: ')+button.dataset.label);button.onclick=()=>add(vehicle.id,part.id);return button;
 }};
 $('garage-open').onclick=()=>{$('garage-dialog').showModal();$('garage-close').focus();load();};
 $('garage-close').onclick=()=>$('garage-dialog').close();
 $('garage-dialog').addEventListener('click',event=>{if(event.target!==$('garage-dialog'))return;const rect=event.target.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)event.target.close();});
 $('garage-clear').onclick=()=>{const before=read().items;if(persist([])){undoItems=before.length?before:null;$('garage-undo').hidden=!undoItems;notify('Garage cleared.');load(true);}};
 $('garage-undo').onclick=()=>{if(!undoItems)return;const restore=undoItems;if(persist(restore)){undoItems=null;$('garage-undo').hidden=true;notify('Saved applications restored.');load();$('garage-close').focus();}};
 document.addEventListener('visibilitychange',()=>{if(!document.hidden){sync();if($('garage-dialog').open)load();}});
 sync();
})();
