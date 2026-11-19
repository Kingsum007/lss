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

function compareCodePoints(a, b) {
  const left = Array.from(a), right = Array.from(b);
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    const delta = left[i].codePointAt(0) - right[i].codePointAt(0);
    if (delta) return delta;
  }
  return left.length - right.length;
}

// LSS-JSON/1 is deliberately small and identical across SDKs. It preserves
// strings, sorts keys by Unicode code point, and accepts only safe integers.
// Decimal quantities should be strings. This is not a claim of RFC 8785 JCS.
export function canonicalPayload(input) {
  const active = new Set();
  const encode = (value, depth) => {
    if (depth > 32) throw new TypeError('JSON nesting exceeds 32 levels.');
    if (value === null) return 'null';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    if (typeof value === 'string') {
      if (!value.isWellFormed()) throw new TypeError('Strings must contain valid Unicode.');
      return JSON.stringify(value);
    }
    if (typeof value === 'number') {
      if (!Number.isSafeInteger(value)) throw new TypeError('Only safe integers are supported. Encode decimal quantities as strings.');
      return String(Object.is(value, -0) ? 0 : value);
    }
    if (typeof value !== 'object') throw new TypeError('Only JSON values are supported.');
    if (active.has(value)) throw new TypeError('Cyclic data cannot be synchronized.');
    if (Object.getOwnPropertySymbols(value).length) throw new TypeError('Symbol properties are not JSON.');
    active.add(value);
    let encoded;
    if (Array.isArray(value)) {
      if (Object.keys(value).length !== value.length) throw new TypeError('Sparse arrays or extra array properties are not supported.');
      encoded = '[' + Array.from(value, item => encode(item, depth + 1)).join(',') + ']';
    } else {
      if (![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw new TypeError('Use plain JSON objects.');
      encoded = '{' + Object.keys(value).sort(compareCodePoints).map(key => {
        if (!key.isWellFormed()) throw new TypeError('Object keys must contain valid Unicode.');
        return JSON.stringify(key) + ':' + encode(value[key], depth + 1);
      }).join(',') + '}';
    }
    active.delete(value);
    return encoded;
  };
  return encode(input, 0);
}

export function assertFits(operation) {
  const bytes = byteLength(encodeBatch([operation]));
  if (bytes > MIN_BATCH) throw new Error('The encoded operation exceeds 2 KiB. Reduce the payload size.');
  return bytes;
}

export async function createOperation(value, id = crypto.randomUUID()) {
  if (!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id)) throw new TypeError('Use a lowercase UUID for the operation ID.');
  const payload = canonicalPayload(value);
  const operation = { id, schema: SCHEMA, payload, digest: await digest(payload) };
  assertFits(operation);
  return operation;
}
