import { BrowserSyncEngine, BatchPolicy, type JsonValue } from '../src/index.js';
type Entry = {kind: string; passed: boolean};
const client = new BrowserSyncEngine<Entry>({validator: p => p.kind.length > 0});
const value: JsonValue = {kind:'inspection', passed:true};
void value; void client.save({kind:'inspection',passed:true});
new BatchPolicy().observe({durationMs:10,full:true,allAcknowledged:true});
