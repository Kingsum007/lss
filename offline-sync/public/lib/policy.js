import { MIN_BATCH, MAX_BATCH } from './encoding.js';

export class BatchPolicy {
  constructor(mode = 'adaptive') { this.setMode(mode); }
  setMode(mode) {
    if (!['adaptive', 'fixed-small', 'fixed-large'].includes(mode)) throw new Error('Unknown batching policy.');
    this.mode = mode;
    this.bytes = mode === 'fixed-large' ? MAX_BATCH : MIN_BATCH;
    this.successes = 0;
  }
  observe({ transientFailure, durationMs, full, allAcknowledged }) {
    if (this.mode !== 'adaptive') return this.bytes;
    if (transientFailure || durationMs > 8000) {
      this.bytes = Math.max(MIN_BATCH, Math.floor(this.bytes / 2));
      this.successes = 0;
    } else if (full && allAcknowledged) {
      if (++this.successes === 2) { this.bytes = Math.min(MAX_BATCH, this.bytes + MIN_BATCH); this.successes = 0; }
    } else this.successes = 0;
    return this.bytes;
  }
}

export function retryDelay(attempt, random = Math.random) {
  return Math.floor(Math.min(30000, 1000 * 2 ** Math.min(Math.max(attempt - 1, 0), 15)) * random());
}
export function retryAfter(value, now = Date.now()) {
  if (!value) return 0;
  if (/^\d+(?:\.\d+)?$/.test(value.trim())) return now + Number(value) * 1000;
  const date = Date.parse(value);
  return Number.isFinite(date) ? Math.max(now, date) : 0;
}
