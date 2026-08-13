import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import {
  createSeededDb, LocalStoragePort, type Action, type Db, type User, can,
} from '@mxlab/domain';
import { maybeAutoSync } from './syncClient';

interface AppState {
  db: Db;
  user: User | null;
  version: number;
  tutor: boolean;
  signIn(userId: string): void;
  signOut(): void;
  setTutor(on: boolean): void;
  /** apply a mutation to the db, persist, re-render */
  update(fn: (db: Db) => void): void;
  allowed(action: Action): boolean;
  resetDemo(): void;
}

const Ctx = createContext<AppState>(null as unknown as AppState);
const port = new LocalStoragePort();

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [db, setDb] = useState<Db>(() => port.load() ?? createSeededDb());
  const [userId, setUserId] = useState<string | null>(
    () => localStorage.getItem('mx-lab-user'),
  );
  const [version, setVersion] = useState(0);
  const [tutor, setTutorState] = useState(() => localStorage.getItem('mx-lab-tutor') === '1');

  const update = useCallback((fn: (db: Db) => void) => {
    fn(db);
    port.save(db);
    setVersion((v) => v + 1);
    // opportunistic background sync when the team server is configured
    maybeAutoSync(db, () => { port.save(db); setVersion((v) => v + 1); });
  }, [db]);

  const signIn = useCallback((id: string) => {
    setUserId(id);
    localStorage.setItem('mx-lab-user', id);
  }, []);
  const signOut = useCallback(() => {
    setUserId(null);
    localStorage.removeItem('mx-lab-user');
  }, []);
  const setTutor = useCallback((on: boolean) => {
    setTutorState(on);
    localStorage.setItem('mx-lab-tutor', on ? '1' : '0');
  }, []);
  const resetDemo = useCallback(() => {
    const fresh = createSeededDb();
    port.save(fresh);
    setDb(fresh);
    setVersion((v) => v + 1);
  }, []);

  const user = db.users.find((u) => u.id === userId) ?? null;
  const allowed = useCallback(
    (action: Action) => (user ? can(user.role, action) : false),
    [user],
  );

  const value = useMemo<AppState>(() => ({
    db, user, version, tutor, signIn, signOut, setTutor, update, allowed, resetDemo,
  }), [db, user, version, tutor, signIn, signOut, setTutor, update, allowed, resetDemo]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  return useContext(Ctx);
}

/** minimal hash router */
export function useRoute(): string[] {
  const [hash, setHash] = useState(() => window.location.hash);
  React.useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return hash.replace(/^#\/?/, '').split('/').filter(Boolean);
}

export function nav(path: string): void {
  window.location.hash = path;
}
