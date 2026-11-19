import { Store } from './store.js';
import { createVault, unlockVault, encryptRecord, decryptRecord } from './crypto.js';
import { canonicalPayload, digest, assertFits, byteLength, encodeBatch, SCHEMA } from './encoding.js';
import { BatchPolicy, retryDelay, retryAfter } from './policy.js';

const PERMANENT = new Set(['ID_CONFLICT', 'INVALID_OPERATION', 'INVALID_PAYLOAD', 'INVALID_DIGEST', 'BAD_DIGEST', 'INVALID_ID', 'INVALID_SCHEMA', 'UNSUPPORTED_SCHEMA', 'VALIDATION_ERROR']);
const LOOPBACK = new Set(['localhost', '127.0.0.1', '[::1]']);

export class SyncEngine extends EventTarget {
  #key = null;
  #epoch = 0;
  #token = '';

  constructor({ dbName = 'lss-v1', endpoint = '/api/sync', token = '', policy = 'adaptive', transport = globalThis.fetch.bind(globalThis), timeoutMs = 30000, random = Math.random, validator = null } = {}) {
    super();
    this.store = new Store(dbName);
    this.dbName = dbName;
    this.endpoint = new URL(endpoint, location.href);
    if (this.endpoint.origin !== location.origin) throw new Error('Use a same-origin synchronization endpoint.');
    if (this.endpoint.protocol !== 'https:' && !LOOPBACK.has(this.endpoint.hostname)) throw new Error('Synchronization requires HTTPS outside the local demo.');
    this.#token = token;
    this.transport = transport;
    this.timeoutMs = timeoutMs;
    this.random = random;
    if (validator !== null && typeof validator !== 'function') throw new TypeError('validator must be a synchronous function.');
    this.validator = validator;
    this.policy = new BatchPolicy(policy);
    this.phase = 'LOCKED';
    this.lastError = '';
    this.metrics = { attempts: 0, requestBytes: 0, responseBytes: 0, lastDurationMs: 0, unlockMs: 0, lastSaveMs: 0 };
    this._running = false;
    this._busy = false;
    this._recovered = false;
    this._lastAttempt = 0;
    this._authPaused = false;
    this._wake = () => { if (document.visibilityState !== 'hidden') this.kick(); };
  }

  get unlocked() { return this.#key !== null; }
  _emit() { this.dispatchEvent(new Event('change')); }

  async init() {
    if (!globalThis.crypto?.subtle || !globalThis.indexedDB || !navigator.locks) throw new Error('Open this application in a current browser on HTTPS or localhost.');
    await this.store.open();
    this.config = await this.store.getConfig();
    this.phase = this.config ? 'LOCKED' : 'SETUP';
    this._emit();
    return { configured: !!this.config };
  }

  async setup(passphrase) {
    const epoch = ++this.#epoch;
    const started = performance.now();
    const prepared = await createVault(passphrase);
    if (epoch !== this.#epoch) throw new Error('Unlock was cancelled.');
    await this.store.createVault(prepared.config);
    this.config = prepared.config;
    if (epoch !== this.#epoch) throw new Error('The vault was created. Unlock it to continue.');
    this.#key = prepared.key;
    this.metrics.unlockMs = performance.now() - started;
    this._recovered = false;
    this.phase = 'IDLE';
    this.lastError = '';
    this.start(); this._emit();
  }

  async unlock(passphrase) {
    if (this.unlocked) return;
    const epoch = ++this.#epoch;
    this.config = await this.store.getConfig();
    if (epoch !== this.#epoch) throw new Error('Unlock was cancelled.');
    if (!this.config) throw new Error('Create a local vault first.');
    const started = performance.now();
    const key = await unlockVault(passphrase, this.config);
    if (epoch !== this.#epoch) throw new Error('Unlock was cancelled.');
    this.#key = key;
    this.metrics.unlockMs = performance.now() - started;
    this.policy.setMode(this.policy.mode);
    this._recovered = false;
    this.phase = 'IDLE'; this.lastError = '';
    this.start(); this._emit();
  }

  lock() {
    ++this.#epoch;
    this.#key = null;
    this._controller?.abort();
    clearTimeout(this._timer);
    this.phase = this.config ? 'LOCKED' : 'SETUP';
    this.lastError = '';
    this._emit();
  }

  setToken(token) { this.#token = String(token); this._authPaused = false; if (this.unlocked) this.kick(); }
  setPolicy(mode) { if (this._busy) throw new Error('Wait for the current transfer before changing policy.'); this.policy.setMode(mode); this._emit(); }

  async save(input) {
    if (!this.#key) throw new Error('Unlock your local vault before saving.');
    const epoch = this.#epoch;
    const key = this.#key;
    const started = performance.now();
    const payload = canonicalPayload(input);
    this._validate(JSON.parse(payload));
    const id = crypto.randomUUID();
    const operation = { id, schema: SCHEMA, payload, digest: await digest(payload) };
    const bytes = assertFits(operation);
    // A rare IV-index collision causes a fresh encryption. Never reuse the IV,
    // report success before transaction commit, or fall back to plaintext.
    for (let attempt = 0; attempt < 4; attempt++) {
      const encrypted = await encryptRecord(key, id, payload);
      if (epoch !== this.#epoch || !this.#key) throw new Error('The vault was locked before the save completed.');
      try {
        await this.store.save({ id, schema: SCHEMA, keyVersion: this.config.keyVersion, ...encrypted, createdAt: new Date().toISOString() }, bytes);
        this.metrics.lastSaveMs = performance.now() - started;
        this.kick(); this._emit();
        return { id, saveMs: this.metrics.lastSaveMs };
      } catch (error) {
        if (error.name === 'ConstraintError' && attempt < 3) continue;
        this.lastError = 'The record could not be committed locally. Keep the form open and try again.';
        this._emit();
        throw error;
      }
    }
    throw new Error('Unable to reserve a unique encryption IV.');
  }

  _validate(value) {
    if (!this.validator) return;
    const result = this.validator(value);
    if (result && typeof result.then === 'function') throw new TypeError('The payload validator must be synchronous.');
    if (result === false) throw new Error('The payload was rejected by the application validator.');
  }

  start() {
    if (!this._running) {
      this._running = true;
      addEventListener('online', this._wake);
      addEventListener('focus', this._wake);
      document.addEventListener('visibilitychange', this._wake);
    }
    this.kick();
  }
  stop() {
    this._running = false;
    clearTimeout(this._timer);
    this._controller?.abort();
    removeEventListener('online', this._wake);
    removeEventListener('focus', this._wake);
    document.removeEventListener('visibilitychange', this._wake);
  }
  kick() {
    if (!this._running || !this.unlocked || this._authPaused) return;
    this._promptRequested = true;
    this._schedule(Math.max(0, 1000 - (Date.now() - this._lastAttempt)));
  }
  _schedule(delay = 0) {
    clearTimeout(this._timer);
    if (!this._running || !this.unlocked || this._authPaused) return;
    this._timer = setTimeout(() => { void this._loop(); }, Math.min(Math.max(0, delay), 2147483647));
  }

  async _loop() {
    if (this._busy || !this._running || !this.unlocked || this._authPaused) return;
    this._busy = true;
    let delay = 1000;
    try {
      const acquired = await navigator.locks.request(`lss-sync:${this.dbName}`, { ifAvailable: true }, async lock => {
        if (!lock) return false;
        if (!this.unlocked || !this._running) return true;
        if (!this._recovered) { await this.store.recover(); this._recovered = true; }
        const prompt = !!this._promptRequested;
        this._promptRequested = false;
        delay = await this._step(prompt);
        return true;
      });
      if (!acquired) delay = 1000;
    } catch {
      this._recovered = false;
      if (this.unlocked) {
        this.phase = 'STORAGE_ERROR';
        this.lastError = 'Storage is unavailable. Saved records remain queued; recovery will retry.';
      }
      delay = 5000;
      this._emit();
    } finally {
      this._busy = false;
      if (this._promptRequested) delay = Math.min(delay, Math.max(0, 1000 - (Date.now() - this._lastAttempt)));
      this._schedule(delay);
    }
  }

  async _select(prompt) {
    const key = this.#key;
    const epoch = this.#epoch;
    const operations = [];
    let seq = 0, full = false;
    while (this.unlocked && epoch === this.#epoch) {
      const item = await this.store.nextDue(seq, prompt ? Number.MAX_SAFE_INTEGER : Date.now());
      if (!item) break;
      seq = item.seq;
      const record = await this.store.getRecord(item.id);
      let operation;
      try {
        if (!record || record.keyVersion !== this.config.keyVersion) throw new Error();
        const payload = await decryptRecord(key, record);
        if (canonicalPayload(JSON.parse(payload)) !== payload) throw new Error();
        this._validate(JSON.parse(payload));
        operation = { id: record.id, schema: record.schema, payload, digest: await digest(payload) };
        assertFits(operation);
      } catch {
        if (epoch !== this.#epoch) break;
        await this.store.transition([item.id], row => ({ ...row, state: 'BLOCKED', error: 'LOCAL_INTEGRITY_ERROR' }));
        this._emit();
        continue;
      }
      if (byteLength(encodeBatch([...operations, operation])) > this.policy.bytes) { full = true; break; }
      operations.push(operation);
    }
    if (epoch !== this.#epoch || !this.unlocked) return { operations: [], full: false };
    return { operations, full };
  }

  async _step(prompt = false) {
    if (!this.#token) { this.phase = 'AUTH_REQUIRED'; this._authPaused = true; this._emit(); return 30000; }
    const gate = await this.store.getConfig('retryGate');
    if (gate?.until > Date.now()) { this.phase = 'WAITING'; this._emit(); return gate.until - Date.now(); }
    const { operations, full } = await this._select(prompt);
    if (!this.unlocked || !this._running) return 30000;
    if (!operations.length) {
      const due = await this.store.earliestDue();
      this.phase = due === null ? 'IDLE' : 'WAITING'; this._emit();
      return due === null ? 30000 : Math.max(10, due - Date.now());
    }
    const ids = operations.map(o => o.id);
    const expected = new Map(operations.map(o => [o.id, o.digest]));
    const body = encodeBatch(operations);
    await this.store.transition(ids, row => ({ ...row, state: 'IN_FLIGHT' }));
    if (!this.unlocked || !this._running) { await this.store.transition(ids, row => ({ ...row, state: 'PENDING' })); return 30000; }
    this.phase = 'SYNCING'; this.lastError = '';
    this._lastAttempt = Date.now();
    this.metrics.attempts++;
    this.metrics.requestBytes += byteLength(body);
    this._emit();
    const began = performance.now();
    const controller = new AbortController(); this._controller = controller;
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let reply, status = 0, gateUntil = 0, networkFailure = false;
    try {
      const response = await this.transport(this.endpoint.href, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${this.#token}` },
        body, cache: 'no-store', credentials: 'omit', redirect: 'error', signal: controller.signal });
      status = response.status;
      if ([429, 503].includes(status)) gateUntil = retryAfter(response.headers.get('Retry-After'));
      // Bound the response as well as the outgoing plaintext batch.
      const reader = response.body?.getReader();
      let text = '', size = 0;
      if (reader) {
        const decode = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 65536) { await reader.cancel(); throw new Error('Response too large.'); }
          text += decode.decode(value, { stream: true });
        }
        text += decode.decode();
      }
      this.metrics.responseBytes += size;
      if (response.ok) reply = JSON.parse(text);
      else networkFailure = true;
    } catch { networkFailure = true; }
    finally { clearTimeout(timeout); if (this._controller === controller) this._controller = null; }
    const durationMs = performance.now() - began;
    this.metrics.lastDurationMs = durationMs;
    if (gateUntil) await this.store.putConfig({ name: 'retryGate', until: gateUntil });

    const acknowledged = new Set(), blocked = new Map();
    if (reply && Array.isArray(reply.receipts) && Array.isArray(reply.errors)) {
      for (const receipt of reply.receipts) {
        if (receipt && receipt.status === 'COMMITTED' && expected.has(receipt.id) && receipt.digest === expected.get(receipt.id)) acknowledged.add(receipt.id);
      }
      for (const error of reply.errors) {
        if (error && expected.has(error.id) && error.permanent === true && PERMANENT.has(error.code) && !acknowledged.has(error.id)) blocked.set(error.id, error.code);
      }
    }
    if (status >= 400 && status < 500 && ![401, 403, 408, 429].includes(status)) {
      for (const id of ids) blocked.set(id, `HTTP_${status}`);
    }
    const authFailed = status === 401 || status === 403;
    const remaining = ids.filter(id => !acknowledged.has(id) && !blocked.has(id));
    const transientFailure = networkFailure || remaining.length > 0;
    let earliest = Infinity;
    // ACK state is itself transactional. If this commit fails, the next worker
    // recovery replays IN_FLIGHT IDs against the server's existing receipts.
    await this.store.transition(ids, row => {
      if (acknowledged.has(row.id)) return { ...row, state: 'ACKNOWLEDGED', error: undefined, acknowledgedAt: new Date().toISOString() };
      if (blocked.has(row.id)) return { ...row, state: 'BLOCKED', error: blocked.get(row.id) };
      const retries = row.retries + 1;
      const dueTime = Math.max(gateUntil, Date.now() + retryDelay(retries, this.random));
      earliest = Math.min(earliest, dueTime);
      return { ...row, state: 'PENDING', retries, dueTime };
    });
    this.policy.observe({ transientFailure, durationMs, full, allAcknowledged: acknowledged.size === ids.length });
    if (this.unlocked) {
      if (authFailed) { this.phase = 'AUTH_REQUIRED'; this._authPaused = true; this.lastError = 'Server authentication failed. Enter a valid server token to resume.'; }
      else if (transientFailure) { this.phase = 'WAITING'; this.lastError = 'The transfer was not fully confirmed. Saved records will retry automatically.'; }
      else { this.phase = 'IDLE'; this.lastError = ''; }
    }
    this._emit();
    return remaining.length ? Math.max(10, earliest - Date.now()) : 10;
  }

  async snapshot() {
    const epoch = this.#epoch, key = this.#key;
    const summary = await this.store.summary();
    const records = [];
    for (const row of summary.records) {
      let payload;
      if (key && epoch === this.#epoch) {
        try { const record = await this.store.getRecord(row.id); payload = JSON.parse(await decryptRecord(key, record)); } catch { /* Retain metadata for damaged records. */ }
      }
      records.push({ id: row.id, state: row.state, createdAt: row.createdAt, error: row.error, ...(payload !== undefined ? { payload } : {}) });
    }
    if (epoch !== this.#epoch || !this.unlocked) for (const record of records) delete record.payload;
    return { configured: !!this.config, unlocked: this.unlocked, counts: summary.counts, batchBytes: this.policy.bytes,
      phase: this.phase, lastError: this.lastError, metrics: { ...this.metrics }, records };
  }

  async close() {
    this.stop(); this.lock();
    while (this._busy) await new Promise(resolve => setTimeout(resolve, 10));
    this.store.close();
  }
}
