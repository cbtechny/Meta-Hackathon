const {chromium}=require(process.env.COUNTERPILOT_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.COUNTERPILOT_CHAT_URL||'http://127.0.0.1:8011';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  const errors=[],passed=[];page.on('pageerror',error=>errors.push(error.message));
  const active=()=>page.locator('.chat-message[data-snapshot]:not(.previous-result)').last();
  async function check(name,action){await action();passed.push(name);console.log('PASS '+name);}
  async function fixture(parts){
   const response=await page.request.post(base+'/api/chat',{data:{
    details:{year:2019,make:'Toyota',model:'RAV4',engine:'2.5L',trim:'XLE',drivetrain:'AWD',...parts[0]},parts,
    edits:{part:parts[0].part}}});assert.equal(response.status(),200);return response.json();
  }
  let initial=await fixture([{part:'brakes'},{part:'air filter'},{part:'belt'}]);
  await page.route('**/api/chat',async route=>{
   const body=route.request().postDataJSON();
   if(!body.session_id){await route.fulfill({json:initial});return;}
   const patches={'Brake pads':{part:'brake pads'},'front':{position:'front'},'Serpentine belt':{part:'serpentine belt'}};
   const edits=patches[body.message];
   const response=await page.request.post(base+'/api/chat',{data:edits?{session_id:body.session_id,revision:body.revision,edits}:body});
   await route.fulfill({response});
  });
  async function send(text){await page.locator('#chat-input').fill(text);await page.locator('#chat-send').click();await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await page.locator('#chat-error').isVisible(),false);}
  await page.goto(base);
  await send('Brakes, an air filter and a belt for my 2019 Toyota RAV4');
  await check('three separate requested items show available cards beside unresolved items',async()=>{
   assert.equal(await active().locator('.request-item').count(),3);
   assert.equal(await active().locator('.request-item[data-item="0"] .candidate').count(),0);
   assert.equal(await active().locator('.request-item[data-item="1"] .candidate').count(),1);
   assert.match(await active().locator('.request-item[data-item="2"]').innerText(),/Which belt/);
   assert.match(await active().locator('.garage-prompt').innerText(),/Want to keep this result/);
   assert.equal(await active().locator('.item-jump').count(),3);
   assert.equal(await active().locator('.chat-follow-up').evaluate(node=>{const box=node.getBoundingClientRect(),log=document.getElementById('chat-messages').getBoundingClientRect();return box.top>=log.top&&box.bottom<=log.bottom;}),true);
  });
  await check('clarifying brakes keeps the air-filter card and moves to the belt question',async()=>{
   await active().getByRole('button',{name:'Brake pads',exact:true}).click();await page.locator('#chat-send:not([disabled])').waitFor();
   await active().getByRole('button',{name:'front',exact:true}).click();await page.locator('#chat-send:not([disabled])').waitFor();
   assert.equal(await active().locator('.candidate').count(),2);
   assert.match(await active().locator('.chat-question').innerText(),/Item 3 \(belt\)/);
   await active().getByRole('button',{name:'Serpentine belt',exact:true}).click();await page.locator('#chat-send:not([disabled])').waitFor();
   assert.equal(await active().locator('.request-item').count(),3);
   for(const item of await active().locator('.request-item').all())assert.equal(await item.locator('.candidate').count(),1);
  });
  await check('save-all explicitly saves all displayed records once and survives reload',async()=>{
   await active().getByRole('button',{name:'Save all 3 displayed records',exact:true}).click();
   assert.equal(await page.locator('#garage-count').innerText(),'3');
   assert.equal(await active().getByRole('button',{name:'Saved to Garage',exact:true}).isDisabled(),true);
   assert.equal(await active().locator('.garage-save:not([disabled])').count(),0);
   await page.reload();assert.equal(await active().locator('.request-item').count(),3);assert.equal(await active().locator('.candidate').count(),3);
   await page.locator('#garage-open').click();await page.locator('.garage-record').nth(2).waitFor();assert.equal(await page.locator('.garage-record').count(),3);await page.locator('#garage-close').click();
  });
  await check('adding another part is a composer action without a premature API call',async()=>{
   let requests=0;const listener=request=>{if(request.url()===base+'/api/chat')requests++;};page.on('request',listener);
   await active().getByRole('button',{name:'Add another part',exact:true}).click();
   assert.equal(await page.locator('#chat-input').inputValue(),'Also add ');assert.equal(requests,0);page.off('request',listener);
  });
  await check('individual item editing keeps the complete grouped reply',async()=>{
   await active().getByRole('button',{name:'Edit item 2',exact:true}).click();await page.locator('#chat-send:not([disabled])').waitFor();
   assert.equal(await active().locator('.request-item').count(),3);assert.match(await active().locator('.chat-question').innerText(),/item 2 \(air filter\)/);
   assert.equal(await page.locator('.previous-result .edit-item:not([disabled])').count(),0);
  });
  await check('360px grouped cards and save prompt fit the viewport',async()=>{
   await page.setViewportSize({width:360,height:844});await page.reload();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   for(const card of await active().locator('.candidate').all())assert.equal(await card.evaluate(node=>node.scrollWidth<=node.clientWidth),true);
   const top=node=>{const log=document.getElementById('chat-messages');log.scrollTop+=node.getBoundingClientRect().top-log.getBoundingClientRect().top;};
   await active().evaluate(top);await page.screenshot({path:'artifacts/multi-parts-mobile.png',fullPage:true});
   await page.setViewportSize({width:1440,height:1000});await active().evaluate(top);await page.screenshot({path:'artifacts/multi-parts-desktop.png',fullPage:true});
  });
  await check('unsupported items stay visible while supported cards remain saveable',async()=>{
   await page.locator('#new-conversation').click();initial=await fixture([{part:'oil filter'},{part:'muffler'},{part:'timing belt'}]);await send('Oil filter, muffler and timing belt');
   assert.equal(await active().locator('.request-item').count(),3);assert.equal(await active().locator('.candidate').count(),1);
   assert.match(await active().locator('.request-item[data-item="1"]').innerText(),/No application loaded/);
   assert.match(await active().locator('.request-item[data-item="2"]').innerText(),/No application loaded/);
  });
  await check('save-all at Garage capacity leaves every existing saved record intact',async()=>{
   // The cookie accepts catalog IDs; use actual records from fixture responses.
   const all=await fixture([{part:'brake pads',position:'front'},{part:'brake pads',position:'rear'},{part:'brake rotors',position:'front'},{part:'brake rotors',position:'rear'},{part:'starter'},{part:'alternator'},{part:'radiator'},{part:'thermostat'},{part:'water pump'},{part:'spark plugs'},{part:'ignition coil'},{part:'fuel pump'},{part:'cabin filter'},{part:'wiper blades',position:'front'},{part:'wiper blades',position:'rear'},{part:'belt tensioner'},{part:'serpentine belt'},{part:'oil filter'},{part:'air filter'},{part:'CV axle',position:'front',side:'left'}]);
   const entries=all.lookup.candidates.slice(0,19).map(part=>[part.vehicle_id,part.id]);assert.equal(entries.length,19);
   await context.addCookies([{name:'counterpilot_garage_v1',value:encodeURIComponent(JSON.stringify(entries)),url:base}]);
   await page.locator('#new-conversation').click();initial=all;await send('Several parts');
   // 19 saved records plus at least two unsaved records exceed the 20-record limit.
   const before=(await context.cookies()).find(cookie=>cookie.name==='counterpilot_garage_v1').value;
   // Check the actual remaining budget with two explicit unsaved fixture records.
   const other=await fixture([{part:'tie rod end',position:'front',side:'left'},{part:'tie rod end',position:'front',side:'right'}]);
   await page.locator('#new-conversation').click();initial=other;await send('Left and right tie rods');
   await active().locator('.garage-save-all').click();assert.match(await page.locator('#garage-toast').innerText(),/not enough room/);
   assert.equal((await context.cookies()).find(cookie=>cookie.name==='counterpilot_garage_v1').value,before);
  });
  assert.deepEqual(errors,[]);fs.writeFileSync('artifacts/multi-parts-browser-results.json',JSON.stringify({passed,errors},null,2)+'\n');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
