import {chromium} from 'playwright';
import {spawn} from 'node:child_process';
import {existsSync,mkdirSync} from 'node:fs';
import assert from 'node:assert/strict';
const python=process.env.PYTHON||(existsSync('.venv/Scripts/python.exe')?'.venv/Scripts/python.exe':'python');
mkdirSync('test-results',{recursive:true});
const server=spawn(python,['examples/server.py','--port','18766','--db','test-results/browser.sqlite3'],{windowsHide:true,stdio:'ignore'});
let browser;
try{
 for(let i=0;i<50;i++){try{if((await fetch('http://127.0.0.1:18766/api/config')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({headless:true,...(existsSync('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')?{channel:'msedge'}:{})});
 const page=await browser.newPage();await page.goto('http://127.0.0.1:18766');
 const result=await page.evaluate(async()=>{
  const {BrowserSyncEngine}=await import('/src/index.js');let lose=true;
  const s=new BrowserSyncEngine({dbName:crypto.randomUUID(),token:'local-demo-only',transport:async(...a)=>{const r=await fetch(...a);if(lose){lose=false;await r.text();throw new TypeError('Lost response');}return r;}});
  await s.init();await s.setup('Synthetic browser SDK passphrase');s.stop();
  for(const p of [null,false,0,'',{kind:'generic',nested:['دری',true]}])await s.save(p);
  const before=await s.snapshot();s.start();
  const end=Date.now()+15000;let state;
  do{await new Promise(r=>setTimeout(r,100));state=await s.snapshot();}while(state.counts.ACKNOWLEDGED!==5&&Date.now()<end);
  s.lock();const locked=await s.snapshot();await s.close();
  return{before:before.records.map(r=>r.payload),count:state.counts.ACKNOWLEDGED,attempts:state.metrics.attempts,hidden:locked.records.every(r=>!('payload'in r))};
 });
 assert.equal(result.count,5);assert.ok(result.attempts>=2);assert.equal(result.hidden,true);assert.ok(result.before.includes(false));assert.ok(result.before.includes(null));assert.ok(result.before.includes(0));
 console.log('PASS browser generic payloads, Python endpoint, lost-response replay and locked snapshots');
}finally{await browser?.close();server.kill();}
