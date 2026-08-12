import React from 'react';
import { DEMO_BANNER } from '@mxlab/domain';
import { AppProvider, nav, useApp, useRoute } from './state';
import { Panel, Pill } from './ui';
import { Garage } from './screens/Garage';
import { BikeProfile } from './screens/BikeProfile';
import { EcuProfile } from './screens/EcuProfile';
import { MapLibrary, MapWorkspace } from './screens/MapsScreen';
import { TransferSheet } from './screens/Companion';
import { NewSession } from './screens/NewSession';
import { SessionDetail } from './screens/SessionDetail';
import { Engineer } from './screens/Engineer';
import { StartLab } from './screens/StartLab';
import { CncModule, Hardware } from './screens/Hardware';
import { AuditScreen, Reports } from './screens/Reports';
import { RegisterBike } from './screens/RegisterBike';

function SignIn() {
  const { db, signIn } = useApp();
  return (
    <div className="wrap" style={{ maxWidth: 560 }}>
      <div style={{ textAlign: 'center', margin: '48px 0 24px' }}>
        <div className="brand" style={{ fontSize: 26 }}>MX<span style={{ color: 'var(--accent)' }}>/</span>LAB</div>
        <p className="hint">Vortex-first race engineering — Phase 1 (simulation)</p>
      </div>
      <Panel title="Sign in (simulated demo accounts)">
        <p className="hint" style={{ marginBottom: 10 }}>
          Production uses real authentication behind the same permission matrix (see docs/architecture).
          Pick a role to explore what that person can and cannot do.
        </p>
        {db.users.map((u) => (
          <button key={u.id} className="btn" style={{ display: 'flex', width: '100%', justifyContent: 'space-between', marginBottom: 6 }}
            onClick={() => signIn(u.id)}>
            <span>{u.name}</span>
            <span className="mono" style={{ color: 'var(--muted)' }}>{u.role.replaceAll('_', ' ')}</span>
          </button>
        ))}
      </Panel>
    </div>
  );
}

function Shell() {
  const { db, user, signOut, tutor, setTutor, resetDemo } = useApp();
  const route = useRoute();

  if (!user) return <><div className="sim-banner">{DEMO_BANNER}</div><SignIn /></>;

  const [head, arg] = route.length ? route : ['garage'];
  const links: Array<[string, string]> = [
    ['garage', 'Garage'], ['maps', 'Maps'], ['session/new', 'New session'],
    ['engineer', 'Race Engineer'], ['starts', 'Start Lab'], ['hardware', 'Hardware'],
    ['cnc', 'CNC'], ['reports', 'Reports'], ['audit', 'Audit'],
  ];

  let screen: React.ReactNode;
  if (head === 'garage' || head === undefined) screen = <Garage />;
  else if (head === 'bike' && arg === 'new') screen = <RegisterBike />;
  else if (head === 'bike' && arg) screen = <BikeProfile bikeId={arg} />;
  else if (head === 'ecu' && arg) screen = <EcuProfile ecuDefId={arg} />;
  else if (head === 'maps' && arg) screen = <MapWorkspace revId={arg} />;
  else if (head === 'maps') screen = <MapLibrary />;
  else if (head === 'transfer' && arg) screen = <TransferSheet revId={arg} />;
  else if (head === 'session' && arg === 'new') screen = <NewSession />;
  else if (head === 'session' && arg) screen = <SessionDetail sessionId={arg} />;
  else if (head === 'engineer') screen = <Engineer initialId={arg} />;
  else if (head === 'starts') screen = <StartLab />;
  else if (head === 'hardware') screen = <Hardware />;
  else if (head === 'cnc') screen = <CncModule />;
  else if (head === 'reports') screen = <Reports />;
  else if (head === 'audit') screen = <AuditScreen />;
  else screen = <Garage />;

  const activeKey = head === 'session' && arg === 'new' ? 'session/new'
    : head === 'bike' || head === 'ecu' ? 'garage'
      : head === 'transfer' ? 'maps' : head;

  return (
    <>
      <div className="sim-banner">{DEMO_BANNER}</div>
      <header className="app no-print">
        <div className="app-inner">
          <a href="#/garage" style={{ textDecoration: 'none', color: 'inherit' }}>
            <span className="brand">MX<span style={{ color: 'var(--accent)' }}>/</span>LAB<small>{db.org.name}</small></span>
          </a>
          <nav className="main">
            {links.map(([path, label]) => (
              <a key={path} href={`#/${path}`} className={activeKey === path.split('/')[0] && (path !== 'session/new' || (head === 'session' && arg === 'new')) ? 'active' : activeKey === path ? 'active' : ''}>
                {label}
              </a>
            ))}
          </nav>
          <div className="userbox">
            <label style={{ display: 'flex', gap: 4, alignItems: 'center', fontSize: 12.5, color: 'var(--muted)' }}>
              <input type="checkbox" checked={tutor} onChange={(e) => setTutor(e.target.checked)} /> Tutor
            </label>
            <Pill tone="neutral">{user.name} · {user.role.replaceAll('_', ' ')}</Pill>
            <button className="btn small" onClick={signOut}>Switch user</button>
          </div>
        </div>
      </header>
      <main className="wrap">{screen}</main>
      <footer className="app no-print">
        <span>MX LAB Phase 1 — offline-first; all data stays in this browser.</span>
        <span>No ECU write paths exist in this build.</span>
        <button className="btn small" onClick={() => { if (confirm('Reset all demo data to the seeded state?')) { resetDemo(); nav('garage'); } }}>
          Reset demo data
        </button>
      </footer>
    </>
  );
}

export function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
