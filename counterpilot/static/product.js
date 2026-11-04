'use strict';
(() => {
 const $=id=>document.getElementById(id);
 let vehicles=[],busy=false;
 function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
 function announce(text){$('app-announcement').textContent='';requestAnimationFrame(()=>$('app-announcement').textContent=text);}
 function choose(vehicle){
  const event=new CustomEvent('counterpilot:use-vehicle',{detail:vehicle,cancelable:true});
  if(window.dispatchEvent(event)){$('vehicles-dialog').close();$('garage-dialog').close();}
 }
 function renderVehicles(){
  const host=$('vehicle-choices');host.replaceChildren();
  if(!vehicles.length){host.append(el('p','Vehicle suggestions are unavailable. You can still describe your vehicle in the chat.','hint'));const retry=el('button','Retry catalog','vehicle-choice');retry.type='button';retry.onclick=()=>{retry.disabled=true;retry.textContent='Loading catalog…';window.dispatchEvent(new Event('counterpilot:reload-catalog'));setTimeout(()=>{if(retry.isConnected){retry.disabled=false;retry.textContent='Retry catalog';}},4000);};host.append(retry);return;}
  for(const vehicle of vehicles){
   const button=el('button',undefined,'vehicle-choice');button.type='button';button.disabled=busy;
   button.append(el('span',String(vehicle.year),'vehicle-year'),el('strong',vehicle.make+' '+vehicle.model),el('span',vehicle.description,'vehicle-spec'),el('span','Use this configuration ↗','vehicle-action'));
   button.onclick=()=>choose(vehicle);host.append(button);
  }
 }
 function openVehicles(){renderVehicles();$('vehicles-dialog').showModal();$('close-vehicles').focus();}
 function copyButton(value){
  const button=el('button','Copy number','copy-number');button.type='button';button.setAttribute('aria-label','Copy part number '+value);
  button.onclick=async()=>{button.disabled=true;try{await navigator.clipboard.writeText(value);button.textContent='Copied';announce('Part number copied.');}catch{button.textContent='Copy unavailable';announce('Clipboard access is unavailable. Select the part number to copy it.');}finally{setTimeout(()=>{button.textContent='Copy number';button.disabled=false;},2200);}};return button;
 }
 function syncConnection(){$('connection-status').hidden=navigator.onLine;}
 window.CounterPilotUI={announce,copyButton,openVehicles,chooseVehicle:choose,isBusy:()=>busy,setBusy(value){busy=value;document.querySelectorAll('.vehicle-choice,.garage-use').forEach(button=>button.disabled=value);}};
 window.addEventListener('counterpilot:catalog',event=>{vehicles=event.detail.vehicles||[];$('catalog-summary').textContent=`${vehicles.length} demo vehicles · ${event.detail.application_count} catalog applications · Source on every record`;if($('vehicles-dialog').open)renderVehicles();});
 $('browse-vehicles').onclick=openVehicles;$('close-vehicles').onclick=()=>$('vehicles-dialog').close();
 $('vehicles-dialog').addEventListener('click',event=>{if(event.target!==event.currentTarget)return;const box=event.target.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)event.target.close();});
 window.addEventListener('online',syncConnection);window.addEventListener('offline',syncConnection);syncConnection();
})();
