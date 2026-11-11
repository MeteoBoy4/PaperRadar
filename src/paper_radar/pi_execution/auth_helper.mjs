// Product-uid secret boundary. No CLI arguments, loader, provider registration,
// credential copying, logging, JWT parsing or secret-derived hashes.
import { createHash } from 'node:crypto';
import { readFileSync, realpathSync, writeSync } from 'node:fs';
import { join, isAbsolute, relative } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const SOURCE_ID = 'pi-auth-refresh-1.4.0-v1';

// Reviewed static source only; these are never credential-derived hashes.
const API_SOURCES = {
  "dist/core/model-runtime.js": "44d8017928eff6721d5a56b4e71f98bcafb124f5aa6e7d3f016491e11fcf6461",
  "dist/core/auth-storage.js": "59791d54e50bfb86f0bb9e8dcee776547ae1744fc4aeb2fe14ff6610c1f5c567",
  "dist/core/runtime-credentials.js": "2bf389ca2b04bd4dcee56433ca845cd8d9d96d0ccf84d2d0e9ad2a5e3957bda1",
  "../pi-ai/dist/auth/resolve.js": "3fcec09018831324d9c7fb02f4aea707e8a9e4fec5a2bdf1b3d84d716fd3091e",
  "../pi-ai/dist/models.js": "de6323034ca216eefecdfc44dd5c93f22713b34a01f2eb21a6d0a5ce85f9bb19",
  "../pi-ai/dist/auth/helpers.js": "afa67f03895ace888d574c0c86c226cab35521cecc51fe4c0320ba710fb32a97",
  "../pi-ai/dist/providers/openai.js": "9dc3881e858b0280e809ec04b8b17f22580fcb1871da2edf3cfbdfa3c13747b3",
  "../pi-ai/dist/auth/oauth/openai-chatgpt.js": "4cf9fc758a07ffe4ee022326404b5dcc86767ee4154945c0417c7f95eaecdcc2"
};

// Exported only for the offline harness. Production always supplies the original
// public ModelRuntime backed by its concrete DefaultAuthStorage.
export async function resolveAuth(runtime, attemptTimeout, signal) {
  const event = {
    format_version: 1, source_id: SOURCE_ID, pid: process.pid,
    started_at: new Date().toISOString(), completed_at: null, refresh_at: null,
    need_refresh: 'unknown', was_expired_by_pi: 'unknown',
    refresh_called: 'unknown', refresh_succeeded: 'unknown', store_committed: 'unknown',
  };
  let token;
  let calls = 0;
  try {
    // Preserve the old bearer CLI's stored-OAuth type gate, so API-key
    // resolvers (including !command) are never executed by this mode.
    const entries = await runtime.listCredentials({signal});
    if (entries.find(entry => entry.providerId === 'openai')?.type !== 'oauth') throw undefined;
    const provider = runtime.getProvider('openai');
    const oauth = provider?.auth.oauth;
    if (!oauth || runtime.getProvider('openai') !== provider) throw undefined;
    const original = oauth.refresh;
    oauth.refresh = async function (credential, originalSignal) {
      calls += 1;
      const now = Date.now();
      event.refresh_at = new Date(now).toISOString();
      event.need_refresh = true;
      event.was_expired_by_pi = Number.isFinite(credential.expires)
        ? now >= credential.expires : 'unknown';
      event.refresh_called = true;
      const next = await original.call(oauth, credential, originalSignal);
      event.refresh_succeeded = true;
      return next;
    };
    // Exactly the former --min-expiry ceil(attempt_timeout)+600s policy.
    const resolved = await runtime.getAuth('openai', {
      minOAuthValidityMs: (Math.ceil(attemptTimeout) + 600) * 1000, signal,
    });
    if (resolved?.source !== 'OAuth') throw undefined;
    token = resolved.auth?.apiKey;
    if (typeof token !== 'string' || !/^[\x21-\x7e]+$/.test(token) || token.startsWith('sk-')) {
      token = undefined;
      throw undefined;
    }
    if (calls === 1 && event.refresh_succeeded === true) event.store_committed = true;
    else if (calls === 0) event.refresh_called = false;
  } catch {
    // Cancellation can race a continuing refresh/persist. Snapshot only what was
    // observed before getAuth returned; no second getAuth or error serialization.
    token = undefined;
  }
  event.completed_at = new Date().toISOString();
  return { token, metadata: Object.freeze({ ...event }) };
}

export function publicEntry(packageRoot) {
  const root = realpathSync(packageRoot);
  const manifest = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
  const entry = manifest.exports?.['.']?.import;
  if (manifest.name !== '@earendil-works/pi-coding-agent' || manifest.version !== '1.4.0'
      || entry !== './dist/index.js' || manifest.exports['.'].types !== './dist/index.d.ts') {
    throw undefined;
  }
  for (const [name, expected] of Object.entries(API_SOURCES)) {
    if (createHash('sha256').update(readFileSync(join(root, name))).digest('hex') !== expected) {
      throw undefined;
    }
  }
  const target = realpathSync(join(root, entry));
  const inside = relative(root, target);
  if (inside.startsWith('..') || isAbsolute(inside)) throw undefined;
  return pathToFileURL(target).href;
}

async function main() {
  if (process.argv.length !== 2 || process.getuid() === 0) return 2;
  const timeout = Number(process.env.PAPERRADAR_AUTH_ATTEMPT_TIMEOUT);
  const fd = Number(process.env.PAPERRADAR_AUTH_METADATA_FD);
  if (!Number.isFinite(timeout) || timeout <= 0 || !Number.isInteger(fd) || fd < 3) return 2;
  const { ModelRuntime } = await import(publicEntry(process.env.PAPERRADAR_PI_PACKAGE));
  const runtime = await ModelRuntime.create({
    authPath: join(process.env.PI_CODING_AGENT_DIR, 'auth.json'),
    modelsPath: null, refreshOnCreate: false, allowModelNetwork: false,
  });
  const result = await resolveAuth(runtime, timeout);
  // Metadata FD never carries the AuthResult, token, credential or error.
  writeSync(fd, JSON.stringify(result.metadata));
  if (!result.token) return 1;
  writeSync(1, result.token + '\n');
  return 0;
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { process.exitCode = await main(); } catch { process.exitCode = 2; }
}
