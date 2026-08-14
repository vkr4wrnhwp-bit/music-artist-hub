import { existsSync } from 'node:fs';
import { startTraceServer } from './server';

const port = Number(process.env.PORT ?? 8787);
const dataDir = process.env.TRACE_DATA_DIR ?? new URL('../data', import.meta.url).pathname;

// serve the built one-file app from the same origin when it exists
// (single-service deployments — Render, a pit-lane laptop — need no proxy)
const defaultStatic = new URL('../../web/dist/index.html', import.meta.url).pathname;
const staticHtml = process.env.TRACE_STATIC_FILE ?? (existsSync(defaultStatic) ? defaultStatic : undefined);

startTraceServer(dataDir, port, staticHtml).then((s) => {
  console.log(`TRACE sync server listening on http://localhost:${s.port}`);
  console.log(`data dir: ${dataDir}`);
  console.log(staticHtml ? `serving app from: ${staticHtml}` : 'API only (no built app found — npm run build to serve it here)');
  console.log('Auth: scrypt passwords, first sign-in sets them. Deploy behind TLS; an IdP for SSO swaps in at /auth/login.');
});
