import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import assert from 'node:assert/strict';
import { canonicalPayload, createOperation } from '../src/index.js';
const values=[null,false,0,'',{'2':false,'10':null,'\ue000':[1,'12.50'],'𝄞':'اطلاعات'}, {nested:{items:[true,null,9007199254740991]}}];
const id='12345678-1234-4234-8234-123456789abc';
const python=process.env.PYTHON || (existsSync('.venv/Scripts/python.exe')?'.venv/Scripts/python.exe':existsSync('.venv/bin/python')?'.venv/bin/python':'python');
const code=`import sys,json\nfrom lss_sync import canonical_payload,make_operation\nfrom lss_sync.backend import ReceiptStore\nimport tempfile,pathlib\ndata=json.load(sys.stdin)\nwith tempfile.TemporaryDirectory() as d:\n s=ReceiptStore(pathlib.Path(d)/'server.sqlite3')\n results=[]\n for item in data:\n  op=item['operation']\n  a=s.apply(op,namespace='test');b=s.apply(op,namespace='test')\n  assert a==b\n  results.append({'canonical':canonical_payload(item['value']),'operation':make_operation(item['value'],operation_id=op['id'])})\n print(json.dumps(results,ensure_ascii=False))`;
const input=[];for(const value of values)input.push({value,operation:await createOperation(value,id)});
// Use independent namespaces/databases for different payloads sharing a fixture ID.
for(const item of input){
 const r=spawnSync(python,['-c',code],{input:JSON.stringify([item]),encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}});
 if(r.status!==0)throw new Error(r.stderr);
 const [result]=JSON.parse(r.stdout);assert.equal(result.canonical,canonicalPayload(item.value));assert.deepEqual(result.operation,item.operation);
}
console.log(`PASS ${values.length} cross-language canonical payload, digest, receipt and replay cases`);


