export const encoder = new TextEncoder();
export const decoder = new TextDecoder('utf-8', { fatal: true });
export const MIN_BATCH = 2048;
export const MAX_BATCH = 16384;
export const SCHEMA = 1;

export function byteLength(value) { return encoder.encode(value).byteLength; }
export function hex(bytes) { return [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, '0')).join(''); }
export function base64(bytes) { return btoa(String.fromCharCode(...new Uint8Array(bytes))); }
export function unbase64(text) { return Uint8Array.from(atob(text), c => c.charCodeAt(0)); }
export async function digest(text) { return hex(await crypto.subtle.digest('SHA-256', encoder.encode(text))); }
export function encodeBatch(operations) { return JSON.stringify({ operations }); }
export function aad(id, schema = SCHEMA) { return encoder.encode(JSON.stringify([id, schema])); }

// Restrict the prototype to a small, immutable site log. No objects, attachments,
// numeric coercion, or locale-dependent serialization cross the wire.
export function canonicalPayload(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('A site log is required.');
  const allowed = new Set(['siteCode', 'occurredAt', 'activity', 'quantity', 'unit']);
  for (const key of Object.keys(input)) if (!allowed.has(key)) throw new Error(`Unsupported field: ${key}`);
  const result = {};
  for (const key of ['activity', 'occurredAt', 'quantity', 'siteCode', 'unit']) {
    const value = input[key];
    if (value === undefined && ['quantity', 'unit'].includes(key)) continue;
    if (typeof value !== 'string' || !value.isWellFormed()) throw new Error(`${key} must be valid text.`);
    const clean = value.trim();
    const max = key === 'activity' ? 1000 : key === 'occurredAt' ? 40 : 32;
    if ((!clean && !['quantity', 'unit'].includes(key)) || clean.length > max) throw new Error(`${key} is empty or too long.`);
    if (key === 'occurredAt' && (!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(clean) || !Number.isFinite(Date.parse(clean)))) throw new Error('Choose a valid date and time with a timezone.');
    result[key] = clean;
  }
  return JSON.stringify(result);
}

export function assertFits(operation) {
  const bytes = byteLength(encodeBatch([operation]));
  if (bytes > MIN_BATCH) throw new Error('This record exceeds the 2 KiB limit. Shorten the activity description.');
  return bytes;
}
