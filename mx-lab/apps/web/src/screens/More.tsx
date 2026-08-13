import React from 'react';
import { DIRECT_WRITE_LABEL } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Panel, Pill } from '../ui';

/** MORE — everything that doesn't need to be in your hand on race day. */
export function MoreScreen() {
  const { db, user, tutor, setTutor } = useApp();
  if (!user) return null;

  const items: Array<{ title: string; desc: string; to: string; badge?: React.ReactNode }> = [
    { title: 'Team Sync', desc: 'Self-hosted persistence server — durable shared database, conflict review, telemetry archive', to: 'sync' },
    { title: 'TRACE Knowledge & Ask TRACE', desc: 'Team memory with citations — search everything, ask structured questions', to: 'knowledge', badge: <Pill tone="warning">DEVELOPMENT</Pill> },
    { title: 'Live Pit Board', desc: 'Large-format team display for the transporter or pit wall', to: 'pitboard' },
    { title: 'Crew assignments', desc: 'Race-day tasks: assigned → in progress → verified', to: 'crew' },
    { title: 'Morning Brief', desc: 'Generated from live readiness, component life, and test plans', to: 'brief' },
    { title: 'Remote tuner access & marketplace', desc: 'Server-enforced scoped grants, minted access tokens · marketplace architecture', to: 'access', badge: <Pill tone="warning">MARKETPLACE SHELL</Pill> },
    { title: 'Hardware & devices', desc: 'MX Nodes, channel health, calibration, competition mode', to: 'hardware', badge: <Pill tone="sim">SIMULATED</Pill> },
    { title: 'CNC program', desc: 'Enclosures, mounts, dock, fixtures — part registry and briefs', to: 'cnc' },
    { title: 'Reports & team archive', desc: 'Printable reports, JSON/CSV exports, offline backup', to: 'reports' },
    { title: 'Audit history', desc: 'Append-only record of every decision and transfer', to: 'audit' },
    { title: 'Register a bike', desc: 'Phase 0 inventory for a new machine', to: 'bike/new' },
  ];

  return (
    <div>
      <div className="page-title">
        <h1>More</h1>
        <span className="sub">{db.org.name}</span>
      </div>
      <div className="cols">
        <div>
          {items.map((it) => (
            <button key={it.to} className="finding" style={{ width: '100%', textAlign: 'left', cursor: 'pointer' }} onClick={() => nav(it.to)}>
              <div style={{ flex: 1 }}>
                <h4>{it.title} {it.badge}</h4>
                <p>{it.desc}</p>
              </div>
              <span style={{ color: 'var(--muted)' }}>→</span>
            </button>
          ))}
        </div>
        <div>
          <Panel title="Team & roles">
            <div className="tbl-scroll">
              <table className="data">
                <tbody>
                  {db.users.map((u) => (
                    <tr key={u.id}>
                      <td style={{ fontWeight: u.id === user.id ? 700 : 400 }}>{u.name}{u.id === user.id ? ' (you)' : ''}</td>
                      <td className="mono" style={{ color: 'var(--muted)' }}>{u.role.replaceAll('_', ' ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="hint">Role changes and invitations arrive with the production backend; permissions are already enforced per role.</p>
          </Panel>
          <Panel title="Preferences">
            <label style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 14 }}>
              <input type="checkbox" checked={tutor} onChange={(e) => setTutor(e.target.checked)} />
              Tutor Mode — contextual explanations on key screens
            </label>
          </Panel>
          <Panel title="Safety">
            <div className="write-disabled">{DIRECT_WRITE_LABEL}</div>
            <p className="hint" style={{ marginTop: 10 }}>
              Phase 1 never writes to an ECU. Map changes travel through the companion workflow and are
              confirmed by a person. Full policy: docs/safety/safety-boundary.md.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
