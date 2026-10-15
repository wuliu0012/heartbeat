import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
globalThis.document = {hidden: false, addEventListener() {}, removeEventListener() {}};
globalThis.window = {addEventListener() {}, removeEventListener() {}};
const source = await readFile(new URL('../frontend/heartbeat-client.js', import.meta.url), 'utf8');
const {createHeartbeat} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const current = {id: 'demo', history: [{role: 'ai', content: 'unselected', versions: ['unselected', 'selected'], verIdx: 1}]};
let calls = [], persisted = false, failSave = false;
globalThis.fetch = async (url, options) => {
  calls.push({url, options});
  if (url.endsWith('/ack')) assert(persisted, 'Cannot ACK before local persistence');
  return {ok: true, json: async () => url.endsWith('/sync') ? {generation: 'g'} : {conversation_id: current.id, generation: 'g', entries: [{id: 'one', conversation_id: current.id, generation: 'g', content: 'synthetic'}]}};
};
const errors = [];
const client = createHeartbeat({getToken: () => 'synthetic-token', getSnapshot: () => current,
  onEntries: async (entries, isCurrent) => { assert(isCurrent()); if (failSave) return false; persisted = true; }, onError: code => errors.push(code)});
assert(await client.poll());
assert.equal(JSON.parse(calls[0].options.body).history[0].content, 'selected');
assert(!JSON.parse(calls[0].options.body).cfg);
persisted = false; failSave = true; calls = [];
assert.equal(await client.poll(), false); assert(!calls.some(c => c.url.endsWith('/ack'))); assert(errors.includes('storage'));
for (const [status, expected] of [[401, 'auth'], [403, 'origin'], [400, 'data']]) {
  globalThis.fetch = async () => ({ok: false, status});
  await client.sync(); assert.equal(errors.at(-1), expected);
}
const count = errors.length;
globalThis.fetch = async () => ({ok: false, status: 409});
await client.sync(); assert.equal(errors.length, count);
for (const base of ['//other.invalid', '/\\other.invalid', 'https://other.invalid', '/%2fevil']) {
  assert.throws(() => createHeartbeat({base}));
}
globalThis.fetch = async () => { throw new TypeError('synthetic network failure'); };
await client.sync(); await client.sync(); await client.sync(); assert.equal(errors.at(-1), 'network');
client.stop();
console.log('PASS selected version, server-only config, persistence before ACK, error classification, same-origin path restriction');
