/** Reproducible application-layer link emulator; no claim of measured Afghan connectivity. */
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile, writeFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import path from 'node:path';
import os from 'node:os';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const full = process.argv.includes('--full');
const reps = full ? 10 : 1, records = full ? 100 : 12;
const output = path.join(root, 'test-results', `benchmark-${new Date().toISOString().replace(/[:.]/g, '-')}`);
await mkdir(output, { recursive: true });
const require = createRequire(import.meta.url);
let playwright;
for (const item of [process.env.PLAYWRIGHT_MODULE, 'playwright', 'C:/Users/sumir/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.js'].filter(Boolean)) {
  try { playwright = require(item); break; } catch { /* documented fallback */ }
}
if (!playwright) throw new Error('Set PLAYWRIGHT_MODULE or install Playwright to run browser measurements.');
const port = await new Promise((resolve, reject) => { const server = createServer(); server.on('error', reject); server.listen(0, '127.0.0.1', () => { const p = server.address().port; server.close(() => resolve(p)); }); });
const origin = `http://127.0.0.1:${port}`;
const server = spawn(process.env.PYTHON || 'python', ['server.py', '--demo', '--port', String(port), '--db', path.join(output, 'server.sqlite3')], { cwd: root, windowsHide: true, stdio: 'ignore' });
let spawnError; server.on('error', e => { spawnError = e; });
const pause = ms => new Promise(r => setTimeout(r, ms));
const profiles = [
  { name: 'P1', kbps: 256, rttMs: 200, outageWindowMs: 0, intermittentUntilMs: 0 },
  { name: 'P2', kbps: 32, rttMs: 800, outageWindowMs: 0, intermittentUntilMs: 0 },
  { name: full ? 'P3' : 'P3-smoke', kbps: 16, rttMs: 1200, outageWindowMs: full ? 20000 : 2000, intermittentUntilMs: full ? 180000 : 12000 }
];
const modes = ['adaptive', 'fixed-small', 'fixed-large'];
const runs = []; let browser; let browserVersion;
try {
  for (let i = 0; i < 100; i++) {
    if (spawnError) throw spawnError;
    try { if ((await fetch(origin + '/api/health')).ok) break; } catch {}
    if (i === 99) throw new Error('Benchmark server did not start.');
    await pause(100);
  }
  browser = await playwright.chromium.launch({ headless: true, args: ['--enable-precise-memory-info'], ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : existsSync('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe') ? { channel: 'msedge' } : {}) });
  browserVersion = browser.version();
  for (let repetition = 0; repetition < reps; repetition++) for (const profile of profiles) {
    const order = modes.map((_, i) => modes[(i + repetition) % modes.length]);
    for (const mode of order) {
      const context = await browser.newContext();
      const page = await context.newPage();
      await page.goto(origin + '/api/health');
      const run = await page.evaluate(async ({ profile, mode, repetition, records, full }) => {
        const { SyncEngine } = await import('/lib/engine.js');
        const { canonicalPayload, byteLength } = await import('/lib/encoding.js');
        const sleep = ms => new Promise(r => setTimeout(r, ms));
        let seed = repetition + 1701;
        const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
        const traffic = { requests: 0, requestBytes: 0, generatedResponseBytes: 0, lostResponses: 0, precommitFailures: 0 };
        let traceStart = 0;
        const available = () => !profile.outageWindowMs || performance.now() - traceStart >= profile.intermittentUntilMs || Math.floor((performance.now() - traceStart) / profile.outageWindowMs) % 2 === 0;
        const phaseDelay = async (ms, signal) => {
          const until = performance.now() + ms;
          while (performance.now() < until) {
            if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
            if (!available()) throw new TypeError('Simulated outage');
            await sleep(Math.min(25, Math.max(0, until - performance.now())));
          }
          if (signal.aborted || !available()) throw new TypeError('Simulated interrupted exchange');
        };
        const transport = async (url, init) => {
          traffic.requests++;
          const bytes = byteLength(init.body); traffic.requestBytes += bytes;
          try { await phaseDelay(profile.rttMs / 2 + bytes * 8 / profile.kbps, init.signal); }
          catch (error) { traffic.precommitFailures++; throw error; }
          const response = await fetch(url, init);
          const text = await response.text();
          const responseBytes = byteLength(text); traffic.generatedResponseBytes += responseBytes;
          try { await phaseDelay(profile.rttMs / 2 + responseBytes * 8 / profile.kbps, init.signal); }
          catch (error) { traffic.lostResponses++; throw error; }
          return new Response(text, { status: response.status, headers: response.headers });
        };
        const engine = new SyncEngine({ dbName: `benchmark-${crypto.randomUUID()}`, policy: mode, token: 'local-demo-only', transport, random });
        await engine.init(); await engine.setup('Synthetic benchmark vault 2026'); engine.stop();
        const saveMs = [], payloadBytes = [];
        for (let i = 0; i < records; i++) {
          const payload = { siteCode: 'NBCC-BENCH', occurredAt: '2026-11-17T00:00:00.000Z', activity: `Synthetic construction activity ${i}. ` };
          payload.activity += 'x'.repeat(512 - byteLength(canonicalPayload(payload)));
          payloadBytes.push(byteLength(canonicalPayload(payload)));
          saveMs.push((await engine.save(payload)).saveMs);
        }
        let summary;
        const baselineHeap = performance.memory?.usedJSHeapSize ?? null;
        let peakHeap = baselineHeap;
        traceStart = performance.now(); engine.start();
        const deadlineMs = full ? 600000 : 45000;
        do {
          await sleep(100);
          summary = await engine.store.summary(0);
          if (performance.memory) peakHeap = Math.max(peakHeap, performance.memory.usedJSHeapSize);
          if (summary.counts.ACKNOWLEDGED === records) break;
        } while (performance.now() - traceStart < deadlineMs);
        const elapsedMs = performance.now() - traceStart;
        engine.stop();
        const sorted = [...saveMs].sort((a, b) => a - b);
        const completed = summary.counts.ACKNOWLEDGED === records;
        return { profile: profile.name, settings: profile, mode, repetition, records, completed,
          completionMs: completed ? elapsedMs : null, observationMs: elapsedMs, deadlineMs,
          counts: summary.counts, finalBatchBytes: engine.policy.bytes, unlockMs: engine.metrics.unlockMs,
          saveMedianMs: sorted[Math.floor(sorted.length / 2)], saveP95Ms: sorted[Math.ceil(sorted.length * .95) - 1], saveMs, payloadBytes,
          heapGrowthBytes: baselineHeap === null ? null : Math.max(0, peakHeap - baselineHeap), traffic };
      }, { profile, mode, repetition, records, full });
      runs.push(run);
      console.log(`${profile.name} ${mode}: ${run.completed ? (run.completionMs / 1000).toFixed(2) + 's' : 'INCOMPLETE'}, ${run.traffic.requests} attempts, save p95 ${run.saveP95Ms.toFixed(2)}ms`);
      await writeFile(path.join(output, 'runs.json'), JSON.stringify(runs, null, 2));
      await context.close();
    }
  }
} finally { if (browser) await browser.close(); server.kill(); }

const assets = [];
async function scan(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const filename = path.join(dir, entry.name);
    if (entry.isDirectory()) await scan(filename);
    else { const bytes = await readFile(filename); assets.push({ file: path.relative(root, filename), bytes: bytes.length, gzipBytes: gzipSync(bytes).length }); }
  }
}
await scan(path.join(root, 'public'));
const report = { generatedAt: new Date().toISOString(), kind: full ? 'Full configured thesis experiment' : 'Quick engineering smoke benchmark',
  environment: { browser: browserVersion, node: process.version, os: `${os.type()} ${os.release()} ${os.arch()}`, cpu: os.cpus()[0]?.model, logicalCpus: os.cpus().length },
  method: 'Application-layer upload/download byte-rate delays and RTT around real HTTP and SQLite; deterministic availability windows and seeded jitter. No TCP, radio, or real mobile-link emulation.',
  limitations: ['Quick mode uses 12 records and one repetition; P3-smoke uses 2-second on/off windows for 12 seconds. It is not the proposed 90-run evaluation.', 'Heap includes the measurement harness and garbage-collection effects; not a total browser memory measure.', 'Gzip size is an asset-size estimate; the demo server sends uncompressed static assets.', 'Times describe this machine and synthetic conditions, not Afghanistan network measurements.'],
  assets, totalAssetBytes: assets.reduce((n, a) => n + a.bytes, 0), totalGzipAssetBytes: assets.reduce((n, a) => n + a.gzipBytes, 0), runs };
await writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
await writeFile(path.join(root, 'test-results', 'benchmark-latest.json'), JSON.stringify({ reportPath: path.join(output, 'report.json'), ...report }, null, 2));
console.log(`Saved ${runs.length} runs. Assets ${report.totalAssetBytes} bytes raw; ${report.totalGzipAssetBytes} bytes estimated gzip. Report: ${path.join(output, 'report.json')}`);
