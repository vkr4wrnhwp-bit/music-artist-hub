import React, { useEffect, useState } from 'react';
import { DEMO_BANNER, searchAll } from '@mxlab/domain';
import { AppProvider, nav, useApp, useRoute } from './state';
import { AreaIcon, CommandPalette, Panel, Pill, TraceIcon, TraceLogo } from './ui';
import { Today } from './screens/Today';
import { Garage } from './screens/Garage';
import { BikeProfile } from './screens/BikeProfile';
import { EcuProfile } from './screens/EcuProfile';
import { MapLibrary, MapWorkspace } from './screens/MapsScreen';
import { TransferSheet } from './screens/Companion';
import { NewSession } from './screens/NewSession';
import { SessionDetail } from './screens/SessionDetail';
import { SessionsHome } from './screens/SessionsHome';
import { Engineer } from './screens/Engineer';
import { StartLab } from './screens/StartLab';
import { CncModule, Hardware } from './screens/Hardware';
import { AuditScreen, Reports } from './screens/Reports';
import { RegisterBike } from './screens/RegisterBike';
import { AnalyzeHub } from './screens/Analyze';
import { MoreScreen } from './screens/More';
import { PitMode } from './screens/PitMode';
import { CompareWorkspace } from './screens/Compare';
import { Planner } from './screens/Planner';
import { KnowledgeScreen } from './screens/Knowledge';
import { IntelligenceScreen } from './screens/Intelligence';
import { RidersScreen } from './screens/Riders';
import {
  AccessScreen, BriefScreen, CrewScreen, DebriefScreen, PitBoard, WeekendScreen,
} from './screens/RaceOps';

const AREAS = [
  { id: 'garage', label: 'Garage', path: 'garage' },
  { id: 'sessions', label: 'Sessions', path: 'sessions' },
  { id: 'tune', label: 'Tune', path: 'tune' },
  { id: 'analyze', label: 'Analyze', path: 'analyze' },
  { id: 'more', label: 'More', path: 'more' },
] as const;

/** which area owns each route head */
const AREA_OF: Record<string, string> = {
  garage: 'garage', fleet: 'garage', bike: 'garage', ecu: 'garage',
  sessions: 'sessions', session: 'sessions', starts: 'sessions', planner: 'sessions',
  weekend: 'sessions', debrief: 'sessions',
  tune: 'tune', maps: 'tune', transfer: 'tune',
  analyze: 'analyze', engineer: 'analyze', compare: 'analyze', intelligence: 'analyze', riders: 'analyze',
  more: 'more', hardware: 'more', cnc: 'more', reports: 'more', audit: 'more', pit: 'more',
  knowledge: 'more', pitboard: 'more', crew: 'more', brief: 'more', access: 'more',
};

const SUBNAV: Record<string, Array<[string, string]>> = {
  garage: [['garage', 'Today'], ['fleet', 'Fleet']],
  sessions: [['sessions', 'Overview'], ['session/new', 'New session'], ['planner', 'Test Planner'], ['weekend', 'Race Weekend'], ['starts', 'Start Lab'], ['debrief', 'Debrief'], ['pit', 'Pit Mode']],
  tune: [['tune', 'Map library']],
  analyze: [['analyze', 'Findings'], ['compare', 'Compare'], ['intelligence', 'Intelligence'], ['riders', 'Riders'], ['engineer', 'TRACE Insights'], ['reports', 'Reports']],
  more: [['more', 'Overview'], ['knowledge', 'Knowledge'], ['pitboard', 'Pit Board'], ['crew', 'Crew'], ['brief', 'Brief'], ['audit', 'Audit']],
};

function SignIn() {
  const { db, signIn } = useApp();
  return (
    <div className="wrap" style={{ maxWidth: 480, margin: '0 auto', padding: '0 20px' }}>
      <div style={{ textAlign: 'center', margin: '64px 0 10px' }}>
        <TraceIcon size={64} />
        <div className="wordmark" style={{ fontSize: 30, display: 'block', marginTop: 10 }}>TRACE</div>
        <p style={{ color: 'var(--muted)', fontSize: 11.5, letterSpacing: '0.28em', textTransform: 'uppercase', margin: '8px 0 0' }}>
          Telemetry &amp; Tuning Platform
        </p>
        <p className="hint" style={{ marginTop: 18 }}>Phase 1 · simulation · pick a demo role to sign in</p>
      </div>
      <Panel>
        {db.users.map((u) => (
          <button
            key={u.id} className="btn"
            style={{ display: 'flex', width: '100%', justifyContent: 'space-between', marginBottom: 8, background: 'var(--raised)' }}
            onClick={() => signIn(u.id)}
          >
            <span>{u.name}</span>
            <span className="mono" style={{ color: 'var(--muted)', fontSize: 12 }}>{u.role.replaceAll('_', ' ')}</span>
          </button>
        ))}
      </Panel>
      <p className="hint" style={{ textAlign: 'center' }}>
        Production uses real authentication behind this same permission matrix.
      </p>
    </div>
  );
}

function Shell() {
  const { db, user, signOut, tutor, setTutor, resetDemo } = useApp();
  const route = useRoute();
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!user) return <><div className="sim-banner">{DEMO_BANNER}</div><SignIn /></>;

  const [head, arg, arg2] = route.length ? route : ['garage'];
  const area = AREA_OF[head] ?? 'garage';

  let screen: React.ReactNode;
  if (head === 'garage' || head === undefined) screen = <Today />;
  else if (head === 'fleet') screen = <Garage />;
  else if (head === 'bike' && arg === 'new') screen = <RegisterBike />;
  else if (head === 'bike' && arg) screen = <BikeProfile bikeId={arg} />;
  else if (head === 'ecu' && arg) screen = <EcuProfile ecuDefId={arg} />;
  else if (head === 'sessions') screen = <SessionsHome />;
  else if (head === 'session' && arg === 'new') screen = <NewSession />;
  else if (head === 'session' && arg) screen = <SessionDetail sessionId={arg} initialTab={arg2} />;
  else if (head === 'starts') screen = <StartLab />;
  else if (head === 'tune') screen = <MapLibrary />;
  else if (head === 'maps' && arg) screen = <MapWorkspace revId={arg} />;
  else if (head === 'maps') screen = <MapLibrary />;
  else if (head === 'transfer' && arg) screen = <TransferSheet revId={arg} />;
  else if (head === 'analyze') screen = <AnalyzeHub />;
  else if (head === 'engineer') screen = <Engineer initialId={arg} />;
  else if (head === 'compare') screen = <CompareWorkspace aId={arg} bId={arg2} />;
  else if (head === 'planner') screen = <Planner />;
  else if (head === 'knowledge') screen = <KnowledgeScreen />;
  else if (head === 'intelligence') screen = <IntelligenceScreen />;
  else if (head === 'riders') screen = <RidersScreen />;
  else if (head === 'weekend') screen = <WeekendScreen />;
  else if (head === 'pitboard') screen = <PitBoard />;
  else if (head === 'crew') screen = <CrewScreen />;
  else if (head === 'brief') screen = <BriefScreen />;
  else if (head === 'debrief') screen = <DebriefScreen />;
  else if (head === 'access') screen = <AccessScreen />;
  else if (head === 'more') screen = <MoreScreen />;
  else if (head === 'hardware') screen = <Hardware />;
  else if (head === 'cnc') screen = <CncModule />;
  else if (head === 'reports') screen = <Reports />;
  else if (head === 'audit') screen = <AuditScreen />;
  else if (head === 'pit') screen = <PitMode />;
  else screen = <Today />;

  // Pit Mode: minimal chrome by design
  if (head === 'pit') {
    return (
      <>
        <div className="sim-banner">{DEMO_BANNER}</div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', maxWidth: 980, margin: '0 auto' }}>
          <TraceLogo />
          <button className="btn small ghost no-print" onClick={() => nav('sessions')}>Exit Pit Mode</button>
        </div>
        <main className="wrap" style={{ paddingTop: 0 }}>{screen}</main>
      </>
    );
  }

  const sub = SUBNAV[area] ?? [];
  const activeSub = (path: string) => {
    if (path === 'session/new') return head === 'session' && arg === 'new';
    if (path === 'engineer') return head === 'engineer';
    return head === path.split('/')[0] && (path !== 'garage' || head === 'garage');
  };

  return (
    <>
      <div className="sim-banner">{DEMO_BANNER}</div>
      <header className="app no-print">
        <div className="app-inner">
          <a href="#/garage" style={{ textDecoration: 'none', color: 'inherit' }} aria-label="TRACE home">
            <TraceLogo />
          </a>
          <nav className="main" aria-label="Primary">
            {AREAS.map((a) => (
              <a key={a.id} href={`#/${a.path}`} className={area === a.id ? 'active' : ''}>{a.label}</a>
            ))}
          </nav>
          <div className="userbox">
            <button className="btn small ghost" onClick={() => setPaletteOpen(true)} aria-label="Search (Ctrl+K)" title="Search everything (Ctrl+K)">
              ⌕ <span className="rolechip" style={{ color: 'var(--muted)', fontSize: 11 }}>⌘K</span>
            </button>
            <label style={{ display: 'flex', gap: 5, alignItems: 'center', cursor: 'pointer' }}>
              <input type="checkbox" checked={tutor} onChange={(e) => setTutor(e.target.checked)} style={{ width: 14, height: 14 }} /> Tutor
            </label>
            <span className="rolechip"><Pill tone="neutral">{user.name} · {user.role.replaceAll('_', ' ')}</Pill></span>
            <button className="btn small ghost" onClick={signOut}>Switch user</button>
          </div>
        </div>
      </header>

      <main className="wrap">
        {sub.length > 1 && (
          <div className="subnav no-print" aria-label="Section">
            {sub.map(([path, label]) => (
              <a key={path} href={`#/${path}`} className={activeSub(path) ? 'active' : ''}>{label}</a>
            ))}
          </div>
        )}
        {screen}
      </main>

      <nav className="tabbar no-print" aria-label="Primary">
        {AREAS.map((a) => (
          <a key={a.id} href={`#/${a.path}`} className={area === a.id ? 'active' : ''}>
            <AreaIcon area={a.id} />
            {a.label}
          </a>
        ))}
      </nav>

      {paletteOpen && <CommandPalette search={(q) => searchAll(db, q)} onClose={() => setPaletteOpen(false)} />}

      <footer className="app no-print">
        <span>TRACE Phase 1 — offline-first; all data stays on this device.</span>
        <span>No ECU write paths exist in this build.</span>
        <button className="btn small ghost" onClick={() => { if (confirm('Reset all demo data to the seeded state?')) { resetDemo(); nav('garage'); } }}>
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
