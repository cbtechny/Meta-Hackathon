const {chromium}=require(process.env.COUNTERPILOT_PLAYWRIGHT||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.COUNTERPILOT_CHAT_URL||'http://127.0.0.1:8013';
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  page.setDefaultTimeout(12000);const passed=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=await page.request.post(base+'/api/chat',{data:{edits:{year:2007,make:'Suzuki',model:'SX4',part:'oil filter',engine:'2.0L',drivetrain:'AWD'}}});assert.equal(response.status(),200);const complete=await response.json();
  const fixture=async()=>{await page.unroute('**/api/chat');await page.route('**/api/chat',r=>r.fulfill({json:complete}));};
  async function check(name,fn){await fn();passed.push(name);console.log('PASS '+name);}
  async function closeDetails(){if(await page.locator('#lookup-panel').isVisible())await page.locator('#close-details').click();}
  async function fresh(){await closeDetails();if(await page.locator('#new-conversation').isVisible())await page.locator('#new-conversation').click();}
  async function send(text='Oil filter for my 2007 Suzuki SX4'){await page.locator('#chat-input').fill(text);await page.locator('#chat-send').click();await page.locator('#chat-send:not([disabled])').waitFor();}
  await page.goto(base);
  await check('keyboard skip link reaches the composer and catalog coverage is accurate',async()=>{
   await page.keyboard.press('Tab');assert.equal(await page.locator('.skip-link').evaluate(n=>n===document.activeElement),true);await page.keyboard.press('Enter');assert.equal(await page.locator('#chat-input').evaluate(n=>n===document.activeElement),true);await page.locator('#catalog-summary').filter({hasText:/6 demo vehicles/}).waitFor();
  });
  await check('catalog discovery starts a real demo selection with provenance',async()=>{
   await page.locator('#browse-vehicles').click();assert.equal(await page.locator('.vehicle-choice').count(),6);const result=page.waitForResponse(r=>r.url()===base+'/api/chat');await page.locator('.vehicle-choice').filter({hasText:'Suzuki SX4'}).click();const data=await(await result).json();assert.equal(data.details.model,'SX4');assert.equal(data.state.sources.model,'demo profile');assert.equal(await page.locator('#vehicles-dialog').isVisible(),false);await page.locator('#chat-send:not([disabled])').waitFor();
  });
  await fresh();await fixture();await send();
  await check('copy part number reports success and uses the retrieved value',async()=>{
   await page.evaluate(()=>{window.testCopied=null;Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.testCopied=text}},configurable:true});});await page.locator('.copy-number').last().click();assert.equal(await page.evaluate(()=>window.testCopied),'FL-00251');assert.equal(await page.locator('.copy-number').last().innerText(),'Copied');
  });
  await check('failed request can be edited without losing details or duplicating bubbles',async()=>{
   await fresh();await page.unroute('**/api/chat');await page.route('**/api/chat',r=>r.fulfill({status:503,json:{detail:'Unavailable'}}));await page.locator('#chat-input').fill('Oil filter please');await page.locator('#chat-send').click();await page.locator('#chat-error').waitFor();await page.locator('#edit-failed').click();assert.equal(await page.locator('#chat-input').inputValue(),'Oil filter please');assert.equal(await page.locator('.user').count(),0);assert.equal(await page.locator('#chat-input').isEnabled(),true);await fixture();await send();assert.equal(await page.locator('.user').count(),1);
  });
  await check('expired session offers explicit continuation with known details',async()=>{
   let calls=0,payload;await page.unroute('**/api/chat');await page.route('**/api/chat',r=>{calls++;if(calls===1)return r.fulfill({status:409,json:{detail:'Expired'}});payload=r.request().postDataJSON();return r.fulfill({json:complete});});await page.locator('#chat-input').fill('Need another filter');await page.locator('#chat-send').click();await page.locator('#resume-chat').waitFor();assert.equal(await page.locator('#retry').isVisible(),false);await page.locator('#resume-chat').click();await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(payload.session_id,null);assert.equal(payload.revision,0);assert.equal(payload.details.model,'SX4');assert.equal(await page.locator('#chat-error').isVisible(),false);
  });
  await check('no-match state offers meaningful recovery and keeps the vehicle',async()=>{
   const noMatch={...complete,details:{...complete.details,year:2017},reply:'No application is loaded for this configuration.',question:null,lookup:{...complete.lookup,status:'outside_coverage',candidates:[],questions:[]}};await page.unroute('**/api/chat');await page.route('**/api/chat',r=>r.fulfill({json:noMatch}));await send('Actually 2017');assert.equal(await page.locator('.lookup-recovery').count(),1);await page.locator('.lookup-recovery').getByRole('button',{name:'Edit vehicle details'}).click();assert.equal(await page.locator('#chat-year').inputValue(),'2017');await closeDetails();
  });
  await fixture();await fresh();await send();
  await check('remove and clear can be undone and clear deletes the cookie',async()=>{
   await closeDetails();await page.locator('.garage-save').last().click();await page.locator('#garage-open').click();await page.locator('.garage-record').waitFor();await page.locator('.garage-record').getByRole('button',{name:/Remove/}).click();await page.locator('#garage-status').filter({hasText:/empty/}).waitFor();await page.locator('#garage-undo').click();await page.locator('.garage-record').waitFor();await page.locator('#garage-clear').click();await page.locator('#garage-status').filter({hasText:/empty/}).waitFor();assert.equal((await context.cookies()).some(c=>c.name==='counterpilot_garage_v1'),false);await page.locator('#garage-undo').click();await page.locator('.garage-record').waitFor();await page.locator('#garage-close').click();
  });
  await check('saved vehicle reuse sends the canonical demo command',async()=>{
   await page.unroute('**/api/chat');await page.locator('#garage-open').click();await page.locator('.garage-use').waitFor();const result=page.waitForResponse(r=>r.url()===base+'/api/chat');await page.locator('.garage-use').click();const r=await result;assert.equal(r.request().postDataJSON().message,'Demo SX4-01');assert.equal((await r.json()).state.sources.model,'demo profile');await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await page.locator('#garage-dialog').isVisible(),false);
  });
  await check('garage failures preserve bookmarks and provide an actionable retry',async()=>{
   await closeDetails();await page.route('**/api/garage',r=>r.fulfill({status:503,json:{detail:'Unavailable'}}));await page.locator('#garage-open').click();await page.getByRole('button',{name:'Retry garage'}).waitFor();assert((await context.cookies()).some(c=>c.name==='counterpilot_garage_v1'));await page.unroute('**/api/garage');await page.getByRole('button',{name:'Retry garage'}).click();await page.locator('.garage-record').waitFor();await page.locator('#garage-close').click();
  });
  await check('mobile details trap focus and Escape returns it to the trigger',async()=>{
   await page.setViewportSize({width:390,height:844});await page.locator('#details-toggle').click();assert.equal(await page.locator('#lookup-panel').getAttribute('aria-modal'),'true');await page.locator('#close-details').focus();await page.keyboard.press('Shift+Tab');assert.equal(await page.locator('#lookup-panel').evaluate(n=>n.contains(document.activeElement)),true);await page.keyboard.press('Tab');assert.equal(await page.locator('#close-details').evaluate(n=>n===document.activeElement),true);await page.keyboard.press('Escape');assert.equal(await page.locator('#lookup-panel').isVisible(),false);assert.equal(await page.locator('#details-toggle').evaluate(n=>n===document.activeElement),true);
  });
  await check('layouts and dialogs fit 320, 360, 390, 768 and 1440 pixels',async()=>{
   for(const width of [320,360,390,768,1440]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'page width '+width);await closeDetails();await page.locator('#garage-open').click();await page.locator('.garage-record').waitFor();assert.equal(await page.locator('#garage-dialog').evaluate(n=>n.scrollWidth<=n.clientWidth+1),true,'garage '+width);await page.locator('#garage-close').click();}
  });
  await check('key text meets 4.5:1 contrast and mobile actions have usable targets',async()=>{
   const contrast=await page.evaluate(()=>{
    function rgb(s){const m=s.match(/[\d.]+/g);return m?m.map(Number):[255,255,255];}function lum(c){const v=c.slice(0,3).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;});return v[0]*.2126+v[1]*.7152+v[2]*.0722;}
    return ['.candidate-vehicle','.price-note','.progress-meaning','.chat-note','.app-actions button','.garage-save'].flatMap(selector=>[...document.querySelectorAll(selector)].filter(n=>n.getClientRects().length&&!n.disabled).map(n=>{let p=n,bg;while(p){bg=rgb(getComputedStyle(p).backgroundColor);if(bg.length===3||bg[3]===1)break;p=p.parentElement;}if(!p)bg=[247,249,245];const a=lum(rgb(getComputedStyle(n).color)),b=lum(bg);return {selector,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};}));});for(const result of contrast)assert(result.ratio>=4.5,JSON.stringify(result));await page.setViewportSize({width:390,height:844});for(const selector of ['#chat-send','#garage-open','#details-toggle','.garage-save','.copy-number']){const box=await page.locator(selector).last().boundingBox();if(box)assert(box.height>=44,selector+' target height');}
  });
  await check('reduced motion disables dialog animations and offline feedback is explicit',async()=>{
   await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#garage-open').click();assert.equal(await page.locator('#garage-dialog').evaluate(n=>getComputedStyle(n).animationName),'none');await page.locator('#garage-close').click();await context.setOffline(true);await page.locator('#connection-status').waitFor();assert.match(await page.locator('#connection-status').innerText(),/offline/);await context.setOffline(false);await page.locator('#connection-status').waitFor({state:'hidden'});
  });
  await check('failed detail updates can be reviewed without overwriting confirmed state',async()=>{
   await page.setViewportSize({width:1440,height:1000});await fresh();await fixture();await send();if(await page.locator('#lookup-panel').isHidden())await page.locator('#details-toggle').click();await page.locator('#chat-engine').fill('3.5L');await page.locator('#chat-engine').press('Tab');await page.unroute('**/api/chat');await page.route('**/api/chat',r=>r.fulfill({status:503,json:{detail:'Unavailable'}}));await page.locator('#apply-details').click();await page.locator('#edit-failed').filter({hasText:'Review changes'}).waitFor();await page.locator('#edit-failed').click();assert.equal(await page.locator('#chat-engine').inputValue(),'3.5L');assert.equal(await page.locator('#apply-details').isEnabled(),true);assert.equal(await page.locator('#chat-error').isVisible(),false);await closeDetails();
  });
  await check('catalog discovery recovers after its first load fails',async()=>{
   const isolated=await context.newPage();isolated.on('pageerror',e=>errors.push(e.message));let calls=0;await isolated.route('**/api/catalog',r=>++calls===1?r.fulfill({status:503,json:{detail:'Unavailable'}}):r.continue());await isolated.goto(base);await isolated.locator('#browse-vehicles').click();await isolated.getByRole('button',{name:'Retry catalog',exact:true}).click();await isolated.locator('.vehicle-choice').filter({hasText:'Suzuki SX4'}).waitFor();assert.equal(await isolated.locator('.vehicle-choice').count(),6);assert.equal(calls,2);assert.equal(await isolated.getByRole('heading',{level:1}).count(),1);await isolated.close();
  });
  await check('storage failure keeps the draft and explains reload limitations',async()=>{
   await page.evaluate(()=>{Storage.prototype.setItem=function(){throw new Error('blocked')};});await page.locator('#chat-input').fill('Keep my draft');await page.locator('#storage-status').waitFor();assert.equal(await page.locator('#chat-input').inputValue(),'Keep my draft');
  });
  assert.deepEqual(errors,[]);fs.writeFileSync('artifacts/polish-browser-results.json',JSON.stringify({passed,errors},null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{console.error('FAIL product polish: '+e.message);process.exitCode=1;});
