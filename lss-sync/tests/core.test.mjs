import test from 'node:test';
import assert from 'node:assert/strict';
import { canonicalPayload, createOperation, BatchPolicy } from '../src/index.js';
import { createVault, unlockVault, encryptRecord, decryptRecord } from '../src/crypto.js';
test('Generic Unicode JSON has deterministic code-point key ordering', () => {
  assert.equal(canonicalPayload({'2': false, '10': null, '\u{1d11e}': 'دری', '\ue000': [1,'2.5']}), '{"10":null,"2":false,"":[1,"2.5"],"𝄞":"دری"}');
  for(const v of [0,false,null,'']) assert.equal(canonicalPayload(v),JSON.stringify(v));
});
test('Unsupported and oversized input is rejected', async () => {
  for(const v of [1.2, NaN, Infinity, undefined, new Date(), '\ud800']) assert.throws(()=>canonicalPayload(v));
  const cycle={};cycle.a=cycle;assert.throws(()=>canonicalPayload(cycle));
  await assert.rejects(()=>createOperation({text:'x'.repeat(3000)}));
});
test('Adaptation and fixed baselines retain their specified bounds', () => {
  const p=new BatchPolicy();const ok={durationMs:100,full:true,allAcknowledged:true};
  p.observe(ok);p.observe(ok);assert.equal(p.bytes,4096);
  p.observe({durationMs:9000,allAcknowledged:true});assert.equal(p.bytes,2048);
  const fixed=new BatchPolicy('fixed-large');fixed.observe({transientFailure:true,durationMs:1});assert.equal(fixed.bytes,16384);
});
test('Encryption authenticates ciphertext and operation identity', async () => {
  const {key,config}=await createVault('SDK synthetic passphrase only');
  const recovered=await unlockVault('SDK synthetic passphrase only',config);
  await assert.rejects(()=>unlockVault('Wrong passphrase only',config));
  assert.equal(key.extractable,false);
  const id=crypto.randomUUID(),record={id,schema:1,...await encryptRecord(key,id,'false')};
  assert.equal(await decryptRecord(recovered,record),'false');
  await assert.rejects(()=>decryptRecord(key,{...record,id:crypto.randomUUID()}));
});
