// The local server exposes the same modules that bundlers import from 'lss-sync'.
import { BrowserSyncEngine } from '/src/index.js';

const status = document.querySelector('#status');
const offline = document.querySelector('#offline');
const sync = new BrowserSyncEngine({
  dbName: 'lss-integration-example',
  endpoint: '/api/sync',
  token: 'local-demo-only', // Demo credential. Supply your application's token in production.
  transport: (...args) => {
    if (offline.checked) throw new TypeError('Simulated offline connection');
    return fetch(...args);
  }
});

async function refresh() {
  const state = await sync.snapshot();
  status.textContent = JSON.stringify({
    unlocked: state.unlocked,
    counts: state.counts,
    batchBytes: state.batchBytes,
    error: state.lastError
  }, null, 2);
}

async function showErrors(action) {
  try { await action(); await refresh(); }
  catch (error) { status.textContent = error.message; }
}

await sync.init();
sync.addEventListener('change', refresh);
await refresh();

document.querySelector('#unlock').onclick = () => showErrors(async () => {
  const input = document.querySelector('#password');
  const state = await sync.snapshot();
  try {
    if (state.configured) await sync.unlock(input.value);
    else await sync.setup(input.value);
  } finally { input.value = ''; }
});
document.querySelector('#save').onclick = () => showErrors(async () => {
  await sync.save(JSON.parse(document.querySelector('#payload').value));
});
document.querySelector('#lock').onclick = () => showErrors(async () => {
  sync.lock();
  document.querySelector('#payload').value = '';
});
// Restoring transport allows the running scheduler to retry; it honors retry delays.
// Call await sync.close() when disposing this integration in a single-page app.
