const {chromium}=require(process.env.COUNTERPILOT_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.env.COUNTERPILOT_CHAT_URL||'http://127.0.0.1:8012';
const cookieName='counterpilot_garage_v1';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  const errors=[],passed=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.request.post(base+'/api/chat',{data:{edits:{year:2007,make:'Suzuki',model:'SX4',engine:'2.0L',drivetrain:'AWD',part:'oil filter'}}});
  assert.equal(response.status(),200);const fixture=await response.json();assert.equal(fixture.lookup.candidates[0].part_number,'FL-00251');
  await page.route('**/api/chat',route=>route.fulfill({json:fixture}));
  async function check(name,action){await action();passed.push(name);console.log('PASS '+name);}
  async function send(){await page.locator('#chat-input').fill('Oil filter for my 2007 Suzuki SX4');await page.locator('#chat-send').click();await page.locator('.garage-save').first().waitFor();await page.locator('#chat-send:not([disabled])').waitFor();}
  async function open(){await page.locator('#garage-open').click();await page.locator('#garage-status').filter({hasText:/^(?:\d+ saved application|Your garage is empty|The saved garage could not be read)/}).waitFor();}
  await page.goto(base);
  await check('empty garage opens without an account',async()=>{await open();assert.match(await page.locator('#garage-status').innerText(),/empty/);await page.locator('#garage-close').click();});
  await send();
  await check('save stores compact first-party cookie IDs and changes the button',async()=>{
   await page.locator('.garage-save').first().click();assert.equal(await page.locator('#garage-count').innerText(),'1');assert.equal(await page.locator('.garage-save').first().innerText(),'Saved to garage');assert.equal(await page.locator('.garage-save').first().isDisabled(),true);
   const cookie=(await context.cookies()).find(c=>c.name===cookieName);assert(cookie);assert.equal(cookie.path,'/');assert.equal(cookie.sameSite,'Lax');assert(cookie.expires>Date.now()/1000+300*86400);assert.deepEqual(JSON.parse(decodeURIComponent(cookie.value)),[['SX4-01',fixture.lookup.candidates[0].id]]);assert(!cookie.value.includes('FL-00251%22%2C%22CounterPilot'));
  });
  await check('garage groups the saved application under its vehicle with demo source',async()=>{
   await open();assert.equal(await page.locator('.garage-vehicle h3').innerText(),'2007 Suzuki SX4');assert.match(await page.locator('.garage-configuration').innerText(),/AWD/);assert.equal(await page.locator('.garage-part-number').innerText(),'FL-00251');assert.match(await page.locator('#garage-items').innerText(),/Demo part/);await page.locator('.garage-evidence summary').click();assert.match(await page.locator('#garage-items').innerText(),/generated_demo/);await page.locator('#garage-close').click();
  });
  await check('reload and a separate tab retain the cookie garage',async()=>{
   await page.reload();assert.equal(await page.locator('#garage-count').innerText(),'1');assert.equal(await page.locator('.garage-save').first().isDisabled(),true);
   const other=await context.newPage();await other.goto(base);assert.equal(await other.locator('#garage-count').innerText(),'1');await other.close();
  });
  await check('new chat retains bookmarks and remove enables save again',async()=>{
   await page.locator('#new-conversation').click();assert.equal(await page.locator('#garage-count').innerText(),'1');await send();assert.equal(await page.locator('.garage-save').first().isDisabled(),true);await open();await page.getByRole('button',{name:'Remove Oil filter FL-00251',exact:false}).click();await page.locator('#garage-status').filter({hasText:/empty/}).waitFor();assert.equal(await page.locator('#garage-count').innerText(),'0');await page.locator('#garage-close').click();assert.equal(await page.locator('.garage-save').first().isDisabled(),false);
  });
  await check('duplicate cards cannot create duplicate bookmarks and clear survives reload',async()=>{
   await page.locator('.garage-save').first().click();await send();assert.equal(await page.locator('.garage-save').count(),2);assert.equal(await page.locator('.garage-save:not([disabled])').count(),0);assert.equal(await page.locator('#garage-count').innerText(),'1');await open();await page.locator('#garage-clear').click();await page.locator('#garage-status').filter({hasText:/empty/}).waitFor();await page.locator('#garage-close').click();await page.reload();assert.equal(await page.locator('#garage-count').innerText(),'0');
  });
  await check('capacity is bounded and clearing an unreadable cookie recovers',async()=>{
   await context.addCookies([{name:cookieName,value:encodeURIComponent(JSON.stringify(Array.from({length:20},(_,i)=>['SX4-01','STALE-'+i]))),url:base}]);await page.reload();await page.locator('.garage-save').first().click();assert.match(await page.locator('#garage-toast').innerText(),/20 applications/);
   await context.addCookies([{name:cookieName,value:'broken',url:base}]);await page.reload();await open();assert.match(await page.locator('#garage-status').innerText(),/could not be read/);await page.locator('#garage-clear').click();await page.locator('#garage-status').filter({hasText:/empty/}).waitFor();await page.locator('#garage-close').click();
  });
  await check('saved garage is usable on mobile without overflow',async()=>{
   await page.locator('.garage-save').first().click();await page.setViewportSize({width:360,height:780});await open();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.equal(await page.locator('#garage-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);await page.screenshot({path:'artifacts/garage-mobile.png',fullPage:true});await page.locator('#garage-close').click();await page.setViewportSize({width:1440,height:1000});await open();await page.screenshot({path:'artifacts/garage-desktop.png',fullPage:true});await page.locator('#garage-close').click();
  });
  await check('blocked cookie write produces a visible failure without a false save',async()=>{
   const isolated=await browser.newContext();const blocked=await isolated.newPage();await blocked.addInitScript(()=>Object.defineProperty(document,'cookie',{get:()=>'',set:()=>{}}));await blocked.route('**/api/chat',route=>route.fulfill({json:fixture}));await blocked.goto(base);await blocked.locator('#chat-input').fill('Oil filter');await blocked.locator('#chat-send').click();await blocked.locator('.garage-save').first().click();assert.match(await blocked.locator('#garage-toast').innerText(),/could not save/);assert.equal(await blocked.locator('#garage-count').innerText(),'0');assert.equal(await blocked.locator('.garage-save').first().isDisabled(),false);await isolated.close();
  });
  assert.deepEqual(errors,[]);fs.writeFileSync('artifacts/garage-browser-results.json',JSON.stringify({passed,errors},null,2)+'\n');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
