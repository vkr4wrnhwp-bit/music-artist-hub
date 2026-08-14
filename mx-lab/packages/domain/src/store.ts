import type { Db } from './types';

/**
 * Storage port. Phase 1 persists the metadata DB locally (offline-first at
 * the track). Production backend (Firebase Auth + Firestore metadata + object
 * storage for telemetry chunks) plugs in behind this same port — see
 * docs/architecture/overview.md. High-rate telemetry never lives here.
 */
export interface StoragePort {
  load(): Db | null;
  save(db: Db): void;
}

export const SCHEMA_VERSION = 2; // v2: TRACE expansion (test plans, twin, knowledge, race ops)
const LS_KEY = 'mx-lab-db-v1';

/** additive fields default in place so older stored v2 databases keep loading */
export function applyDbDefaults(db: Db): Db {
  if (!db.importedTraces) db.importedTraces = {};
  return db;
}

export class LocalStoragePort implements StoragePort {
  load(): Db | null {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
      const db = JSON.parse(raw) as Db;
      if (db.schemaVersion !== SCHEMA_VERSION) return null; // future: migrations
      return applyDbDefaults(db);
    } catch {
      return null;
    }
  }
  save(db: Db): void {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(db));
    } catch {
      // quota/private mode — app continues in-memory; sync queue holds changes
    }
  }
}

export class MemoryStoragePort implements StoragePort {
  private db: Db | null = null;
  load(): Db | null { return this.db ? (JSON.parse(JSON.stringify(this.db)) as Db) : null; }
  save(db: Db): void { this.db = JSON.parse(JSON.stringify(db)) as Db; }
}

export function exportDb(db: Db): string {
  return JSON.stringify({ exportedAt: new Date().toISOString(), db }, null, 2);
}

export function importDb(json: string): Db {
  const parsed = JSON.parse(json) as { db?: Db };
  const db = parsed.db ?? (parsed as unknown as Db);
  if (!db || db.schemaVersion !== SCHEMA_VERSION || !Array.isArray(db.bikes)) {
    throw new Error('Not a valid MX LAB archive (schema mismatch).');
  }
  return applyDbDefaults(db);
}
