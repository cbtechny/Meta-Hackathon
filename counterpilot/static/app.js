const $ = id => document.getElementById(id);
const fields = ['year','make','model','category','position','brake_package'];
let catalog = [], searchVersion = 0, vinVersion = 0;
function node(tag, text, cls) { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(cls)e.className=cls; return e; }
function fill(criteria) { for(const f of fields) $(f).value=criteria[f]??''; }
function reset() { vinVersion++;$('vin').value='';$('vin-result').replaceChildren();document.querySelector('details.vin').open=false;$('details').open=false;searchVersion++; fill({}); $('vehicle').value=''; $('request').value=''; $('result-body').replaceChildren(node('p','Ready for a new request.','hint')); }
function readCriteria() { const c={}; for(const f of fields) if($(f).value)c[f]=f==='year'?Number($(f).value):$(f).value.trim(); return c; }
async function api(url,data) {
 const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const payload=await r.json();
 if(!r.ok)throw new Error(typeof payload.detail==='string'?payload.detail:'Check the entered values and try again.');
 return payload;
}
function showCards(result, parent) {
 for(const p of result.candidates){
  const card=node('article',undefined,'candidate');
  card.append(node('span','FICTIONAL APPLICATION','badge'),node('h3',p.name),node('p',p.part_number,'part-number'));
  card.append(node('p',result.vehicle.description));
  for(const evidence of p.evidence){card.append(node('p',evidence.statement),node('p','Source: '+evidence.source,'hint'));}
  const ul=node('ul'); for(const restriction of p.restrictions)ul.append(node('li',restriction));card.append(ul);
  const refs=node('details'); refs.append(node('summary','Cross-reference notes'));
  for(const ref of p.interchanges)refs.append(node('p',ref.number+' — '+ref.status));
  card.append(refs);parent.append(card);
 }
}
function render(result){
 const body=$('result-body');body.replaceChildren();
 const badge=node('span',result.status==='candidates'?'APPLICATION RECORD FOUND':result.status==='needs_clarification'?'ONE MORE DETAIL':'OUTSIDE DEMO COVERAGE','badge '+(result.status==='needs_clarification'?'question':''));
 body.append(badge,node('p',result.message,'message'));
 const values=Object.entries(result.criteria).filter(([,v])=>v!==null).map(([k,v])=>k.replaceAll('_',' ')+': '+v);
 body.append(node('div',values.length?values.join(' · '):'No criteria yet.','criteria'));
 body.append(node('p','Interpretation: '+result.provider+' · Matching: deterministic fictional catalog','hint'));
 for(const q of result.questions){
  const block=node('div',undefined,'question-block');block.append(node('p',q.label));
  if(q.options.length){const choices=node('div',undefined,'choices');for(const option of q.options){const b=node('button',option);b.type='button';b.onclick=()=>{$(q.field).value=option;runSearch();};choices.append(b);}block.append(choices);}
  else { const b=node('button','Enter '+q.field); b.type='button'; b.onclick=()=>{$('details').open=true;$(q.field).focus();};block.append(b);}
  body.append(block);$('details').open=true;
 }
 if(result.candidates.length){
  const confirm=node('div',undefined,'confirm');
  confirm.append(node('strong','Confirm the vehicle configuration'),node('p',result.vehicle.year+' '+result.vehicle.make+' '+result.vehicle.model+' · '+result.vehicle.description));
  confirm.append(node('p','The demo covers this exact configuration. If these details differ, the application is outside the demonstrated coverage.'));
  const b=node('button','These vehicle details match · inspect candidates');b.type='button';
  b.onclick=()=>{confirm.replaceChildren(node('p','Vehicle details acknowledged for this demonstration.'));showCards(result,body);};
  confirm.append(b);body.append(confirm);
 }
}
async function runSearch(){
 const version=++searchVersion; const b=$('submit');b.disabled=true;$('results').setAttribute('aria-busy','true');
 try {
  const data=await api('/api/search',{text:$('request').value,provider:$('provider').value,criteria:readCriteria()});
  if(version!==searchVersion)return;
  fill(data.criteria);render(data);
 }catch(e){if(version===searchVersion)$('result-body').replaceChildren(node('span','LOOKUP UNAVAILABLE','badge error'),node('p',e.message,'error-text'),node('p','Switch to offline or manual interpretation and retry.','hint'));}
 finally{b.disabled=false;$('results').setAttribute('aria-busy','false');}
}
$('search-form').onsubmit=e=>{e.preventDefault();runSearch();};
$('reset').onclick=reset;
$('request').addEventListener('input',()=>{searchVersion++;fill({});$('vehicle').value='';$('result-body').replaceChildren(node('p','Request changed. Run a new application check.','hint'));});
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{reset();$('request').value=b.dataset.prompt;runSearch();});
$('vehicle').onchange=()=>{searchVersion++;$('brake_package').value='';$('result-body').replaceChildren(node('p','Vehicle changed. Run a new application check.','hint'));const v=catalog.find(v=>v.id===$('vehicle').value);for(const f of ['year','make','model'])$(f).value=v?v[f]:'';};
for(const f of fields)$(f).addEventListener('input',()=>{searchVersion++;$('result-body').replaceChildren(node('p','Details changed. Run the application check again.','hint'));});
$('provider').onchange=()=>{searchVersion++;fill({});$('vehicle').value='';if($('provider').value==='manual')$('details').open=true;$('result-body').replaceChildren(node('p','Interpretation changed. Run a new application check.','hint'));};
$('vin').oninput=()=>{vinVersion++;$('vin-result').replaceChildren();};
$('vin-form').onsubmit=async e=>{
 e.preventDefault();const version=++vinVersion;$('vin-submit').disabled=true;$('vin-result').replaceChildren(node('p','Decoding identity…','hint'));
 try {
  const data=await api('/api/vin',{vin:$('vin').value});
  if(version!==vinVersion)return;
  const v=data.vehicle;
  const display=node('div',undefined,'confirm');
  display.append(node('p',[v.model_year,v.make,v.model,v.trim,v.engine?.displacement_l&&v.engine.displacement_l+'L',v.drivetrain].filter(Boolean).join(' · ')));
  display.append(node('p',data.message));
  if(v.api_error_code && v.api_error_code!=='0')display.append(node('p','Decoder reported a warning. Review all fields before use.','error-text'));
  const b=node('button','Confirm identity & use these fields');b.type='button';
  b.onclick=()=>{searchVersion++;for(const f of ['year','make','model'])$(f).value=f==='year'?(v.model_year||''):(v[f]||'');$('vehicle').value='';$('details').open=true;$('result-body').replaceChildren(node('p','VIN identity copied. Review configuration details and run the application check.','hint'));display.replaceChildren(node('p','Identity copied. Brake package and exact configuration still need confirmation.'));};
  display.append(b);$('vin-result').replaceChildren(display);
 }catch(e){if(version===vinVersion)$('vin-result').replaceChildren(node('p',e.message,'error-text'));}
 finally{$('vin-submit').disabled=false;}
};
fetch('/api/catalog').then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{
 catalog=data.vehicles;for(const v of catalog){const o=node('option',v.year+' '+v.make+' '+v.model+' · '+v.description);o.value=v.id;$('vehicle').append(o);}
 $('provider').value=data.default_provider;
 $('provider-note').textContent=data.meta_configured?'Meta key is configured; live integration remains unverified until a successful request.':'Offline mode is ready. Meta requires a local MODEL_API_KEY; no live call has been verified.';
}).catch(()=>{$('provider-note').textContent='Could not load coverage. Refresh the page after starting the local server.';});
