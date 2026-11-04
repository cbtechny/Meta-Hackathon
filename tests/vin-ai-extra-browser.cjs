const {chromium}=require(process.env.COUNTERPILOT_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.COUNTERPILOT_CHAT_URL||'http://127.0.0.1:8017';
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true}),passed=[];
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(10000);
  const seeded=await(await page.request.post(base+'/api/chat',{data:{edits:{year:2019,make:'Toyota',model:'RAV4',part:'oil filter'}}})).json();
  await page.route('**/api/chat',route=>route.fulfill({json:seeded}));
  async function check(name,fn){await fn();passed.push(name);console.log('PASS '+name);}
  await page.goto(base);
  await check('older server explains missing upload endpoint and keeps manual VIN entry available',async()=>{
   await page.route('**/api/vin-photo',route=>route.fulfill({status:404,json:{detail:'Not Found'}}));await page.locator('#scan-vin').click();await page.locator('#vin-file').setInputFiles('artifacts/vin-ai/clear.png');await page.locator('#vin-read').click();await page.locator('#vin-photo-status').filter({hasText:/Restart CounterPilot/}).waitFor();assert.equal(await page.locator('#vin-read').isEnabled(),true);await page.locator('#vin-manual').click();await page.locator('#vin-review').fill('1HGCM82633A004352');assert.equal(await page.locator('#vin-confirm').isEnabled(),true);await page.keyboard.press('Escape');await page.unroute('**/api/vin-photo');
  });
  await check('photo network failure is recoverable and retry sends one request',async()=>{
   await page.route('**/api/vin-photo',route=>route.fulfill({status:503,json:{detail:'Service unavailable'}}));await page.locator('#scan-vin').click();await page.locator('#vin-file').setInputFiles('artifacts/vin-ai/clear.png');await page.locator('#vin-read').click();await page.locator('#vin-photo-status').filter({hasText:/unavailable/}).waitFor();assert.equal(await page.locator('#vin-read').isEnabled(),true);
   await page.unroute('**/api/vin-photo');let requests=0;await page.route('**/api/vin-photo',async route=>{requests++;await new Promise(r=>setTimeout(r,300));await route.fulfill({json:{status:'readable',vin:'1HGCM82633A004352',message:'Review'}});});await page.locator('#vin-read').click();assert.equal(await page.locator('#vin-read').isDisabled(),true);await page.locator('#vin-review').waitFor({state:'visible'});assert.equal(requests,1);await page.keyboard.press('Escape');
  });
  await page.locator('#chat-input').fill('Oil filter for a RAV4');await page.locator('#chat-send').click();await page.locator('#chat-send:not([disabled])').waitFor();
  await check('fallback explanation identifies itself and retains catalog evidence',async()=>{
   await page.route('**/api/explain',route=>route.fulfill({json:{mode:'fallback',label:'Catalog summary — AI explanation unavailable',disclosure:'Demo part — simulated application.',focus:[],other_details:[],record:{name:'Oil filter',part_number:'FL-00131',brand:'CounterPilot Demo',source:'generated_demo',fitment_notes:'Simulated fitment'},unknown_fields:['engine'],next_check:'Verify catalog restrictions.',identity_note:'VIN is identity only.'}}));await page.locator('.why-result').last().click();await page.locator('.explanation-label').filter({hasText:/unavailable/}).waitFor();assert.match(await page.locator('.why-summary').last().innerText(),/generated_demo/);
  });
  await page.locator('#new-conversation').click();await page.locator('#chat-input').fill('Oil filter for a RAV4');await page.locator('#chat-send').click();await page.locator('#chat-send:not([disabled])').waitFor();
  await check('stale explanation response cannot replace historical disclosure after correction',async()=>{
   await page.unroute('**/api/explain');await page.route('**/api/explain',async route=>{await new Promise(r=>setTimeout(r,700));try{await route.fulfill({json:{label:'STALE-CONTENT'}});}catch{}});
   await page.locator('.why-result').last().click();await page.locator('#chat-input').fill('Actually a different year');await page.locator('#chat-send').click();await page.locator('#chat-send:not([disabled])').waitFor();await page.waitForTimeout(900);assert.equal((await page.locator('#chat-messages').innerText()).includes('STALE-CONTENT'),false);assert.match(await page.locator('.previous-result .why-summary').innerText(),/earlier lookup/);
  });
  fs.writeFileSync('artifacts/vin-ai/extra-browser-results.json',JSON.stringify({passed},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
