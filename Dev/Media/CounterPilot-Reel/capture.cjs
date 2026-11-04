'use strict';
// Actual live UI footage; no API routes, fixtures, or simulated responses.
const {chromium}=require(process.env.COUNTERPILOT_PLAYWRIGHT||'playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const scenes=require('./scenes.json');
const output=path.resolve('artifacts/counterpilot-reel');
const base=process.env.COUNTERPILOT_CHAT_URL||'http://127.0.0.1:8011';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 fs.mkdirSync(path.join(output,'raw'),{recursive:true});fs.mkdirSync(path.join(output,'stills'),{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:432,height:768},deviceScaleFactor:1,
  recordVideo:{dir:path.join(output,'raw'),size:{width:1080,height:1920}}});
 const page=await context.newPage(),video=page.video(),origin=Date.now(),markers=[],errors=[],turns=[];
 page.setDefaultTimeout(40000);page.on('pageerror',error=>errors.push(error.message));
 page.on('response',async response=>{
  if(response.url()===base+'/api/chat'&&response.request().method()==='POST'){
   const data=await response.json();turns.push({status:response.status(),parts:data.parts,question:data.question,
    types:(data.lookup?.candidates||[]).map(part=>part.part_type)});
  }
 });
 const active=()=>page.locator('.chat-message[data-snapshot]:not(.previous-result)').last();
 async function frame(name){await page.screenshot({path:path.join(output,'stills',name+'.png')});}
 async function top(){await active().evaluate(node=>{const log=document.getElementById('chat-messages');log.scrollTop+=node.getBoundingClientRect().top-log.getBoundingClientRect().top;});}
 async function section(index,action){
  const scene=scenes[index],start=(Date.now()-origin)/1000;console.log('Recording '+scene.id);
  await action();await frame(scene.id);
  const remaining=(scene.end-scene.start)*1000-(Date.now()-origin-start*1000);
  if(remaining>0)await pause(remaining);
  markers.push({id:scene.id,start,end:(Date.now()-origin)/1000,target_duration:scene.end-scene.start});
  fs.writeFileSync(path.join(output,'capture.json'),JSON.stringify({source:'actual live UI; no intercepted requests',markers,turns,errors},null,2));
 }
 async function send(text){
  await page.locator('#chat-input').pressSequentially(text,{delay:35});await pause(600);
  const responsePromise=page.waitForResponse(response=>response.url()===base+'/api/chat'&&response.request().method()==='POST');
  await page.locator('#chat-send').click();const response=await responsePromise;assert.equal(response.status(),200);
  await page.locator('#chat-send:not([disabled])').waitFor();assert.equal(await page.locator('#chat-error').isVisible(),false);
 }
 async function choose(name){
  const responsePromise=page.waitForResponse(response=>response.url()===base+'/api/chat'&&response.request().method()==='POST');
  await active().getByRole('button',{name,exact:true}).click();const response=await responsePromise;assert.equal(response.status(),200);
  await page.locator('#chat-send:not([disabled])').waitFor();await pause(800);
 }
 try{
  await page.goto('https://dev.meta.ai/events/global-hackathon',{waitUntil:'domcontentloaded',timeout:60000});
  const eventTitle=page.getByText('META GLOBAL AI DEVELOPER HACKATHON',{exact:true}).first();
  await eventTitle.waitFor();await eventTitle.scrollIntoViewIfNeeded();
  await section(0,async()=>{
   await frame('event-title');await pause(10000);
   await page.getByText('Build for Your World',{exact:true}).first().scrollIntoViewIfNeeded();await frame('event-theme');await pause(9000);
   await page.goto(base);await page.getByRole('heading',{name:'CounterPilot',exact:true}).waitFor();
  });
  await section(1,async()=>{await page.locator('#chat-input').focus();await pause(3000);});
  await section(2,async()=>{
   await send('I need brakes, an air filter, and a belt for my 2019 Toyota RAV4.');
   assert.equal(await active().locator('.request-item').count(),3);await top();await pause(4000);await frame('three-item-checklist');
   await active().locator('.item-jump').nth(1).click();await pause(4500);
  });
  await section(3,async()=>{
   await top();await choose('Brake pads');await choose('front');await choose('Serpentine belt');
   assert.equal(await active().locator('.candidate').count(),3);await top();await frame('three-results-checklist');await pause(1500);
   for(let index=0;index<3;index++){
    await active().locator('.item-jump').nth(index).click();await frame('result-'+(index+1));await pause(2000);
   }
  });
  await section(4,async()=>{
   await active().locator('.item-jump').first().click();const card=active().locator('.candidate').first();
   await card.locator('.part-evidence summary').click();await card.locator('.part-evidence').scrollIntoViewIfNeeded();await pause(10000);
   await card.locator('.badge').scrollIntoViewIfNeeded();await frame('demo-label');await pause(6000);
   await card.locator('.part-evidence').scrollIntoViewIfNeeded();
  });
  await section(5,async()=>{
   await send('Change the air filter to a cabin filter.');await top();assert.equal(await active().locator('.request-item').count(),3);
   assert.match(await active().locator('.item-jump').nth(1).innerText(),/cabin/i);await frame('corrected-checklist');await pause(5000);
   await active().locator('.item-jump').nth(1).click();await pause(5000);
  });
  await section(6,async()=>{
   await active().locator('.garage-prompt').scrollIntoViewIfNeeded();await pause(2000);
   await active().getByRole('button',{name:'Save all 3 displayed records',exact:true}).click();assert.equal(await page.locator('#garage-count').innerText(),'3');
   await page.locator('#garage-open').click();await page.locator('.garage-record').nth(2).waitFor();await frame('garage-three-records');await pause(4500);
   await page.locator('.garage-record').last().scrollIntoViewIfNeeded();await pause(3000);await page.locator('#garage-close').click();
   await active().getByRole('button',{name:'Add another part',exact:true}).click();assert.equal(await page.locator('#chat-input').inputValue(),'Also add ');await pause(2000);
  });
  await section(7,async()=>{
   // Leave the add-another-part message unsent, as specified in the script.
   await top();await frame('closing-checklist');await pause(6000);
   await active().locator('.item-jump').nth(1).click();await pause(5000);await top();
  });
  assert.deepEqual(errors,[]);assert.equal(turns.length,5);
  console.log('Capture completed: five live Meta chat turns, three saved records.');
 }finally{
  await context.close();await video.saveAs(path.join(output,'raw','counterpilot-live-walkthrough.webm'));await browser.close();
 }
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
