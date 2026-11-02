const { chromium } = require(process.env.COUNTERPILOT_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const external=[];page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8000'))external.push(r.url());});
 const done=[];
 async function check(name,action){await action();done.push(name);console.log('PASS '+name);}
 await page.goto('http://127.0.0.1:8000');
 await page.locator('#vehicle option').nth(5).waitFor({state:'attached'});
 await check('filter flow and configuration acknowledgment',async()=>{
  await page.getByRole('button',{name:'A simple match'}).click();
  await page.getByText('APPLICATION RECORD FOUND',{exact:true}).waitFor();
  assert.equal(await page.locator('.candidate').count(),0);
  await page.getByRole('button',{name:/These vehicle details match/}).click();
  await page.locator('.candidate').waitFor();
  assert.match(await page.locator('.part-number').innerText(),/DEMO-RAV4-OIL_FILTER/);
 });
 await check('package split excludes candidates until answered',async()=>{
  await page.getByRole('button',{name:/Catch a package split/}).click();
  await page.getByText('Which brake package is fitted?',{exact:false}).waitFor();
  assert.equal(await page.locator('.candidate').count(),0);
  await page.getByRole('button',{name:'heavy-duty',exact:true}).click();
  await page.getByRole('button',{name:/These vehicle details match/}).click();
  await page.locator('.candidate').waitFor();
  assert.match(await page.locator('.part-number').innerText(),/HEAVY-DUTY/);
 });
 await check('front/rear clarification followed by front match',async()=>{
  await page.getByRole('button',{name:/Ask front or rear/}).click();
  await page.getByRole('button',{name:'front',exact:true}).click();
  await page.getByRole('button',{name:/These vehicle details match/}).click();
  await page.locator('.candidate').waitFor();
  assert.match(await page.locator('.part-number').innerText(),/TIGUAN.*FRONT/);
 });
 await check('changed text clears stale criteria and candidates',async()=>{
  await page.locator('#request').fill('alternator for a 2021 Ford F-150');
  assert.equal(await page.locator('#brake_package').inputValue(),'');
  assert.equal(await page.locator('.candidate').count(),0);
  await page.locator('#submit').click();
  await page.getByText('OUTSIDE DEMO COVERAGE',{exact:true}).waitFor();
 });
 await check('missing vehicle then manual correction',async()=>{
  await page.locator('#request').fill('oil filter');
  await page.locator('#submit').click();
  await page.getByText('What model year?',{exact:true}).waitFor();
  await page.locator('#vehicle').selectOption('CRV-01');
  await page.locator('#submit').click();
  await page.getByRole('button',{name:/These vehicle details match/}).click();
  await page.locator('.candidate').waitFor();
  assert.match(await page.locator('.part-number').innerText(),/DEMO-CRV/);
 });
 await check('Meta failure remains recoverable in manual mode',async()=>{
  await page.locator('#provider').selectOption('meta');
  await page.locator('#submit').click();
  await page.getByText('LOOKUP UNAVAILABLE',{exact:true}).waitFor();
  await page.locator('#provider').selectOption('manual');
  await page.locator('#vehicle').selectOption('SIL1500-01');
  await page.locator('#category').selectOption('cabin_filter');
  await page.locator('#submit').click();
  await page.getByRole('button',{name:/These vehicle details match/}).click();
  await page.locator('.candidate').waitFor();
  assert.match(await page.locator('.part-number').innerText(),/SIL1500.*CABIN/);
 });
 await check('VIN failure leaves manual input available',async()=>{
  await page.locator('details.vin summary').click();
  await page.locator('#vin').fill('invalid');
  await page.locator('#vin-submit').click();
  await page.getByText('VIN could not be decoded. Enter vehicle details manually.',{exact:true}).waitFor();
  assert.equal(await page.locator('#submit').isEnabled(),true);
 });
 await check('VIN requires explicit confirmation before field copy (simulated response)',async()=>{
  await page.route('**/api/vin',route=>route.fulfill({json:{vehicle:{model_year:'2019',make:'Toyota',model:'RAV4',engine:{displacement_l:'2.5'}},requires_confirmation:true,message:'Confirm these identity details.'}}));
  await page.locator('#vin').fill('1HGCM82633A004352');
  await page.locator('#vin-submit').click();
  await page.getByRole('button',{name:'Confirm identity & use these fields'}).waitFor();
  assert.equal(await page.locator('#make').inputValue(),'Chevrolet');
  await page.getByRole('button',{name:'Confirm identity & use these fields'}).click();
  assert.equal(await page.locator('#make').inputValue(),'Toyota');
 });
 await page.locator('#provider').selectOption('mock');
 await page.getByRole('button',{name:/Catch a package split/}).click();
 await page.getByText('Which brake package is fitted?',{exact:false}).waitFor();
 await page.screenshot({path:'artifacts/desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await check('mobile layout has no horizontal overflow',async()=>{
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:'artifacts/mobile.png',fullPage:true});
 });
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 console.log('PASS no browser exceptions or external asset requests');
 fs.writeFileSync('artifacts/browser-results.json',JSON.stringify({passed:done,errors,external},null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});

