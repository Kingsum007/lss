export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type PolicyMode = 'adaptive' | 'fixed-small' | 'fixed-large';
export type QueueState = 'PENDING' | 'IN_FLIGHT' | 'ACKNOWLEDGED' | 'BLOCKED';
export interface Operation { id: string; schema: 1; payload: string; digest: string; }
export interface SyncOptions<T extends JsonValue = JsonValue> {
  dbName?: string;
  endpoint?: string;
  token?: string;
  policy?: PolicyMode;
  transport?: typeof fetch;
  timeoutMs?: number;
  random?: () => number;
  validator?: ((payload: T) => boolean | void) | null;
}
export interface QueueRecord<T extends JsonValue = JsonValue> {
  id: string; state: QueueState; createdAt: string; error?: string; payload?: T;
}
export interface SyncSnapshot<T extends JsonValue = JsonValue> {
  configured: boolean; unlocked: boolean; counts: Record<QueueState, number>;
  batchBytes: number; phase: string; lastError: string;
  metrics: { attempts: number; requestBytes: number; responseBytes: number; lastDurationMs: number; unlockMs: number; lastSaveMs: number };
  records: QueueRecord<T>[];
}
/** Browser-only engine. Use HTTPS/localhost with IndexedDB, Web Crypto and Web Locks. */
export class BrowserSyncEngine<T extends JsonValue = JsonValue> extends EventTarget {
  constructor(options?: SyncOptions<T>);
  readonly unlocked: boolean;
  readonly dbName: string;
  readonly phase: string;
  init(): Promise<{ configured: boolean }>;
  setup(passphrase: string): Promise<void>;
  unlock(passphrase: string): Promise<void>;
  lock(): void;
  save(payload: T): Promise<{ id: string; saveMs: number }>;
  start(): void;
  stop(): void;
  kick(): void;
  setToken(token: string): void;
  setPolicy(mode: PolicyMode): void;
  snapshot(): Promise<SyncSnapshot<T>>;
  close(): Promise<void>;
}
export interface BatchObservation { transientFailure?: boolean; durationMs: number; full?: boolean; allAcknowledged?: boolean; }
export class BatchPolicy {
  constructor(mode?: PolicyMode);
  mode: PolicyMode; bytes: number; successes: number;
  setMode(mode: PolicyMode): void;
  observe(observation: BatchObservation): number;
}
export function retryDelay(attempt: number, random?: () => number): number;
export function retryAfter(value: string | null, now?: number): number;
export function canonicalPayload(value: JsonValue): string;
export function createOperation(value: JsonValue, id?: string): Promise<Operation>;
export function encodeBatch(operations: Operation[]): string;
export function digest(value: string): Promise<string>;
export function byteLength(value: string): number;
export const MIN_BATCH: 2048;
export const MAX_BATCH: 16384;
export const SCHEMA: 1;
