// Offline only: explicit fixed Node/package paths supplied by the developer.
// All credentials, refresh methods and backing I/O below are synthetic.
import assert from 'node:assert/strict';
import { resolveAuth, publicEntry } from '../src/paper_radar/pi_execution/auth_helper.mjs';
const { ModelRuntime } = await import(publicEntry(process.argv[2]));
let count = 0;
for (const mode of ['fresh', 'refresh', 'expired', 'race', 'refresh-fail', 'persist-fail',
                    'short', 'derive-fail', 'cancel']) {
  const original = {type: 'oauth', expires: Date.now() + (mode === 'fresh' ? 3600000 : mode === 'expired' ? -1 : 600000)};
  Object.defineProperty(original, 'access', {get() { throw new Error('opaque credential must not be inspected'); }});
  let current = original, committed = false, locked = false, calls = 0;
  const abort = new AbortController();
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const store = {
    async read() { return current; }, async list() { return [{providerId:'openai',type:'oauth'}]; }, async delete() {},
    async modify(provider, fn) {
      assert.equal(provider, 'openai'); locked = true;
      if (mode === 'race') current = {type: 'oauth', expires: Date.now() + 3600000};
      try {
        const next = await fn(current);
        if (mode === 'persist-fail') throw new Error('secret synthetic error');
        if (next) {current = next; committed = true;}
        return current;
      } finally {locked = false;}
    },
  };
  const runtime = await ModelRuntime.create({credentials: store, modelsPath: null,
    refreshOnCreate: false, allowModelNetwork: false});
  const oauth = runtime.getProvider('openai').auth.oauth;
  oauth.refresh = async (credential, signal) => {
    assert.equal(locked, true); assert.equal(credential, original);
    assert.notEqual(signal, abort.signal); calls++;
    if (mode === 'refresh-fail') throw new Error('secret synthetic response');
    if (mode === 'cancel') {abort.abort(); await pending;}
    return {type: 'oauth', expires: Date.now() + (mode === 'short' ? 500000 : 3600000)};
  };
  oauth.toAuth = async () => {
    if (mode === 'derive-fail') throw new Error('secret synthetic token');
    return {apiKey: 'synthetic-bearer'};
  };
  const result = await resolveAuth(runtime, 300, abort.signal);
  const event = result.metadata;
  assert.equal(event.source_id, 'pi-auth-refresh-1.4.0-v1');
  assert.equal(JSON.stringify(event).includes('secret'), false);
  assert.equal('expires' in event, false);
  if (['fresh','race'].includes(mode)) {
    assert.equal(event.refresh_called, false); assert.equal(event.need_refresh, 'unknown');
    assert.equal(event.store_committed, 'unknown'); assert.equal(calls, 0);
  } else if (['refresh','expired'].includes(mode)) {
    assert.equal(event.store_committed, true); assert.equal(committed, true);
    assert.equal(event.was_expired_by_pi, mode === 'expired');
    assert.equal(result.token, 'synthetic-bearer'); assert.equal(calls, 1);
  } else {
    assert.equal(event.store_committed, 'unknown'); assert.equal(result.token, undefined);
    assert.equal(event.refresh_called, true);
    if (mode !== 'refresh-fail' && mode !== 'cancel') assert.equal(event.refresh_succeeded, true);
  }
  if (mode === 'cancel') {
    release(); await new Promise(resolve => setTimeout(resolve, 10));
    assert.equal(committed, true); assert.equal(event.store_committed, 'unknown');
    assert.equal(event.refresh_succeeded, 'unknown'); // snapshot cannot mutate later
  }
  count++;
}
console.log(`offline public ModelRuntime harness: ${count} scenarios passed`);

// Run the actual executable entry with the original concrete file store and
// original provider toAuth. A long-lived synthetic OAuth credential guarantees
// no refresh/network; the fake-store cases above exercise the refresh branch.
const {mkdtempSync, writeFileSync, rmSync} = await import('node:fs');
const {tmpdir} = await import('node:os');
const {join} = await import('node:path');
const {spawnSync} = await import('node:child_process');
const directory = mkdtempSync(join(tmpdir(), 'paperradar-auth-harness-'));
try {
  writeFileSync(join(directory,'auth.json'), JSON.stringify({openai: {
    type: 'oauth', access: 'synthetic-main-bearer', refresh: 'synthetic-refresh',
    expires: Date.now() + 3600000,
  }}), {mode: 0o600});
  const helper = new URL('../src/paper_radar/pi_execution/auth_helper.mjs', import.meta.url);
  const env = {PI_CODING_AGENT_DIR: directory, HOME: directory, TMPDIR: directory,
    PI_SKIP_VERSION_CHECK:'1', PI_TELEMETRY:'0', PAPERRADAR_PI_PACKAGE:process.argv[2],
    PAPERRADAR_AUTH_ATTEMPT_TIMEOUT:'300', PAPERRADAR_AUTH_METADATA_FD:'3'};
  const child = spawnSync(process.execPath, [helper.pathname], {
    cwd:directory, env, stdio:['ignore','pipe','pipe','pipe'], timeout:10000,
  });
  assert.equal(child.status,0); assert.equal(child.stderr.length,0);
  assert.equal(child.stdout.toString(),'synthetic-main-bearer\n');
  const metadata = JSON.parse(child.output[3].toString());
  assert.equal(metadata.refresh_called,false);
  assert.equal(metadata.store_committed,'unknown');
  assert.equal(child.output[3].toString().includes('synthetic-main-bearer'),false);
  const refused = spawnSync(process.execPath,[helper.pathname,'arbitrary'],{
    cwd:directory,env,stdio:['ignore','pipe','pipe','pipe'],timeout:10000,
  });
  assert.equal(refused.status,2); assert.equal(refused.stdout.length,0);
  assert.equal(refused.stderr.length,0); assert.equal(refused.output[3].length,0);
  console.log('offline sealed main entry: concrete synthetic file store and separate FDs passed');
} finally {rmSync(directory,{recursive:true,force:true});}

{
  let called = false;
  const result = await resolveAuth({
    async listCredentials() {return [{providerId:'openai',type:'api_key'}];},
    getProvider() {called=true; throw new Error('must not inspect API key');},
    async getAuth() {called=true; throw new Error('must not execute !command');},
  },300);
  assert.equal(called,false); assert.equal(result.token,undefined);
  assert.equal(result.metadata.refresh_called,'unknown');
  console.log('offline non-OAuth gate: no API-key resolver execution');
}
