import { encoder, decoder, base64, unbase64, aad } from './encoding.js';

export const ITERATIONS = 600000;
const CHECK = 'LSS vault verification v1';
const CHECK_AAD = encoder.encode('LSS key-check v1');

export async function deriveKey(passphrase, salt, iterations = ITERATIONS) {
  if (typeof passphrase !== 'string' || !passphrase.isWellFormed() || Array.from(passphrase).length < 12) throw new Error('Use a valid Unicode passphrase of at least 12 characters.');
  const material = await crypto.subtle.importKey('raw', encoder.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations, hash: 'SHA-256' }, material,
    { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}

export async function createVault(passphrase) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await deriveKey(passphrase, salt);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const check = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: CHECK_AAD }, key, encoder.encode(CHECK));
  return { key, config: { name: 'vault', version: 1, keyVersion: crypto.randomUUID(), iterations: ITERATIONS,
    salt: base64(salt), checkIv: base64(iv), check: base64(check) } };
}

export async function unlockVault(passphrase, config) {
  if (config.version !== 1 || config.iterations !== ITERATIONS) throw new Error('Unsupported vault configuration.');
  try {
    const key = await deriveKey(passphrase, unbase64(config.salt), config.iterations);
    const check = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unbase64(config.checkIv), additionalData: CHECK_AAD }, key, unbase64(config.check));
    if (decoder.decode(check) !== CHECK) throw new Error();
    return key;
  } catch { throw new Error('Cannot unlock. Check your passphrase; the vault may also be damaged.'); }
}

export async function encryptRecord(key, id, payload, schema = 1) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: aad(id, schema) }, key, encoder.encode(payload));
  return { iv: base64(iv), ciphertext };
}

export async function decryptRecord(key, record) {
  const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: unbase64(record.iv), additionalData: aad(record.id, record.schema) }, key, record.ciphertext);
  return decoder.decode(plain);
}
