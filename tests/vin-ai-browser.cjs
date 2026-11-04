const {chromium}=require(process.env.COUNTERPILOT_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.COUNTERPILOT_CHAT_URL||'http://127.0.0.1:8017';
const fixture='artifacts/vin-ai/clear.png';
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});const passed=[],errors=[];
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
  async function check(name,fn){await fn();passed.push(name);console.log('PASS '+name);}
  const seeded=await(await page.request.post(base+'/api/chat',{data:{edits:{year:2019,make:'Toyota',model:'RAV4',engine:'2.5L',part:'oil filter'}}})).json();
  let photoCalls=0,chatCalls=[];let photoResult={status:'readable',vin:'1HGCM82633A004352',message:'Review every character.',requires_confirmation:true};
  await page.route('**/api/vin-photo',async route=>{photoCalls++;await route.fulfill({json:photoResult});});
  await page.route('**/api/chat',async route=>{const payload=route.request().postDataJSON();chatCalls.push(payload);await route.fulfill({json:payload.message?.startsWith('VIN ')?{...seeded,lookup:{candidates:[],status:'needs_clarification'},reply:'NHTSA decoded a proposed vehicle. Confirm these details.',question:{field:'vin_confirmation',label:'Are these details correct?',options:['Yes','No']}}:seeded});});
  await page.goto(base);
  await check('scan action is beside prominent chat, keyboard modal restores focus',async()=>{
   const composer=await page.locator('.composer').boundingBox();assert.ok(composer.height>=90);
   await page.locator('#scan-vin').click();assert.equal(await page.locator('#vin-photo-dialog').isVisible(),true);
   await page.keyboard.press('Escape');assert.equal(await page.locator('#scan-vin').evaluate(el=>el===document.activeElement),true);
  });
  await check('selection previews locally; reading and decoding require separate explicit actions',async()=>{
   await page.locator('#scan-vin').click();await page.locator('#vin-file').setInputFiles(fixture);
   assert.equal(await page.locator('#vin-preview').isVisible(),true);assert.equal(photoCalls,0);assert.equal(chatCalls.length,0);
   await page.locator('#vin-read').click();await page.locator('#vin-review').waitFor({state:'visible'});
   assert.equal(await page.locator('#vin-review').inputValue(),'1HGCM82633A004352');assert.equal(photoCalls,1);assert.equal(chatCalls.length,0);
   assert.equal((await page.evaluate(()=>JSON.stringify(sessionStorage))).includes('data:image'),false);
   await page.locator('#vin-review').fill('1IGCM82633A004352');await page.locator('#vin-confirm').click();assert.equal(chatCalls.length,0);
   await page.locator('#vin-review').fill('1HGCM82633A004352');await page.locator('#vin-confirm').click();await page.locator('#chat-send:not([disabled])').waitFor();
   assert.equal(chatCalls[0].message,'VIN 1HGCM82633A004352');assert.equal(await page.locator('#vin-photo-dialog').isVisible(),false);
   assert.equal(await page.locator('#vin-preview').getAttribute('src'),null);assert.equal(await page.locator('#scan-vin').isVisible(),true);
  });
  await check('unreadable and multiple results never insert a guessed VIN',async()=>{
   for(const status of ['unclear','multiple','not_found']){photoResult={status,vin:null,message:'Retake or type the VIN.'};await page.locator('#scan-vin').click();await page.locator('#vin-file').setInputFiles(fixture);await page.locator('#vin-read').click();await page.locator('#vin-review').waitFor({state:'visible'});assert.equal(await page.locator('#vin-review').inputValue(),'');assert.equal(await page.locator('#vin-confirm').isDisabled(),true);await page.keyboard.press('Escape');}
  });
  await check('invalid file is recoverable without model call',async()=>{
   const before=photoCalls;await page.locator('#scan-vin').click();await page.locator('#vin-file').setInputFiles({name:'bad.svg',mimeType:'image/svg+xml',buffer:Buffer.from('<svg/>')});assert.match(await page.locator('#vin-photo-status').innerText(),/Choose a JPEG/);assert.equal(photoCalls,before);await page.keyboard.press('Escape');
  });
  await check('late scan response after closing cannot revive photo or VIN',async()=>{
   await page.unroute('**/api/vin-photo');await page.route('**/api/vin-photo',async route=>{await new Promise(r=>setTimeout(r,700));try{await route.fulfill({json:{status:'readable',vin:'1HGCM82633A004352',message:'Late'}});}catch{}});
   await page.locator('#scan-vin').click();await page.locator('#vin-file').setInputFiles(fixture);await page.locator('#vin-read').click();await page.keyboard.press('Escape');await page.waitForTimeout(900);await page.locator('#scan-vin').click();assert.equal(await page.locator('#vin-review').inputValue(),'');assert.equal(await page.locator('#vin-preview').getAttribute('src'),null);await page.keyboard.press('Escape');
  });
  await page.locator('#new-conversation').click();await page.locator('#chat-input').fill('Oil filter for my RAV4');await page.locator('#chat-send').click();await page.locator('#chat-send:not([disabled])').waitFor();
  let explanationCalls=0;await page.route('**/api/explain',async route=>{explanationCalls++;await route.fulfill({json:{mode:'ai',label:'AI-guided evidence summary',disclosure:'Demo part — simulated application. Not real-world fitment.',focus:[{field:'part',value:'oil filter',source:'customer'}],other_details:[],record:{name:'Oil filter',part_number:'FL-00131',brand:'CounterPilot Demo',source:'generated_demo',fitment_notes:'<img src=x onerror=alert(1)> Literal catalog text.'},unknown_fields:['trim','drivetrain'],unconfirmed_vehicle_details:['trim','drivetrain'],next_check:'Confirm unresolved details.',identity_note:'VIN is identity only.'}});});
  await check('explanation is explicit, safe-rendered, and reused on repeated clicks',async()=>{
   const button=page.locator('.why-result').last();assert.equal(explanationCalls,0);await button.click();await page.locator('.explanation-label').waitFor();assert.equal(explanationCalls,1);assert.match(await page.locator('.why-summary').last().innerText(),/simulated/);assert.equal(await page.locator('.why-summary img').count(),0);await button.click();await button.click();assert.equal(explanationCalls,1);
   await page.screenshot({path:'artifacts/vin-ai/chat-explanation-desktop.png',fullPage:true});
  });
  await check('corrections mark earlier explanations historical and disable their action',async()=>{
   await page.locator('#chat-input').fill('Actually a different year');await page.locator('#chat-send').click();await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await page.locator('.previous-result .why-result').first().isDisabled(),true);assert.match(await page.locator('.previous-result .why-summary').first().innerText(),/earlier lookup details/);
  });
  await check('mobile chat and scan review fit 320, 390, and 768 pixels',async()=>{
   for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('#scan-vin').click();await page.locator('#vin-file').setInputFiles(fixture);await page.locator('#vin-manual').click();const box=await page.locator('#vin-review').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width);if(width===390)await page.screenshot({path:'artifacts/vin-ai/scan-mobile.png',fullPage:true});await page.keyboard.press('Escape');}
   await page.setViewportSize({width:390,height:844});await page.screenshot({path:'artifacts/vin-ai/chat-mobile.png',fullPage:true});
  });
  await check('new chat resets modal content and retains the chat-first home',async()=>{await page.locator('#new-conversation').click();assert.equal(await page.locator('#vin-preview').getAttribute('src'),null);await page.screenshot({path:'artifacts/vin-ai/home-mobile.png',fullPage:true});await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'artifacts/vin-ai/home-desktop.png',fullPage:true});});
  assert.deepEqual(errors,[]);fs.writeFileSync('artifacts/vin-ai/browser-results.json',JSON.stringify({passed,errors},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
