/** Real-browser integration checks. These are functional tests, not the thesis's 90-run experiment. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdir, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const output = path.join(root, 'test-results', `browser-${stamp}`);
await mkdir(output, { recursive: true });
const modules = [process.env.PLAYWRIGHT_MODULE, 'playwright',
  'C:/Users/sumir/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js'].filter(Boolean);
let playwright;
for (const spec of modules) {
  try { playwright = require(spec); break; } catch { /* try the next documented location */ }
}
if (!playwright) throw new Error('Playwright is required for browser tests. Set PLAYWRIGHT_MODULE to its index.js.');

const port = await new Promise((resolve, reject) => {
  const socket = createServer();
  socket.on('error', reject);
  socket.listen(0, '127.0.0.1', () => { const p = socket.address().port; socket.close(() => resolve(p)); });
});
const origin = `http://127.0.0.1:${port}`;
const server = spawn(process.env.PYTHON || 'python', ['server.py', '--demo', '--port', String(port), '--db', path.join(output, 'server.sqlite3')],
  { cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let serverLog = '';
server.stdout.on('data', chunk => { serverLog += chunk; });
server.stderr.on('data', chunk => { serverLog += chunk; });
let launchError;
server.on('error', error => { launchError = error; });

const results = [];
let browser;
const contexts = new Set();
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const checkServer = async () => {
  for (let i = 0; i < 100; i++) {
    if (launchError) throw launchError;
    if (server.exitCode !== null) throw new Error(`Test server exited: ${serverLog}`);
    try { if ((await fetch(`${origin}/api/health`)).ok) return; } catch { /* startup */ }
    await pause(100);
  }
  throw new Error('Test server did not start.');
};
const serverCount = async () => (await (await fetch(`${origin}/api/stats`, { headers: { Authorization: 'Bearer local-demo-only' } })).json()).entries;

async function run(name, operation) {
  if (process.env.TEST_FILTER && !new RegExp(process.env.TEST_FILTER, 'i').test(name)) return;
  const started = performance.now();
  try {
    const details = await operation();
    results.push({ name, passed: true, durationMs: Math.round(performance.now() - started), ...(details ? { details } : {}) });
    console.log(`PASS ${name}`);
  } catch (error) {
    results.push({ name, passed: false, durationMs: Math.round(performance.now() - started), error: String(error.stack || error) });
    console.error(`FAIL ${name}: ${error.message}`);
  } finally {
    for (const context of contexts) await context.close();
    contexts.clear();
  }
}

async function newPage() {
  const context = await browser.newContext(); contexts.add(context);
  const page = await context.newPage();
  await page.goto(origin, { waitUntil: 'networkidle' });
  await page.evaluate(async () => {
    window.SyncEngine = (await import('/lib/engine.js')).SyncEngine;
    window.testPassphrase = 'Research test vault only 2026';
    window.sample = activity => ({ siteCode: 'NBCC-TEST', occurredAt: new Date().toISOString(), activity });
    window.networkMode = 'normal';
    window.transportCalls = 0; window.receivedResponses = 0; window.activeRequests = 0; window.maxRequests = 0;
    window.sentIds = []; window.lostResponses = 0;
    window.testTransport = async (url, init) => {
      window.transportCalls++;
      window.activeRequests++;
      window.maxRequests = Math.max(window.maxRequests, window.activeRequests);
      const body = JSON.parse(init.body);
      window.sentIds.push(body.operations.map(operation => operation.id));
      try {
        if (window.networkMode === 'offline') throw new TypeError('Synthetic disconnected link');
        if (window.networkMode === 'delay') await new Promise(resolve => setTimeout(resolve, 100));
        const response = await fetch(url, init);
        window.receivedResponses++;
        if (window.networkMode === 'lose-once') {
          await response.text();
          window.lostResponses++;
          window.networkMode = 'normal';
          throw new TypeError('Synthetic lost response after server commit');
        }
        if (window.networkMode === 'bad-receipt' && response.ok) {
          const value = await response.json();
          for (const receipt of value.receipts) receipt.digest = '0'.repeat(64);
          return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
        }
        return response;
      } finally { window.activeRequests--; }
    };
    window.engine = new window.SyncEngine({ dbName: `test-${crypto.randomUUID()}`, token: 'local-demo-only', transport: window.testTransport });
    await window.engine.init();
    await window.engine.setup(window.testPassphrase);
    window.engine.stop();
  });
  return { page, context };
}
async function counts(page, expected, timeout = 15000) {
  const deadline = Date.now() + timeout;
  let state;
  do {
    state = await page.evaluate(() => window.engine.snapshot());
    if (Object.entries(expected).every(([key, value]) => state.counts[key] === value)) return state;
    await pause(60);
  } while (Date.now() < deadline);
  assert.fail(`Queue did not reach ${JSON.stringify(expected)}; got ${JSON.stringify({ counts: state.counts, phase: state.phase, error: state.lastError })}`);
}
async function start(page) { await page.evaluate(() => { window.engine.start(); window.engine.kick(); }); }

try {
  await checkServer();
  const launch = { headless: true };
  if (process.env.BROWSER_EXECUTABLE) launch.executablePath = process.env.BROWSER_EXECUTABLE;
  else if (existsSync('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')) launch.channel = 'msedge';
  browser = await playwright.chromium.launch(launch);

  await run('Encrypted persistence, locked views, and wrong-passphrase rejection', async () => {
    const { page } = await newPage();
    const result = await page.evaluate(async () => {
      const secret = 'Private synthetic site activity 7F8E9D';
      const saved = await window.engine.save(window.sample(secret));
      const record = await window.engine.store.getRecord(saved.id);
      const config = await window.engine.store.getConfig();
      const summary = await window.engine.store.summary();
      const persisted = JSON.stringify([record, config, summary]);
      const ciphertext = new Uint8Array(record.ciphertext);
      const plainInCipher = new TextDecoder().decode(ciphertext).includes(secret);
      window.engine.lock();
      const locked = await window.engine.snapshot();
      let rejected = false;
      try { await window.engine.unlock('A definitely incorrect passphrase'); } catch { rejected = true; }
      return { persistedPlaintext: persisted.includes(secret), plainInCipher, cipherBytes: ciphertext.length,
        locked: !locked.unlocked, payloadHidden: locked.records.every(row => !row.payload), rejected, counts: locked.counts };
    });
    assert.equal(result.persistedPlaintext, false);
    assert.equal(result.plainInCipher, false);
    assert.ok(result.cipherBytes > 16);
    assert.equal(result.locked, true);
    assert.equal(result.payloadHidden, true);
    assert.equal(result.rejected, true);
    assert.equal(result.counts.PENDING, 1);
  });

  await run('Atomic save failure never reports success or creates a queue entry', async () => {
    const { page } = await newPage();
    const result = await page.evaluate(async () => {
      window.engine.store.save = async record => {
        const tx = window.engine.store.db.transaction(['records', 'outbox', 'nonces'], 'readwrite');
        const outcome = new Promise((resolve, reject) => { tx.onabort = () => reject(new Error('Synthetic storage abort')); tx.onerror = () => reject(tx.error); });
        tx.objectStore('records').add(record);
        tx.abort();
        await outcome;
      };
      let rejected = false;
      try { await window.engine.save(window.sample('Never committed')); } catch { rejected = true; }
      const records = await new Promise((resolve, reject) => {
        const req = window.engine.store.db.transaction('records').objectStore('records').count();
        req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
      });
      return { rejected, records, summary: await window.engine.store.summary() };
    });
    assert.equal(result.rejected, true);
    assert.equal(result.records, 0);
    assert.equal(Object.values(result.summary.counts).reduce((a, b) => a + b, 0), 0);
  });

  await run('Lost response after server commit retries the same ID without duplicate insertion', async () => {
    const { page } = await newPage();
    const before = await serverCount();
    await page.evaluate(async () => { window.networkMode = 'lose-once'; await window.engine.save(window.sample('Lost-response example')); });
    await start(page);
    await counts(page, { ACKNOWLEDGED: 1, PENDING: 0, IN_FLIGHT: 0 });
    const evidence = await page.evaluate(() => ({ sent: window.sentIds.flat(), lost: window.lostResponses, attempts: window.engine.metrics.attempts, responses: window.receivedResponses, mode: window.networkMode }));
    const sent = evidence.sent;
    assert.equal(evidence.lost, 1, JSON.stringify(evidence));
    assert.ok(sent.length >= 2, JSON.stringify(evidence));
    assert.equal(new Set(sent).size, 1);
    assert.equal((await serverCount()) - before, 1);
  });

  await run('Restart recovers persisted IN_FLIGHT entries and uploads them', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => {
      const saved = await window.engine.save(window.sample('Interrupted process'));
      await window.engine.store.transition([saved.id], row => ({ ...row, state: 'IN_FLIGHT' }));
      const dbName = window.engine.store.name;
      window.engine.stop(); window.engine.lock(); window.engine.store.close();
      window.engine = new window.SyncEngine({ dbName, token: 'local-demo-only', transport: window.testTransport });
      await window.engine.init(); await window.engine.unlock(window.testPassphrase);
    });
    await start(page);
    await counts(page, { ACKNOWLEDGED: 1, PENDING: 0, IN_FLIGHT: 0 });
  });

  await run('Corrupt ciphertext is retained and blocked while other records synchronize', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => {
      const bad = await window.engine.save(window.sample('Corrupted record'));
      await window.engine.save(window.sample('Unaffected record'));
      const record = await window.engine.store.getRecord(bad.id);
      const bytes = new Uint8Array(record.ciphertext); bytes[0] ^= 1;
      record.ciphertext = bytes.buffer;
      await new Promise((resolve, reject) => {
        const tx = window.engine.store.db.transaction('records', 'readwrite');
        tx.oncomplete = resolve; tx.onerror = () => reject(tx.error);
        tx.objectStore('records').put(record);
      });
    });
    await start(page);
    await counts(page, { BLOCKED: 1, ACKNOWLEDGED: 1, PENDING: 0, IN_FLIGHT: 0 });
    assert.equal(await page.evaluate(async () => (await window.engine.store.summary()).records.length), 2);
  });

  await run('Unverified server receipt cannot mark a local record acknowledged', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => { window.networkMode = 'bad-receipt'; await window.engine.save(window.sample('Receipt verification')); });
    await start(page);
    await page.waitForFunction(() => window.receivedResponses >= 1);
    await pause(300);
    const state = await page.evaluate(async () => { window.engine.stop(); return window.engine.snapshot(); });
    assert.equal(state.counts.ACKNOWLEDGED, 0);
    assert.equal(state.counts.PENDING + state.counts.IN_FLIGHT, 1);
    await page.evaluate(() => { window.networkMode = 'normal'; });
    await start(page);
    await counts(page, { ACKNOWLEDGED: 1 });
  });

  await run('Failed local acknowledgement commit retains the record for safe recovery', async () => {
    const { page } = await newPage();
    const before = await serverCount();
    await page.evaluate(async () => {
      await window.engine.save(window.sample('Local acknowledgement failure'));
      const original = window.engine.store.transition.bind(window.engine.store);
      window.ackFailureInjected = false;
      window.engine.store.transition = async (ids, change) => {
        const probe = change({ id: ids[0], state: 'IN_FLIGHT', retries: 0 });
        if (!window.ackFailureInjected && probe.state === 'ACKNOWLEDGED') {
          window.ackFailureInjected = true;
          throw new Error('Synthetic failed acknowledgement transaction');
        }
        return original(ids, change);
      };
    });
    await start(page);
    await page.waitForFunction(() => window.ackFailureInjected === true);
    const state = await page.evaluate(async () => { window.engine.stop(); return window.engine.snapshot(); });
    assert.equal(state.counts.ACKNOWLEDGED, 0);
    assert.equal(state.counts.PENDING + state.counts.IN_FLIGHT, 1);
    await start(page);
    await counts(page, { ACKNOWLEDGED: 1, PENDING: 0, IN_FLIGHT: 0 });
    assert.equal((await serverCount()) - before, 1);
  });

  await run('Unauthorized uploads pause without losing data and resume with valid credentials', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => { window.engine.setToken('invalid-demo-token'); await window.engine.save(window.sample('Authentication pause')); });
    await start(page);
    await page.waitForFunction(() => window.receivedResponses >= 1);
    await pause(200);
    const state = await page.evaluate(() => window.engine.snapshot());
    assert.equal(state.counts.ACKNOWLEDGED, 0);
    assert.equal(state.counts.PENDING + state.counts.IN_FLIGHT, 1);
    await page.evaluate(() => window.engine.setToken('local-demo-only'));
    await start(page);
    await counts(page, { ACKNOWLEDGED: 1 });
  });

  await run('Repeated synchronization triggers never start overlapping requests', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => {
      window.networkMode = 'delay';
      for (let i = 0; i < 12; i++) await window.engine.save(window.sample(`Sequential item ${i} ${'x'.repeat(350)}`));
      window.engine.start();
      for (let i = 0; i < 50; i++) window.engine.kick();
    });
    await counts(page, { ACKNOWLEDGED: 12, PENDING: 0, IN_FLIGHT: 0 }, 20000);
    assert.equal(await page.evaluate(() => window.maxRequests), 1);
  });

  await run('Browser offline reload preserves the encrypted queue and cached app shell', async () => {
    const { page, context } = await newPage();
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
      if (!navigator.serviceWorker.controller) await new Promise(resolve => navigator.serviceWorker.addEventListener('controllerchange', resolve, { once: true }));
      await window.engine.save(window.sample('Offline reload persistence'));
      window.reloadDatabase = window.engine.store.name;
    });
    const dbName = await page.evaluate(() => window.reloadDatabase);
    await context.setOffline(true);
    await page.reload({ waitUntil: 'domcontentloaded' });
    assert.ok(await page.locator('body').innerText());
    await page.evaluate(async database => {
      const { SyncEngine } = await import('/lib/engine.js');
      window.engine = new SyncEngine({ dbName: database, token: 'local-demo-only' });
      await window.engine.init();
      await window.engine.unlock('Research test vault only 2026');
      window.engine.stop();
    }, dbName);
    await counts(page, { PENDING: 1, ACKNOWLEDGED: 0 });
    await context.setOffline(false);
    await start(page);
    await counts(page, { ACKNOWLEDGED: 1 });
  });

  await run('Desktop and mobile app layouts remain usable without uncaught script errors', async () => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } }); contexts.add(context);
    const page = await context.newPage(); const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => Boolean(window.lss));
    await page.locator('#passphrase').fill('UI synthetic workspace 2026');
    await page.locator('#passphrase-confirm').fill('UI synthetic workspace 2026');
    await page.locator('#vault-submit').click();
    await page.locator('#workspace').waitFor({ state: 'visible' });
    await page.locator('.experiment-settings summary').first().click();
    await page.locator('#pause-connection').check();
    await page.locator('#site-code').fill('NBCC-01');
    await page.locator('#activity').fill('Synthetic example: foundation inspection completed.');
    await page.locator('#save-entry').click();
    await page.locator('#records-list .record').waitFor();
    await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    assert.deepEqual(errors, []);
    await page.locator('#lock').click();
    assert.equal(await page.locator('#activity').inputValue(), '');
    assert.equal(await page.locator('#records-list').innerText(), '');
    return { screenshots: ['desktop.png', 'mobile.png'] };
  });

  await run('Two workers sharing one vault serialize requests with the browser lock', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => {
      for (let i = 0; i < 10; i++) await window.engine.save(window.sample(`Concurrent worker ${i} ${'a'.repeat(400)}`));
      window.peer = new window.SyncEngine({ dbName: window.engine.dbName, token: 'local-demo-only', transport: window.testTransport });
      await window.peer.init(); await window.peer.unlock(window.testPassphrase); window.peer.stop();
      window.networkMode = 'delay'; window.engine.start(); window.peer.start();
    });
    await counts(page, { ACKNOWLEDGED: 10, PENDING: 0, IN_FLIGHT: 0 }, 20000);
    assert.equal(await page.evaluate(() => window.maxRequests), 1);
  });

  await run('Retry-After survives recovery and cannot be bypassed by repeated triggers', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => {
      await window.engine.save(window.sample('Rate-limit recovery'));
      window.gateTimes = [];
      const original = window.engine.transport;
      window.engine.transport = async (...args) => {
        window.gateTimes.push(Date.now());
        if (window.gateTimes.length === 1) return new Response('{}', { status: 429, headers: { 'Retry-After': '2' } });
        return original(...args);
      };
      window.engine.start();
    });
    await page.waitForFunction(() => window.gateTimes.length === 1);
    await pause(200);
    const gate = await page.evaluate(async () => {
      const saved = await window.engine.store.getConfig('retryGate');
      window.engine.stop(); window.engine._recovered = false; window.engine.start();
      for (let i = 0; i < 30; i++) window.engine.kick();
      return saved;
    });
    assert.ok(gate.until > Date.now());
    await counts(page, { ACKNOWLEDGED: 1 });
    const times = await page.evaluate(() => window.gateTimes);
    assert.ok(times[1] - times[0] >= 1950);
  });

  await run('Lock cancels an unlock already waiting for local configuration', async () => {
    const { page } = await newPage();
    const result = await page.evaluate(async () => {
      window.engine.lock();
      const original = window.engine.store.getConfig.bind(window.engine.store);
      window.engine.store.getConfig = async (...args) => { await new Promise(r => setTimeout(r, 30)); return original(...args); };
      const unlocking = window.engine.unlock(window.testPassphrase).then(() => false, () => true);
      window.engine.lock();
      return { cancelled: await unlocking, unlocked: window.engine.unlocked };
    });
    assert.equal(result.cancelled, true); assert.equal(result.unlocked, false);
  });

  await run('An IV collision including the key-check IV retries encryption atomically', async () => {
    const { page } = await newPage();
    const result = await page.evaluate(async () => {
      const config = await window.engine.store.getConfig();
      const iv = Uint8Array.from(atob(config.checkIv), c => c.charCodeAt(0));
      const original = crypto.getRandomValues.bind(crypto); let collisions = 0;
      crypto.getRandomValues = array => {
        if (array.byteLength === 12 && collisions++ === 0) { array.set(iv); return array; }
        return original(array);
      };
      try {
        const saved = await window.engine.save(window.sample('IV collision recovery'));
        const record = await window.engine.store.getRecord(saved.id);
        return { differentIV: record.iv !== config.checkIv, counts: (await window.engine.snapshot()).counts };
      } finally { crypto.getRandomValues = original; }
    });
    assert.equal(result.differentIV, true); assert.equal(result.counts.PENDING, 1);
  });

  await run('Actual upload timeout retains the entry and recovery ignores an incorrect online hint', async () => {
    const { page } = await newPage();
    await page.evaluate(async () => {
      await window.engine.save(window.sample('Timeout and online hint'));
      window.timeoutAttempts = 0;
      const original = window.engine.transport;
      window.engine.timeoutMs = 50;
      window.engine.transport = async (url, init) => {
        if (++window.timeoutAttempts === 1) return new Promise((resolve, reject) => {
          init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
        });
        window.engine.timeoutMs = 30000;
        return original(url, init);
      };
      Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false });
      window.engine.start();
    });
    await counts(page, { ACKNOWLEDGED: 1, PENDING: 0 });
    assert.ok(await page.evaluate(() => window.timeoutAttempts >= 2));
  });
} catch (error) {
  results.push({ name: 'Harness startup', passed: false, error: String(error.stack || error) });
  console.error(error.message);
} finally {
  for (const context of contexts) await context.close().catch(() => {});
  if (browser) await browser.close();
  server.kill();
  const report = { generatedAt: new Date().toISOString(), runtime: process.version, browser: browser ? browser.version() : null,
    purpose: 'Functional browser checks with synthetic records and injected faults; not the 90-run thesis evaluation.',
    passed: results.filter(r => r.passed).length, failed: results.filter(r => !r.passed).length, tests: results };
  await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
  await writeFile(path.join(root, 'test-results', 'browser-latest.json'), JSON.stringify({ reportPath: path.join(output, 'report.json'), ...report }, null, 2));
  console.log(`Browser checks: ${report.passed} passed, ${report.failed} failed. Report: ${path.join(output, 'report.json')}`);
  if (report.failed) process.exitCode = 1;
}
