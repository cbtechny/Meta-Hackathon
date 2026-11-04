const { chromium } = require(process.env.COUNTERPILOT_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.COUNTERPILOT_CHAT_URL || 'http://127.0.0.1:8000';
const live = process.env.COUNTERPILOT_CHAT_LIVE === '1';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  page.setDefaultTimeout(15000);
  const errors=[],external=[],passed=[];
  const active=()=>page.locator('.has-results:not(.previous-result)');
  page.on('pageerror',()=>errors.push('Browser exception'));
  page.on('request',r=>{if(!r.url().startsWith(base+'/'))external.push('External browser request');});
  async function check(name,action){await action();passed.push(name);console.log('PASS '+name);}
  async function send(text){await page.locator('#chat-input').fill(text);const response=page.waitForResponse(r=>r.url()===base+'/api/chat'&&r.request().method()==='POST');await page.locator('#chat-send').click();const result=await response;assert.equal(result.status(),200);await page.locator('#chat-send:not([disabled])').waitFor({timeout:40000});return result.json();}
  async function fresh(){if(await page.locator('#new-conversation').isVisible())await page.locator('#new-conversation').click();assert.equal(await page.locator('.user').count(),0);assert.equal(await page.locator('.candidate').count(),0);}
  async function fixture(details){const response=await page.request.post(base+'/api/chat',{data:{edits:details}});assert.equal(response.status(),200);return response.json();}
  async function routeResult(result){await page.unroute('**/api/chat');await page.route('**/api/chat',route=>route.fulfill({json:result}));}
  await page.goto(base+'/chat');
  await check('one centered chat homepage with no legacy navigation',async()=>{
   await page.getByRole('heading',{name:'CounterPilot',exact:true}).waitFor();
   assert.equal(new URL(page.url()).pathname,'/');
   assert.equal(await page.locator('#chat-year').isVisible(),false);
   assert.equal(await page.locator('nav').count(),0);
   await page.getByText('Chat and find your parts.',{exact:true}).waitFor();
   assert.match(await page.locator('#chat-send').innerText(),/Chat/);
   assert.equal(await page.locator('#new-conversation').isVisible(),false);
   assert.equal(await page.locator('#details-toggle').isVisible(),false);
   assert.equal(await page.locator('#chat-candidates').count(),0);
   await page.screenshot({path:'artifacts/chat-home-empty-desktop.png',fullPage:true});
   await page.setViewportSize({width:390,height:844});await page.screenshot({path:'artifacts/chat-home-empty-mobile.png',fullPage:true});await page.setViewportSize({width:1440,height:1100});
  });
  await check('example CTA fills the composer without sending a request',async()=>{
   let requests=0;const count=r=>{if(r.url()===base+'/api/chat')requests++;};page.on('request',count);
   const text=await page.locator('#example-text').innerText();await page.locator('#try-example').click();assert.equal(await page.locator('#chat-input').inputValue(),text);assert.equal(requests,0);await page.locator('#chat-input').fill('');page.off('request',count);
  });
  await check('light CTAs explain the flow and fill a request without submitting',async()=>{
   let requests=0;const count=r=>{if(r.url()===base+'/api/chat')requests++;};page.on('request',count);
   await page.locator('#how-toggle').click();assert.equal(await page.locator('#how-it-works').isVisible(),true);
   await page.locator('#how-toggle').click();assert.equal(await page.locator('#how-it-works').isVisible(),false);
   await page.locator('#use-vin').click();assert.equal(await page.locator('#chat-input').inputValue(),'VIN ');
   await page.locator('#start-example').click();assert.equal(await page.locator('#chat-input').inputValue(),await page.locator('#example-text').innerText());
   assert.equal(requests,0);await page.locator('#chat-input').fill('');page.off('request',count);
  });
  await check('examples rotate without API calls and respect reduced motion',async()=>{
   let requests=0;const count=r=>{if(r.url()===base+'/api/chat')requests++;};page.on('request',count);
   await page.locator('#search-title').click();const before=await page.locator('#example-text').innerText();await page.waitForTimeout(5300);assert.notEqual(await page.locator('#example-text').innerText(),before);
   await page.emulateMedia({reducedMotion:'reduce'});const frozen=await page.locator('#example-text').innerText();await page.waitForTimeout(5300);assert.equal(await page.locator('#example-text').innerText(),frozen);assert.equal(requests,0);page.off('request',count);
  });
  await check('invalid VIN stays in chat with a clear recoverable correction',async()=>{
   const data=await send('1IGCM82633A004352');
   assert.equal(data.question.field,'vin');assert.match(data.reply,/does not use I, O or Q/);
   assert.equal(await page.locator('.user').count(),1);assert.equal(await page.locator('.candidate').count(),0);
   await fresh();
  });
  if(live){
   await check('real conversation produces immediate inline records and optional questions',async()=>{
    let data=await send('Oil filter');assert.equal(data.question?.field,'year');
    data=await send('2019 Toyota RAV4');assert.equal(data.details.part,'oil filter');assert.equal(data.question.field,'engine');assert.equal(data.question.optional,true);assert.equal(await active().locator('.part-number').innerText(),'FL-00131');
    data=await send('2.5L');assert.equal(data.lookup.candidates[0].part_number,'FL-00131');assert.equal(data.lookup.detail_progress.confirmed,4);
   });
   await check('real vehicle correction removes active candidates',async()=>{
    const data=await send('Actually, the model year is 2018.');assert.equal(data.details.year,2018);assert.equal(data.lookup.status,'outside_coverage');assert.equal(await active().count(),0);
   });
   await fresh();
   await check('real unsupported Camry request stays outside coverage',async()=>{
    const data=await send('Need front pads for a 2018 Camry.');assert.equal(data.details.model,'Camry');assert.equal(data.lookup.status,'outside_coverage');assert.equal(await active().count(),0);
   });
  }
  const complete=await fixture({year:2019,make:'Toyota',model:'RAV4',part:'oil filter',engine:'2.5L'});
  const partial=await fixture({part:'oil filter'});
  await fresh();await page.emulateMedia({reducedMotion:'no-preference'});
  await page.route('**/api/chat',async route=>{await new Promise(resolve=>setTimeout(resolve,1600));await route.fulfill({json:partial});});
  await check('SVG car revs and travels once when chat starts without delaying the request',async()=>{
   await page.locator('#chat-input').fill('Oil filter');await page.locator('#chat-send').click();await page.locator('#typing').waitFor();
   assert.equal(await page.locator('#composer-track').getAttribute('aria-hidden'),'true');
   await page.waitForTimeout(150);const start=await page.locator('.track-car').boundingBox();
   await page.waitForTimeout(650);const moving=await page.locator('.track-car').boundingBox();assert.ok(moving.x>start.x+20);
   await page.screenshot({path:'artifacts/chat-car-moving.png',fullPage:true});
   await page.locator('#chat-send:not([disabled])').waitFor();
   await page.getByText('Details fill in as you chat. Open Details to edit or choose a registered value.',{exact:true}).waitFor();
   assert.equal(await page.locator('#chat-input').evaluate(node=>node===document.activeElement),true);
   await page.locator('#dismiss-hint').focus();await page.keyboard.press('Enter');await page.locator('#chat-hint').waitFor({state:'hidden'});
   assert.equal(await page.locator('#composer-track').evaluate(node=>node.classList.contains('is-driving')),false);
  });
  await page.unroute('**/api/chat');await fresh();await routeResult(partial);
  await check('reduced motion skips car movement and new chat resets hints',async()=>{
   await page.emulateMedia({reducedMotion:'reduce'});await send('Oil filter');
   assert.equal(await page.locator('#composer-track').evaluate(node=>node.classList.contains('is-driving')),false);
   await fresh();await page.getByText('Start with the part and vehicle. A VIN works too.',{exact:true}).waitFor();
   assert.equal(await page.locator('.track-car').evaluate(node=>getComputedStyle(node).animationName),'none');
   await page.screenshot({path:'artifacts/chat-car-home.png',fullPage:true});
   await page.emulateMedia({reducedMotion:'no-preference'});
  });
  await page.unroute('**/api/chat');
  await fresh();let calls=0;
  await page.route('**/api/chat',route=>{calls++;return route.fulfill({status:calls===1?503:200,json:calls===1?{detail:'Simulated outage'}:complete});});
  await check('retry preserves message and shows part number immediately in its reply',async()=>{
   await page.locator('#chat-input').fill('Oil filter for a 2019 RAV4, 2.5L');await page.locator('#chat-send').click();await page.locator('#chat-error').waitFor();assert.equal(await page.locator('.user').count(),1);
   await page.locator('#retry').click();await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await page.locator('.user').count(),1);
   assert.equal(await active().locator('.part-number').innerText(),'FL-00131');assert.equal(await page.getByRole('button',{name:/inspect candidates/}).count(),0);
   assert.match(await active().innerText(),/Demo part [\u2014-] simulated fitment/);assert.match(await active().innerText(),/Brand: CounterPilot Demo/);
   assert.match(await active().locator('.detail-progress').innerText(),/Vehicle details confirmed: 4 of 6/);
   assert.match(await active().locator('.detail-progress').innerText(),/not fitment probability/);
   assert.match(await active().locator('.detail-progress').innerText(),/Other unconfirmed options: hybrid/);
  });
  await check('evidence is collapsed, keyboard accessible and attached to the correct message',async()=>{
   const evidence=active().locator('.part-evidence');assert.equal(await evidence.getAttribute('open'),null);
   await evidence.locator('summary').focus();await page.keyboard.press('Enter');assert.notEqual(await evidence.getAttribute('open'),null);
   assert.match(await evidence.innerText(),/generated_demo/);await evidence.locator('summary').press('Enter');
   assert.equal(await active().locator('.chat-question').innerText(),'Which trim does your vehicle have?');
  });
  await check('reload keeps the card, original score and text-only outgoing history',async()=>{
   await page.reload();assert.equal(await active().locator('.part-number').innerText(),'FL-00131');
   const stored=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('counterpilot-chat-v3')));
   assert.equal(stored.snapshots.length,1);assert.deepEqual(Object.keys(stored.history[1]).sort(),['content','role']);
   assert.match(await active().locator('.detail-progress').innerText(),/4 of 6/);
  });
  await check('existing cached conversations migrate without invented progress',async()=>{
   await page.evaluate(()=>{const stored=JSON.parse(sessionStorage.getItem('counterpilot-chat-v3'));delete stored.snapshots;delete stored.lastResult.lookup.detail_progress;sessionStorage.setItem('counterpilot-chat-v3',JSON.stringify(stored));});
   await page.reload();assert.equal(await active().locator('.part-number').innerText(),'FL-00131');
   assert.match(await active().locator('.detail-progress').innerText(),/update with your next lookup/);
  });
  const follow={field:'drivetrain',label:'What drivetrain does your vehicle have?',options:[],optional:true};
  const skipped={...complete,question:follow,lookup:{...complete.lookup,questions:[follow]}};
  await routeResult(skipped);
  await check('skip sends one follow-up answer and prior controls become inactive',async()=>{
   const response=page.waitForResponse(r=>r.url()===base+'/api/chat');await active().getByRole('button',{name:"I don't know / skip"}).click();const sent=(await response).request().postDataJSON();
   assert.equal(sent.message,"I don't know the trim");assert.ok(sent.history.every(m=>Object.keys(m).sort().join(',')==='content,role'));
   await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await active().count(),1);assert.equal(await page.locator('.previous-result .candidate').count(),1);
   assert.equal(await page.locator('.previous-result .chat-follow-up button').isDisabled(),true);
   assert.equal(await active().locator('.chat-question').innerText(),follow.label);
  });
  await page.unroute('**/api/chat');
  await check('incompatible correction retires prior cards and reload preserves snapshots',async()=>{
   await page.locator('#chat-year').fill('2018');const update=page.waitForResponse(r=>r.url()===base+'/api/chat');await page.locator('#apply-details').click();await update;await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await active().count(),0);
   assert.equal(await page.locator('.previous-result .candidate').count(),2);await page.reload();assert.equal(await page.locator('.previous-result .candidate').count(),2);
   assert.equal(await page.locator('#chat-year').inputValue(),'2018');assert.equal(await page.locator('#chat-part').inputValue(),'oil filter');
   assert.equal(await page.locator('.previous-result .result-age:visible').count(),2);assert.match(await page.locator('.previous-result .detail-progress').last().innerText(),/4 of 6/);
  });
  await fresh();calls=0;
  await page.route('**/api/chat',async route=>{calls++;await new Promise(resolve=>setTimeout(resolve,300));await route.fulfill({json:partial}).catch(()=>{});});
  await check('repeated Enter submits once with accessible loading',async()=>{
   await page.locator('#chat-input').fill('Oil filter');await page.locator('#chat-input').press('Enter');await page.keyboard.press('Enter');await page.locator('#typing').waitFor();assert.equal(await page.locator('#chat-send').isDisabled(),true);await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(calls,1);
  });
  await check('new conversation clears snapshots and ignores in-flight replies',async()=>{
   await page.locator('#chat-input').fill('Something else');await page.locator('#chat-send').click();await fresh();await page.waitForTimeout(500);assert.equal(await page.locator('.assistant').count(),0);await page.reload();assert.equal(await page.locator('.user').count(),0);assert.equal(await page.locator('.candidate').count(),0);
  });
  await routeResult(complete);
  await check('untrusted messages render as text without executable markup',async()=>{
   const text='<img src=x onerror=alert(1)>';await send(text);assert.equal(await page.locator('.user img').count(),0);assert.equal(await page.locator('.user .chat-bubble').innerText(),text);
  });
  const verified={...complete,lookup:{...complete.lookup,candidates:complete.lookup.candidates.map(p=>({...p,part_number:'000123',name:'Test fixture part',brand:'Fixture manufacturer',display_label:'Verified source record',data_status:'verified',verification_date:'2026-11-03',evidence:[{source:'Fixture document, not real fitment evidence',statement:'Browser test fixture only.'}]}))}};
  await fresh();await routeResult(verified);
  await check('verified card preserves number text, source and verification date',async()=>{
   await send('Show a verified fixture');assert.equal(await active().locator('.part-number').innerText(),'000123');assert.match(await active().innerText(),/Verified source record/);assert.match(await active().innerText(),/2026-11-03/);
   await active().locator('.part-evidence summary').click();assert.match(await active().locator('.part-evidence').innerText(),/Fixture document/);
  });
  await check('prices and illustrative photos survive reload without extra alternatives',async()=>{
   await fresh();await routeResult(complete);await send('Oil filter');
   assert.match(await active().locator('.part-price').innerText(),/Demo price · \$12\.95 \/ each/);
   const photo=active().locator('.product-photo img');await photo.evaluate(img=>img.decode());assert.ok(await photo.evaluate(img=>img.naturalWidth>0));
   assert.equal(await active().locator('.compare-choice').count(),0);await page.reload();
   assert.match(await active().locator('.part-price').innerText(),/\$12\.95/);assert.equal(await active().locator('.product-photo img').getAttribute('src'),complete.lookup.candidates[0].image.url);
  });
  await check('missing photos and older records have safe fallbacks',async()=>{
   await fresh();const legacy={...complete,lookup:{...complete.lookup,candidates:complete.lookup.candidates.map(p=>({...p,price:null,image:{url:'/static/parts/missing_test.jpg',alt:'Missing test image'}}))}};
   await routeResult(legacy);await send('Legacy record');await active().locator('.photo-fallback').waitFor();assert.equal(await active().locator('.part-price').innerText(),'Price unavailable');
   assert.equal(await active().locator('.part-number').innerText(),'FL-00131');
  });
  const multiple={...complete,lookup:{...complete.lookup,candidates:Array.from({length:4},(_,i)=>({...complete.lookup.candidates[0],part_id:'FIXTURE-'+i,part_number:'FIXTURE-'+i,name:'Comparison fixture '+(i+1)}))}};
  await check('compare selects at most three active retrieved records with keyboard dismissal',async()=>{
   await fresh();await routeResult(multiple);await send('Compare fixture records');
   const choices=active().locator('.compare-choice input');assert.equal(await choices.count(),4);await choices.nth(0).check();await choices.nth(1).check();await choices.nth(2).check();assert.equal(await choices.nth(3).isDisabled(),true);
   await active().locator('.compare-open').focus();await page.keyboard.press('Enter');await page.locator('#compare-dialog').waitFor();assert.equal(await page.locator('.comparison-item').count(),3);
   assert.match(await page.locator('#compare-items').innerText(),/Demo price/);await page.keyboard.press('Escape');assert.equal(await page.locator('#compare-dialog').isVisible(),false);
   assert.equal(await active().locator('.compare-open').evaluate(node=>node===document.activeElement),true);
   await page.setViewportSize({width:360,height:844});await active().locator('.compare-open').click();assert.equal(await page.locator('#compare-dialog').evaluate(node=>node.scrollWidth<=node.clientWidth),true);
   await page.screenshot({path:'artifacts/chat-compare-mobile.png',fullPage:true});await page.locator('#close-compare').click();await page.setViewportSize({width:1440,height:1100});
   if(await page.locator('#lookup-panel').isHidden())await page.locator('#details-toggle').click();await page.locator('#chat-engine').fill('3.5L');
   assert.equal(await page.locator('.previous-result .compare-choice input:not([disabled])').count(),0);assert.equal(await page.locator('.compare-choice input:checked').count(),0);
   await fresh();assert.equal(await page.locator('#compare-items').innerText(),'');
  });
  await check('equivalent two-liter spellings keep current results and engine suggestions',async()=>{
   const twoLiter=await fixture({year:2007,make:'Suzuki',model:'SX4',part:'oil filter',engine:'2L'});
   await fresh();await routeResult(twoLiter);await send('Oil filter for a 2007 Suzuki SX4 2L');
   if(await page.locator('#lookup-panel').isHidden())await page.locator('#details-toggle').click();
   for(const spelling of ['2','2.0','2L','2.0 L','2 liters','2.0 litres']){
    await page.locator('#chat-engine').fill(spelling);
    await page.getByRole('option',{name:'2.0L',exact:true}).waitFor();
    assert.equal(await page.locator('#apply-details').isDisabled(),true);
    assert.equal(await active().count(),1);
   }
   await page.getByRole('option',{name:'2.0L',exact:true}).click();
   assert.equal(await page.locator('#apply-details').isDisabled(),true);
   assert.equal(await active().count(),1);
   for(const spelling of ['2.0T','2.0L diesel','2.5L']){
    await page.locator('#chat-engine').fill(spelling);
    assert.equal(await page.locator('#apply-details').isEnabled(),true);
   }
   await fresh();
  });
  const editable=await fixture({year:2019,make:'Toyota',model:'RAV4',part:'oil filter',engine:'2.5L'});
  await fresh();await routeResult(editable);await send('Oil filter for a 2019 Toyota RAV4 with a 2.5L engine');
  await check('details appear without stealing focus and autocomplete allows registered corrections',async()=>{
   assert.equal(await page.locator('#lookup-panel').isVisible(),true);assert.equal(await page.locator('#chat-input').evaluate(node=>node===document.activeElement),true);
   assert.equal(await page.locator('#chat-trim').inputValue(),'');
   await page.locator('#chat-year').fill('2023');await page.locator('#chat-year').press('Tab');
   await page.locator('#chat-make').fill('Hon');await page.getByRole('option',{name:'Honda',exact:true}).waitFor();await page.locator('#chat-make').press('ArrowDown');await page.locator('#chat-make').press('Enter');
   assert.equal(await page.locator('#chat-make').inputValue(),'Honda');
   await page.locator('#chat-model').fill('CR');await page.getByRole('option',{name:'CR-V',exact:true}).click();
   await page.locator('#chat-engine').fill('1.5');await page.getByRole('option',{name:'1.5T',exact:true}).click();
   await page.unroute('**/api/chat');const response=page.waitForResponse(r=>r.url()===base+'/api/chat');await page.locator('#apply-details').click();const changed=await response;assert.equal(changed.status(),200);assert.equal(changed.request().postDataJSON().edits.model,'CR-V');assert.equal(changed.request().postDataJSON().message,'');
   await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await page.locator('#chat-engine').inputValue(),'1.5T');assert.equal(await active().locator('.part-number').innerText(),'FL-00161');
  });
  await check('unregistered free text is preserved without autocomplete substitution',async()=>{
   await page.locator('#chat-model').fill('My unregistered model');await page.locator('#chat-model').press('Tab');const response=page.waitForResponse(r=>r.url()===base+'/api/chat');await page.locator('#apply-details').click();const result=await response;assert.equal(result.status(),200);assert.equal((await result.json()).details.model,'My unregistered model');await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await active().count(),0);
  });
  await fresh();await routeResult(complete);await send('Oil filter for a 2019 Toyota RAV4 with a 2.5L engine');
  await page.waitForTimeout(350);await page.screenshot({path:'artifacts/chat-inline-desktop.png',fullPage:true});
  await check('390px and 360px layouts reveal the number inside the chat without overflow',async()=>{
   for(const width of [390,360]){
    await page.setViewportSize({width,height:844});await fresh();await send('Oil filter for a 2019 Toyota RAV4 with a 2.5L engine');
    await page.waitForTimeout(350);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    const bounds=await active().locator('.part-number').evaluate(node=>{const n=node.getBoundingClientRect(),log=document.getElementById('chat-messages').getBoundingClientRect();return {top:n.top,bottom:n.bottom,logTop:log.top,logBottom:log.bottom,viewport:innerHeight};});
    assert.ok(bounds.top>=bounds.logTop&&bounds.bottom<=bounds.logBottom&&bounds.bottom<=bounds.viewport,'Part number must be visible in chat and viewport');
    await page.screenshot({path:`artifacts/chat-inline-mobile-${width}.png`,fullPage:true});
   }
  });
  await check('mobile details stay optional, close with Escape and keep text editable',async()=>{
   assert.equal(await page.locator('#lookup-panel').isVisible(),false);await page.locator('#details-toggle').click();assert.equal(await page.locator('#lookup-panel').isVisible(),true);
   await page.locator('#chat-engine').focus();assert.equal(await page.locator('#chat-engine').getAttribute('role'),'combobox');await page.keyboard.press('Escape');assert.equal(await page.locator('#lookup-panel').isVisible(),true);await page.keyboard.press('Escape');assert.equal(await page.locator('#lookup-panel').isVisible(),false);
  });
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  fs.writeFileSync(live?'artifacts/chat-browser-live-results.json':'artifacts/chat-browser-results.json',JSON.stringify({live,passed,errors,external},null,2)+'\n');
 }finally{await browser.close();}
})().catch(error=>{console.error('FAIL chat browser check: '+error.message);process.exit(1);});
