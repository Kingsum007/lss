import test from 'node:test';
import assert from 'node:assert/strict';
import { BatchPolicy, retryDelay, retryAfter } from '../public/lib/policy.js';
import { canonicalPayload, digest, assertFits, byteLength, encodeBatch, MIN_BATCH, MAX_BATCH } from '../public/lib/encoding.js';
import { createVault, unlockVault, encryptRecord, decryptRecord } from '../public/lib/crypto.js';

test('Adaptive limit grows only after two full, entirely acknowledged fast batches', () => {
  const p = new BatchPolicy();
  const success = { transientFailure: false, durationMs: 8000, full: true, allAcknowledged: true };
  assert.equal(p.observe(success), 2048);
  assert.equal(p.observe(success), 4096);
  p.observe(success);
  p.observe({ ...success, full: false });
  assert.equal(p.observe(success), 4096);
  assert.equal(p.observe(success), 6144);
  for (let i = 0; i < 40; i++) p.observe(success);
  assert.equal(p.bytes, MAX_BATCH);
});

test('A slow acknowledgement or failed attempt halves the next limit without going below minimum', () => {
  const p = new BatchPolicy();
  p.bytes = MAX_BATCH;
  p.observe({ durationMs: 8001, full: true, allAcknowledged: true });
  assert.equal(p.bytes, MAX_BATCH / 2);
  for (let i = 0; i < 10; i++) p.observe({ transientFailure: true, durationMs: 1 });
  assert.equal(p.bytes, MIN_BATCH);
  assert.equal(p.successes, 0);
});

test('Fixed baselines keep the same limit under successes, failures, and slow transfers', () => {
  for (const [mode, expected] of [['fixed-small', MIN_BATCH], ['fixed-large', MAX_BATCH]]) {
    const p = new BatchPolicy(mode);
    for (let i = 0; i < 8; i++) p.observe({ transientFailure: i % 2 === 0, durationMs: 9000, full: true, allAcknowledged: true });
    assert.equal(p.bytes, expected);
  }
});

test('Jitter has exponential ceilings and a 30-second cap; Retry-After supports dates and seconds', () => {
  assert.equal(retryDelay(1, () => .5), 500);
  assert.equal(retryDelay(3, () => .5), 2000);
  assert.equal(retryDelay(100, () => .5), 15000);
  assert.equal(retryAfter('3', 10000), 13000);
  assert.equal(retryAfter('garbage', 10000), 0);
  assert.equal(retryAfter('Wed, 21 Oct 2015 07:28:00 GMT', 0), Date.parse('2015-10-21T07:28:00Z'));
});

test('Canonical payload normalizes field order, preserves Dari, and rejects extra data and timezone omissions', async () => {
  const input = { siteCode: ' NBCC-1 ', occurredAt: '2026-11-17T01:00:00Z', activity: 'ثبت فعالیت ساختمانی' };
  const a = canonicalPayload(input);
  const b = canonicalPayload({ activity: input.activity, occurredAt: input.occurredAt, siteCode: input.siteCode });
  assert.equal(a, b);
  assert.ok(a.includes(input.activity));
  assert.equal((await digest(a)).length, 64);
  assert.throws(() => canonicalPayload({ ...input, attachment: 'x' }));
  assert.throws(() => canonicalPayload({ ...input, occurredAt: '2026-11-17T01:00:00' }));
  assert.throws(() => canonicalPayload({ ...input, activity: '\ud800' }));
});

test('Admission counts UTF-8, escaped JSON payload, envelope, ID and digest against 2 KiB', () => {
  const operation = { id: crypto.randomUUID(), schema: 1, payload: 'ی'.repeat(700), digest: 'a'.repeat(64) };
  assert.equal(assertFits(operation), byteLength(encodeBatch([operation])));
  assert.ok(assertFits(operation) > operation.payload.length);
  assert.throws(() => assertFits({ ...operation, payload: 'ی'.repeat(1000) }));
});

test('AES-GCM key is non-extractable; wrong passphrase, changed ciphertext, ID and schema fail', async () => {
  const passphrase = 'Only a synthetic research passphrase';
  const { key, config } = await createVault(passphrase);
  assert.equal(key.extractable, false);
  await assert.rejects(() => crypto.subtle.exportKey('raw', key));
  const unlocked = await unlockVault(passphrase, config);
  await assert.rejects(() => unlockVault('Wrong synthetic passphrase', config));
  const id = crypto.randomUUID();
  const payload = 'Sensitive synthetic record — اطلاعات آزمایشی';
  const record = { id, schema: 1, ...await encryptRecord(unlocked, id, payload) };
  assert.equal(await decryptRecord(key, record), payload);
  await assert.rejects(() => decryptRecord(key, { ...record, id: crypto.randomUUID() }));
  await assert.rejects(() => decryptRecord(key, { ...record, schema: 2 }));
  const tampered = new Uint8Array(record.ciphertext.slice(0)); tampered[0] ^= 1;
  await assert.rejects(() => decryptRecord(key, { ...record, ciphertext: tampered.buffer }));
});
