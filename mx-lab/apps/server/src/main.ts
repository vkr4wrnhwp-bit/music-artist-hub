import { startTraceServer } from './server';

const port = Number(process.env.PORT ?? 8787);
const dataDir = process.env.TRACE_DATA_DIR ?? new URL('../data', import.meta.url).pathname;

startTraceServer(dataDir, port).then((s) => {
  console.log(`TRACE sync server listening on http://localhost:${s.port}`);
  console.log(`data dir: ${dataDir}`);
  console.log('Auth is DEMO identity issuance — swap /auth/login for a real IdP in production.');
});
