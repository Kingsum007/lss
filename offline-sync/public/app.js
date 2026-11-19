import { SyncEngine } from './lib/engine.js';

const $ = id => document.getElementById(id);
const ui = Object.fromEntries([...document.querySelectorAll('[id]')].map(node => [node.id, node]));
let configured = false;
let unlocked = false;
let paused = false;
let busy = false;
let refreshing = false;
let refreshAgain = false;
let configLoaded = false;
let isDemo = false;
let viewGeneration = 0;
let engine;

function announce(message, kind = '') {
  ui.notice.textContent = message;
  ui.notice.className = `notice ${kind}`;
  ui.notice.hidden = !message;
}

function errorMessage(error) {
  return typeof error?.message === 'string' ? error.message : 'The operation could not be completed. Your saved records have been retained.';
}

function localDate() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function resetEntry() {
  ui['entry-form'].reset();
  ui['occurred-at'].value = localDate();
  ui['activity-count'].textContent = '0 / 1000';
}

function clearVisiblePayloads() {
  ui['records-list'].replaceChildren();
  ui['entry-form'].reset();
  ui['activity-count'].textContent = '0 / 1000';
  ui.passphrase.value = '';
  ui['passphrase-confirm'].value = '';
  ui['server-token'].value = '';
  ui.workspace.hidden = true;
  ui['vault-panel'].hidden = false;
}

function formatBytes(value = 0) {
  if (!Number.isFinite(value) || value < 0) return '—';
  return value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KiB`;
}

function formatMs(value) {
  if (!Number.isFinite(value)) return '—';
  return value < 1000 ? `${value.toFixed(0)} ms` : `${(value / 1000).toFixed(2)} s`;
}

function updateHint() {
  ui['network-hint'].textContent = navigator.onLine ? 'Network available · browser hint' : 'Offline · browser hint';
}

function renderRecords(records) {
  const fragment = document.createDocumentFragment();
  for (const record of records.slice(0, 50)) {
    const article = document.createElement('article');
    article.className = 'record';
    const body = document.createElement('div');
    const top = document.createElement('div');
    top.className = 'record-top';
    const site = document.createElement('strong');
    site.className = 'record-site';
    site.textContent = record.payload?.siteCode || 'Protected record';
    const time = document.createElement('span');
    time.className = 'record-time';
    const date = new Date(record.payload?.occurredAt || record.createdAt);
    time.textContent = Number.isNaN(date.getTime()) ? '' : date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    top.append(site, time);
    const activity = document.createElement('p');
    activity.className = 'record-activity';
    activity.textContent = record.payload?.activity || 'This record cannot be displayed. Its stored copy has been retained.';
    const meta = document.createElement('div');
    meta.className = 'record-meta';
    const quantity = [record.payload?.quantity, record.payload?.unit].filter(Boolean).join(' ');
    meta.textContent = `${quantity ? `${quantity} · ` : ''}${String(record.id).slice(0, 8)}`;
    body.append(top, activity, meta);
    if (record.error) {
      const warning = document.createElement('div');
      warning.className = 'record-error';
      warning.textContent = String(record.error);
      body.append(warning);
    }
    const state = document.createElement('span');
    state.className = `state-pill ${String(record.state).toLowerCase()}`;
    state.textContent = ({ PENDING: 'Waiting to send', IN_FLIGHT: 'Sending', ACKNOWLEDGED: 'Acknowledged', BLOCKED: 'Needs attention' })[record.state] || record.state;
    article.append(body, state);
    fragment.append(article);
  }
  ui['records-list'].replaceChildren(fragment);
  ui['records-empty'].hidden = records.length > 0;
}

function renderSnapshot(state) {
  configured = Boolean(state.configured);
  unlocked = Boolean(state.unlocked);
  ui['vault-panel'].hidden = unlocked;
  ui.workspace.hidden = !unlocked;
  ui['vault-heading'].textContent = configured ? 'Welcome back. Unlock your logs.' : 'Create your private workspace.';
  ui['vault-description'].textContent = configured ? 'Your encrypted entries are still on this device. Unlock to continue recording and resume delivery.' : 'Choose a strong passphrase to protect your site logs before they are stored on this device.';
  ui['vault-submit'].textContent = busy ? 'Opening workspace…' : configured ? 'Unlock workspace' : 'Create encrypted workspace';
  ui['vault-submit'].disabled = busy;
  ui.passphrase.disabled = busy;
  ui.passphrase.autocomplete = configured ? 'current-password' : 'new-password';
  ui.passphrase.minLength = configured ? 1 : 12;
  ui['confirm-row'].hidden = configured;
  ui['passphrase-confirm'].required = !configured;
  ui['passphrase-help'].textContent = configured ? 'The encryption key stays in memory while this workspace is unlocked.' : 'Use at least 12 characters. Keep this passphrase safe: it is needed to recover your encrypted entries.';
  for (const [key, id] of Object.entries({ PENDING: 'count-pending', IN_FLIGHT: 'count-inflight', ACKNOWLEDGED: 'count-acknowledged', BLOCKED: 'count-blocked' })) {
    ui[id].textContent = state.counts?.[key] ?? 0;
  }
  ui['batch-limit'].textContent = ((state.batchBytes || 2048) / 1024).toLocaleString(undefined, { maximumFractionDigits: 2 });
  ui['metric-attempts'].textContent = state.metrics?.attempts ?? 0;
  ui['metric-bytes'].textContent = formatBytes(state.metrics?.requestBytes ?? 0);
  ui['metric-duration'].textContent = formatMs(state.metrics?.lastDurationMs);
  ui['metric-unlock'].textContent = formatMs(state.metrics?.unlockMs);
  const pending = state.counts?.PENDING || 0;
  const inflight = state.counts?.IN_FLIGHT || 0;
  const blocked = state.counts?.BLOCKED || 0;
  let status = pending ? 'Entries are queued' : 'Ready to record';
  let detail = 'Your entries are protected on this device.';
  let dot = '';
  if (inflight) { status = 'Sending queued entries'; detail = 'Waiting for committed receipts from the server.'; }
  if (pending) { detail = 'Automatic retries continue while this workspace is unlocked.'; }
  if (!pending && !inflight && (state.counts?.ACKNOWLEDGED || 0) > 0) { status = 'All eligible entries acknowledged'; detail = 'Server receipts have been saved on this device.'; }
  if (blocked) { detail = `${blocked} ${blocked === 1 ? 'record needs' : 'records need'} attention. Saved copies have been retained.`; dot = 'paused'; }
  if (state.lastError) { status = 'Delivery needs attention'; detail = String(state.lastError); dot = 'paused'; }
  if (String(state.phase).toLowerCase().includes('auth')) { status = 'Server authentication needed'; detail = 'Add a current access token in Server connection.'; dot = 'paused'; }
  if (String(state.phase).toLowerCase().includes('storage')) { status = 'Local storage needs attention'; detail = state.lastError || 'Processing has paused to preserve saved records.'; dot = 'error'; }
  if (paused) { status = 'Demo connection paused'; detail = 'Local saves continue. Resume the connection to send queued entries.'; dot = 'paused'; }
  ui['sync-status'].textContent = status;
  ui['sync-detail'].textContent = detail;
  ui['sync-dot'].className = `status-dot ${dot}`;
  if (unlocked) renderRecords(state.records || []);
  else ui['records-list'].replaceChildren();
}

async function refresh() {
  if (refreshing) { refreshAgain = true; return; }
  refreshing = true;
  try {
    do {
      refreshAgain = false;
      const generation = viewGeneration;
      const state = await engine.snapshot();
      if (generation === viewGeneration) renderSnapshot(state);
      else refreshAgain = true;
    } while (refreshAgain);
  } catch (error) { announce(errorMessage(error), 'error'); }
  finally { refreshing = false; }
}

async function readConfig() {
  if (configLoaded) return;
  try {
    const response = await fetch('/api/config', { cache: 'no-store', signal: AbortSignal.timeout(5000) });
    if (!response.ok) return;
    const config = await response.json();
    isDemo = config.demo === true;
    configLoaded = true;
    ui['authentication-panel'].hidden = isDemo;
    ui['demo-note'].hidden = !isDemo;
    if (isDemo) engine.setToken('local-demo-only');
    if (unlocked) engine.kick();
  } catch { /* An offline session can still capture records without server configuration. */ }
}

async function boot() {
  if (!window.isSecureContext || !globalThis.crypto?.subtle || !globalThis.indexedDB) {
    ui.unsupported.hidden = false;
    ui['vault-panel'].hidden = true;
    ui['offline-ready'].textContent = 'Secure browser context required';
    return;
  }
  engine = new SyncEngine({ transport: (...args) => paused ? Promise.reject(new TypeError('Demo connection is paused.')) : fetch(...args) });
  window.lss = engine;
  engine.addEventListener('change', refresh);
  await engine.init();
  await refresh();
  resetEntry();
  updateHint();
  readConfig();
  setInterval(() => { if (!configLoaded) readConfig(); }, 15000);

  ui['vault-form'].addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    const passphrase = ui.passphrase.value;
    if (!configured && passphrase !== ui['passphrase-confirm'].value) { announce('The passphrases do not match.', 'error'); return; }
    busy = true;
    ui['vault-submit'].disabled = true;
    ui['vault-submit'].textContent = 'Opening workspace…';
    announce('');
    try {
      if (configured) await engine.unlock(passphrase);
      else await engine.setup(passphrase);
      ui.passphrase.value = '';
      ui['passphrase-confirm'].value = '';
      resetEntry();
      engine.start();
      await refresh();
      ui['site-code'].focus();
    } catch (error) { announce(errorMessage(error), 'error'); }
    finally { busy = false; ui.passphrase.value = ''; ui['passphrase-confirm'].value = ''; await refresh(); }
  });

  ui['entry-form'].addEventListener('submit', async event => {
    event.preventDefault();
    if (!unlocked || ui['save-entry'].disabled) return;
    const date = new Date(ui['occurred-at'].value);
    if (Number.isNaN(date.getTime())) { announce('Choose a valid date and time.', 'error'); return; }
    const payload = { siteCode: ui['site-code'].value.trim(), occurredAt: date.toISOString(), activity: ui.activity.value.trim() };
    if (ui.quantity.value.trim()) payload.quantity = ui.quantity.value.trim();
    if (ui.unit.value.trim()) payload.unit = ui.unit.value.trim();
    ui['save-entry'].disabled = true;
    try {
      const result = await engine.save(payload);
      resetEntry();
      ui['save-time'].textContent = `Local save: ${formatMs(result.saveMs)}`;
      announce('Entry encrypted and saved on this device. Delivery will continue automatically.');
      await refresh();
      ui['site-code'].focus();
    } catch (error) { announce(errorMessage(error), 'error'); }
    finally { ui['save-entry'].disabled = false; }
  });
  ui.activity.addEventListener('input', () => { ui['activity-count'].textContent = `${ui.activity.value.length} / 1000`; });
  ui.lock.addEventListener('click', () => {
    viewGeneration += 1;
    engine.stop();
    engine.lock();
    unlocked = false;
    clearVisiblePayloads();
    announce('Workspace locked. Your saved entries remain encrypted.');
    refresh();
  });
  ui['sync-now'].addEventListener('click', () => { readConfig(); engine.kick(); refresh(); });
  ui.policy.addEventListener('change', () => {
    try { engine.setPolicy(ui.policy.value); }
    catch (error) { ui.policy.value = engine.policy.mode; announce(errorMessage(error), 'error'); }
    refresh();
  });
  ui['pause-connection'].addEventListener('change', () => {
    paused = ui['pause-connection'].checked;
    if (!paused) { readConfig(); engine.kick(); }
    refresh();
  });
  ui['token-form'].addEventListener('submit', event => {
    event.preventDefault();
    engine.setToken(ui['server-token'].value.trim());
    ui['server-token'].value = '';
    engine.kick();
    announce('Access token set for this session. A server response will confirm the connection.');
  });
  window.addEventListener('online', () => { updateHint(); readConfig(); engine.kick(); });
  window.addEventListener('offline', updateHint);
  window.addEventListener('pagehide', () => { viewGeneration += 1; engine.stop(); engine.lock(); unlocked = false; clearVisiblePayloads(); });
  window.addEventListener('pageshow', () => { updateHint(); refresh(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { readConfig(); engine.kick(); refresh(); } });

  if ('serviceWorker' in navigator) {
    try {
      await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;
      ui['offline-ready'].textContent = 'Application ready for offline use';
    } catch { ui['offline-ready'].textContent = 'Offline reload unavailable; keep this page open'; }
  } else { ui['offline-ready'].textContent = 'Keep this page open while offline'; }
}

boot().catch(error => { announce(errorMessage(error), 'error'); ui['offline-ready'].textContent = 'Application could not finish loading'; });
