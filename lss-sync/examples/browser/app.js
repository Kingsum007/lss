import {BrowserSyncEngine} from '/src/index.js';
const sync=new BrowserSyncEngine({dbName:'sdk-example',token:'local-demo-only'});
const status=document.querySelector('#status');
const refresh=async()=>{const s=await sync.snapshot();status.textContent=JSON.stringify({unlocked:s.unlocked,counts:s.counts,batchBytes:s.batchBytes,error:s.lastError},null,2);};
await sync.init();sync.addEventListener('change',refresh);await refresh();
document.querySelector('#unlock').onclick=async()=>{try{const p=document.querySelector('#password');const s=await sync.snapshot();if(s.configured)await sync.unlock(p.value);else await sync.setup(p.value);p.value='';}catch(e){status.textContent=e.message;}};
document.querySelector('#save').onclick=async()=>{try{await sync.save(JSON.parse(document.querySelector('#payload').value));await refresh();}catch(e){status.textContent=e.message;}};
document.querySelector('#lock').onclick=()=>{sync.lock();document.querySelector('#payload').value='';};
