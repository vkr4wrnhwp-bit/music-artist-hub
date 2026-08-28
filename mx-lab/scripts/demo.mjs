#!/usr/bin/env node
/**
 * One-command local demo: the built single-file app plus the sync server.
 *   npm run demo
 * App:  http://localhost:8080   (build output, offline-capable)
 * Sync: http://localhost:8787   (self-hosted persistence backend)
 */
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const distIndex = join(root, 'apps/web/dist/index.html');
if (!existsSync(distIndex)) {
  console.error('No build found — run `npm run build` first (or `npm run demo` via the package script, which builds).');
  process.exit(1);
}

const APP_PORT = Number(process.env.APP_PORT ?? 8080);
const SYNC_PORT = Number(process.env.PORT ?? 8787);

const app = createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(readFileSync(distIndex));
});
app.listen(APP_PORT, () => {
  console.log(`TRACE app     → http://localhost:${APP_PORT}`);
});

const server = spawn('npx', ['tsx', join(root, 'apps/server/src/main.ts')], {
  stdio: 'inherit',
  env: { ...process.env, PORT: String(SYNC_PORT) },
});
server.on('exit', (code) => process.exit(code ?? 0));
process.on('SIGINT', () => { server.kill('SIGINT'); app.close(); });

console.log('\nSign in (first sign-in sets your password), then More → Team Sync to connect.');
