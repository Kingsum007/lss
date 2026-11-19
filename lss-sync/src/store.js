function result(request) {
  return new Promise((resolve, reject) => { request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error); });
}
function completed(tx) {
  return new Promise((resolve, reject) => {
    let cause;
    tx.oncomplete = resolve;
    // The request error bubbles before tx.error is set. Preserve its type and
    // wait for the abort so callers retry only after rollback has completed.
    tx.onerror = event => { cause = event.target.error || tx.error; };
    tx.onabort = () => reject(tx.error || cause || new Error('Storage transaction aborted.'));
  });
}

export class Store {
  constructor(name) { this.name = name; }
  async open() {
    const req = indexedDB.open(this.name, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      db.createObjectStore('config', { keyPath: 'name' });
      db.createObjectStore('records', { keyPath: 'id' });
      db.createObjectStore('nonces', { keyPath: 'key' });
      const queue = db.createObjectStore('outbox', { keyPath: 'seq', autoIncrement: true });
      queue.createIndex('id', 'id', { unique: true });
      queue.createIndex('stateSeq', ['state', 'seq']);
      queue.createIndex('stateDue', ['state', 'dueTime']);
    };
    this.db = await result(req);
    this.db.onversionchange = () => this.db.close();
    return this;
  }
  async getConfig(name = 'vault') {
    return result(this.db.transaction('config').objectStore('config').get(name));
  }
  async putConfig(config) {
    const tx = this.db.transaction('config', 'readwrite'); const done = completed(tx);
    tx.objectStore('config').put(config); await done;
  }
  async createVault(config) {
    const tx = this.db.transaction(['config', 'nonces'], 'readwrite'); const done = completed(tx);
    tx.objectStore('config').add(config);
    tx.objectStore('nonces').add({ key: `${config.keyVersion}:${config.checkIv}` });
    await done;
  }
  async save(record, byteLength) {
    const tx = this.db.transaction(['records', 'outbox', 'nonces'], 'readwrite'); const done = completed(tx);
    tx.objectStore('nonces').add({ key: `${record.keyVersion}:${record.iv}` });
    tx.objectStore('records').add(record);
    tx.objectStore('outbox').add({ id: record.id, state: 'PENDING', retries: 0, dueTime: 0, byteLength, createdAt: record.createdAt });
    await done;
  }
  async getRecord(id) { return result(this.db.transaction('records').objectStore('records').get(id)); }
  async nextDue(afterSeq = 0, now = Date.now()) {
    const tx = this.db.transaction('outbox');
    const range = IDBKeyRange.bound(['PENDING', afterSeq], ['PENDING', Number.MAX_SAFE_INTEGER], true, false);
    return new Promise((resolve, reject) => {
      const req = tx.objectStore('outbox').index('stateSeq').openCursor(range);
      req.onerror = () => reject(req.error);
      req.onsuccess = () => {
        const c = req.result;
        if (!c) return resolve(null);
        if (c.value.dueTime <= now) resolve(c.value); else c.continue();
      };
    });
  }
  async earliestDue() {
    const range = IDBKeyRange.bound(['PENDING', 0], ['PENDING', Number.MAX_SAFE_INTEGER]);
    const cursor = await result(this.db.transaction('outbox').objectStore('outbox').index('stateDue').openCursor(range));
    return cursor ? cursor.value.dueTime : null;
  }
  async transition(ids, change) {
    if (!ids.length) return;
    const tx = this.db.transaction('outbox', 'readwrite'); const done = completed(tx);
    const store = tx.objectStore('outbox');
    for (const id of ids) {
      const req = store.index('id').get(id);
      req.onsuccess = () => { if (req.result) store.put(change(req.result)); else tx.abort(); };
    }
    await done;
  }
  async recover() {
    const tx = this.db.transaction('outbox', 'readwrite'); const done = completed(tx);
    const req = tx.objectStore('outbox').index('stateSeq').openCursor(IDBKeyRange.bound(['IN_FLIGHT', 0], ['IN_FLIGHT', Number.MAX_SAFE_INTEGER]));
    req.onsuccess = () => { const c = req.result; if (c) { c.update({ ...c.value, state: 'PENDING' }); c.continue(); } };
    await done;
  }
  async summary(limit = 50) {
    const tx = this.db.transaction('outbox');
    const q = tx.objectStore('outbox');
    const states = ['PENDING', 'IN_FLIGHT', 'ACKNOWLEDGED', 'BLOCKED'];
    const counts = await Promise.all(states.map(s => result(q.index('stateSeq').count(IDBKeyRange.bound([s, 0], [s, Number.MAX_SAFE_INTEGER])))));
    const records = await new Promise((resolve, reject) => {
      const rows = []; const r = this.db.transaction('outbox').objectStore('outbox').openCursor(null, 'prev');
      r.onerror = () => reject(r.error);
      r.onsuccess = () => { const c = r.result; if (!c || rows.length === limit) return resolve(rows); rows.push(c.value); c.continue(); };
    });
    return { counts: Object.fromEntries(states.map((s, i) => [s, counts[i]])), records };
  }
  close() { this.db?.close(); }
}
