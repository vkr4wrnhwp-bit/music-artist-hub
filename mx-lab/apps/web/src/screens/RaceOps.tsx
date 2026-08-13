import React, { useState } from 'react';
import {
  appendAudit, buildChecklist, computeReadiness, dayTimeline, draftDebrief,
  grantIsActive, morningBrief,
} from '@mxlab/domain';
import { nav, useApp } from '../state';
import { EmptyState, Help, Panel, Pill, readinessTone } from '../ui';

// ------------------------------------------------------------- race weekend

export function WeekendScreen() {
  const { db, user, update } = useApp();
  const event = db.events[0];
  const [noteDate, setNoteDate] = useState(event?.days[1]?.date ?? '2026-08-15');
  if (!event) return <EmptyState title="No race events yet" />;
  const track = db.tracks.find((t) => t.id === event.trackId);

  return (
    <div>
      <div className="page-title">
        <h1>{event.name}</h1>
        <span className="sub">{track?.name}</span>
        <Pill tone="sim">SIMULATED EVENT</Pill>
      </div>
      <Help id="weekend">
        Every slot inherits event, track, bike, and conditions. The weekend view shows how the setup
        evolved from Friday to the motos — the story a season is made of.
      </Help>
      <div className="cols-3">
        {event.days.map((day) => (
          <Panel key={day.date} title={day.label}>
            {day.slots.map((slot, i) => {
              const s = db.sessions.find((x) => x.id === slot.sessionId);
              const rev = s ? db.mapRevisions.find((r) => r.id === s.setupSnapshot.mapRevisionId) : null;
              return (
                <div key={i} style={{ background: 'var(--raised)', borderRadius: 10, padding: '10px 14px', marginBottom: 8 }}>
                  <p style={{ margin: 0, fontWeight: 650 }}>{slot.label}</p>
                  {s ? (
                    <p className="hint" style={{ margin: '2px 0 0' }}>
                      <a href={`#/session/${s.id}`}>{s.objective}</a> · map {rev?.rev} · {s.setupSnapshot.setup.gearing}
                    </p>
                  ) : <p className="hint" style={{ margin: '2px 0 0' }}>Not run yet</p>}
                </div>
              );
            })}
          </Panel>
        ))}
      </div>

      <Panel title="Setup evolution across the weekend">
        {(() => {
          const linked = event.days.flatMap((d) => d.slots.map((s) => s.sessionId)).filter(Boolean)
            .map((id) => db.sessions.find((s) => s.id === id)!)
            .sort((a, b) => a.startedAt.localeCompare(b.startedAt));
          if (linked.length < 2) return <p className="hint">Link at least two sessions to see the evolution.</p>;
          const first = linked[0];
          const last = linked[linked.length - 1];
          const revA = db.mapRevisions.find((r) => r.id === first.setupSnapshot.mapRevisionId);
          const revB = db.mapRevisions.find((r) => r.id === last.setupSnapshot.mapRevisionId);
          return (
            <>
              <p style={{ fontSize: 14.5 }}>
                Started on <b className="mono">{revA?.rev} · {first.setupSnapshot.setup.gearing}</b>, finished on{' '}
                <b className="mono">{revB?.rev} · {last.setupSnapshot.setup.gearing}</b>.
              </p>
              <button className="btn small primary" onClick={() => nav(`compare/${first.id}/${last.id}`)}>Open in TRACE Compare</button>
            </>
          );
        })()}
      </Panel>

      <Panel title="Race-day timeline">
        <div className="btn-row" style={{ marginBottom: 10 }}>
          <input type="date" value={noteDate} onChange={(e) => setNoteDate(e.target.value)} style={{ background: 'var(--raised)', border: 0, borderRadius: 7, padding: '8px 12px' }} />
          <button className="btn small" onClick={() => {
            const t = prompt('Manual timeline note:');
            if (!t) return;
            update((d) => appendAudit(d, user!.id, 'note.manual', 'RaceEvent', event.id, t));
          }}>+ Manual note</button>
          <span className="hint">Timeline entries originate from real system events (audit log).</span>
        </div>
        <Timeline dateISO={noteDate} />
      </Panel>
    </div>
  );
}

export function Timeline({ dateISO, bikeId }: { dateISO: string; bikeId?: string }) {
  const { db } = useApp();
  const events = dayTimeline(db, dateISO, bikeId);
  if (!events.length) return <p className="hint">No system events on {dateISO}.</p>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {events.map((e) => (
        <div key={e.id} style={{ display: 'flex', gap: 14, fontSize: 13.5, alignItems: 'baseline' }}>
          <span className="mono" style={{ color: 'var(--accent)', flex: '0 0 76px' }}>
            {new Date(e.at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
          </span>
          <span style={{ flex: 1 }}>{e.summary} <span className="hint">— {db.users.find((u) => u.id === e.actorUserId)?.name ?? 'system'}</span></span>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------- pit board

export function PitBoard() {
  const { db } = useApp();
  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <div className="page-title"><h1>Live Pit Board</h1><Pill tone="sim">SIMULATED</Pill></div>
      <div className="fleet" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(min(420px, 100%), 1fr))' }}>
        {db.bikes.filter((b) => !b.retired).map((bike) => {
          const readiness = computeReadiness(db, bike);
          const rider = db.riders.find((r) => r.id === bike.assignedRiderId);
          const rev = db.mapRevisions.find((r) => r.id === bike.currentMapRevisionId);
          const last = [...db.sessions].filter((s) => s.bikeId === bike.id).sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
          const fresh = last && (Date.now() - new Date(last.startedAt).getTime()) < 2 * 3600 * 1000;
          const task = db.crewTasks.find((t) => t.bikeId === bike.id && t.status !== 'verified');
          const big = fresh ? 'RETURNING' : readiness.readyForInstrumentedTest ? 'READY' : readiness.status === 'Maintenance Required' ? 'MAINTENANCE' : 'BLOCKED';
          const tone = big === 'READY' ? 'var(--good)' : big === 'RETURNING' ? 'var(--warning)' : 'var(--critical)';
          return (
            <div key={bike.id} className="bike-card" style={{ cursor: 'default', padding: '22px 26px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span className="mono" style={{ fontSize: 30, fontWeight: 800 }}>{bike.label}</span>
                <span style={{ fontSize: 22, fontWeight: 800, color: tone, letterSpacing: '0.06em' }}>{big}</span>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: 16 }}>{rider?.name ?? 'Unassigned'} · map <b className="mono">{rev?.rev ?? '—'}</b></p>
              {!readiness.readyForInstrumentedTest && (
                <p style={{ margin: '6px 0 0', color: 'var(--critical)', fontSize: 14, fontWeight: 650 }}>
                  {readiness.gates.find((g) => g.critical && !g.pass)?.label}
                </p>
              )}
              {task && <p style={{ margin: '6px 0 0', fontSize: 14, color: 'var(--ink-2)' }}>Next: {task.title} — {db.users.find((u) => u.id === task.assigneeUserId)?.name}</p>}
              {last && <p className="hint" style={{ margin: '6px 0 0' }}>Last session {new Date(last.startedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} · {last.objective}</p>}
            </div>
          );
        })}
      </div>
      <p className="hint" style={{ textAlign: 'center', marginTop: 18 }}>Optimized for a transporter display or tablet on the pit wall.</p>
    </div>
  );
}

// ------------------------------------------------------------- crew tasks

export function CrewScreen() {
  const { db, user, update, allowed } = useApp();
  const canManage = allowed('session.create') || allowed('setup.edit');
  return (
    <div>
      <div className="page-title"><h1>Crew assignments</h1><span className="sub">race-day tasks, not project management</span></div>
      {canManage && (
        <div className="btn-row" style={{ marginBottom: 16 }}>
          <button className="btn primary" onClick={() => {
            const title = prompt('Task:');
            if (!title) return;
            update((d) => {
              d.crewTasks.unshift({
                id: `task-${Date.now()}`, orgId: d.org.id, assigneeUserId: user!.id,
                title, status: 'assigned', createdAt: new Date().toISOString(),
              });
              appendAudit(d, user!.id, 'task.create', 'CrewTask', 'new', title);
            });
          }}>+ Task</button>
        </div>
      )}
      <Panel>
        <div className="tbl-scroll">
          <table className="data">
            <thead><tr><th>Assignee</th><th>Task</th><th>Bike</th><th>Status</th><th /></tr></thead>
            <tbody>
              {db.crewTasks.map((t) => (
                <tr key={t.id}>
                  <td>{db.users.find((u) => u.id === t.assigneeUserId)?.name}</td>
                  <td style={{ fontWeight: 600 }}>{t.title}</td>
                  <td className="mono">{t.bikeId ? db.bikes.find((b) => b.id === t.bikeId)?.label : '—'}</td>
                  <td><Pill tone={t.status === 'verified' ? 'good' : t.status === 'in_progress' ? 'warning' : 'neutral'}>{t.status.replaceAll('_', ' ')}</Pill></td>
                  <td>
                    {t.status !== 'verified' && (
                      <button className="btn small ghost" onClick={() => update((d) => {
                        const x = d.crewTasks.find((y) => y.id === t.id)!;
                        x.status = x.status === 'assigned' ? 'in_progress' : 'verified';
                        appendAudit(d, user!.id, 'task.advance', 'CrewTask', x.id, `${x.title} → ${x.status}`);
                      })}>{t.status === 'assigned' ? 'Start' : 'Verify'}</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------- brief & debrief

export function BriefScreen() {
  const { db } = useApp();
  const brief = morningBrief(db);
  return (
    <div style={{ maxWidth: 720 }}>
      <div className="page-title"><h1>Morning Brief</h1><span className="sub">{new Date().toLocaleDateString()}</span></div>
      <section className="hero" style={{ padding: '22px 26px' }}>
        <p className="eyebrow">Today</p>
        <div style={{ display: 'flex', gap: 40, flexWrap: 'wrap', margin: '8px 0' }}>
          <span className="pit-stat" style={{ fontSize: 32 }}>{brief.ready}/{brief.total}<small>bikes ready</small></span>
          <span className="pit-stat" style={{ fontSize: 32 }}>{brief.maintenanceItems.length}<small>maintenance items</small></span>
          <span className="pit-stat" style={{ fontSize: 32 }}>{brief.openInsights}<small>open insights</small></span>
        </div>
        {brief.focus && <p style={{ fontSize: 16, fontWeight: 650, margin: '8px 0 0' }}>Focus: {brief.focus}</p>}
      </section>
      {brief.scheduled.length > 0 && (
        <Panel title="Scheduled tests">
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14 }}>{brief.scheduled.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </Panel>
      )}
      <Panel title="Watch">
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14 }}>
          {brief.watch.map((w, i) => <li key={i}>{w}</li>)}
          {brief.maintenanceItems.map((m, i) => <li key={`m${i}`}>{m}</li>)}
        </ul>
      </Panel>
      <p className="hint">Generated from live TRACE records — readiness gates, component life, faults, focus, and test plans.</p>
    </div>
  );
}

export function DebriefScreen() {
  const { db, user, update, allowed } = useApp();
  const today = new Date().toISOString().slice(0, 10);
  const stored = db.debriefs.find((d) => d.date === today);
  const draft = draftDebrief(db, today);
  const [learned, setLearned] = useState((stored?.learned ?? draft.learned).join('\n'));
  const [tomorrow, setTomorrow] = useState((stored?.tomorrow ?? draft.tomorrow).join('\n'));
  const canApprove = allowed('abtest.conclude');

  return (
    <div style={{ maxWidth: 720 }}>
      <div className="page-title">
        <h1>Debrief</h1>
        <span className="sub">{today}</span>
        {stored?.approvedByUserId && <Pill tone="good">Approved</Pill>}
      </div>
      <Help id="debrief">
        TRACE drafts the debrief from concluded tests, decisions, faults, and plans; the team edits and
        approves. Approved debriefs become permanent knowledge.
      </Help>
      <Panel title="What we learned">
        <textarea rows={6} style={{ width: '100%', background: 'var(--raised)', border: 0, borderRadius: 8, padding: 12 }}
          value={learned} onChange={(e) => setLearned(e.target.value)} />
      </Panel>
      <Panel title="Tomorrow">
        <textarea rows={5} style={{ width: '100%', background: 'var(--raised)', border: 0, borderRadius: 8, padding: 12 }}
          value={tomorrow} onChange={(e) => setTomorrow(e.target.value)} />
      </Panel>
      <div className="btn-row">
        <button className="btn primary" disabled={!canApprove} onClick={() => {
          update((d) => {
            const existing = d.debriefs.find((x) => x.date === today);
            const entry = {
              id: existing?.id ?? `debrief-${today}`, orgId: d.org.id, date: today,
              learned: learned.split('\n').filter(Boolean), tomorrow: tomorrow.split('\n').filter(Boolean),
              approvedByUserId: user!.id, editedByUserId: user!.id,
            };
            if (existing) Object.assign(existing, entry); else d.debriefs.push(entry);
            appendAudit(d, user!.id, 'debrief.approve', 'Debrief', entry.id, `Debrief approved for ${today}.`);
          });
        }}>Approve & store</button>
        {!canApprove && <span className="hint">Crew chief, tuner, or manager approves the final debrief.</span>}
      </div>
      {db.debriefs.filter((d) => d.date !== today).map((d) => (
        <Panel key={d.id} title={`Stored — ${d.date}`}>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>{d.learned.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </Panel>
      ))}
    </div>
  );
}

// ------------------------------------------------------------- remote access + marketplace

export function AccessScreen() {
  const { db, user, update, allowed } = useApp();
  const canManage = allowed('user.manage');
  return (
    <div>
      <div className="page-title">
        <h1>Remote tuner access</h1>
        <Pill tone="sim">SIMULATED — enforcement ships with the backend</Pill>
      </div>
      <Help id="access">
        Grants are scoped (bikes, permissions), time-limited, revocable, and audited. Nothing is shared
        by default; map-edit access is off unless explicitly enabled.
      </Help>
      {canManage && (
        <div className="btn-row" style={{ marginBottom: 16 }}>
          <button className="btn primary" onClick={() => {
            const name = prompt('External tuner name:');
            if (!name) return;
            update((d) => {
              d.grants.unshift({
                id: `grant-${Date.now()}`, orgId: d.org.id, tunerName: name,
                bikeIds: [d.bikes[0]?.id].filter(Boolean) as string[],
                readTelemetry: true, readMaps: true, commentAccess: true,
                exportAllowed: false, mapEditAllowed: false,
                createdByUserId: user!.id, createdAt: new Date().toISOString(),
                expiresAt: new Date(Date.now() + 48 * 3600 * 1000).toISOString(),
                state: 'SIMULATED',
              });
              appendAudit(d, user!.id, 'grant.create', 'RemoteAccessGrant', 'new', `48h read-only grant for ${name}.`);
            });
          }}>+ 48h read-only grant</button>
        </div>
      )}
      <Panel>
        <div className="tbl-scroll">
          <table className="data">
            <thead><tr><th>Tuner</th><th>Bikes</th><th>Permissions</th><th>Expires</th><th>Status</th><th /></tr></thead>
            <tbody>
              {db.grants.map((g) => (
                <tr key={g.id}>
                  <td style={{ fontWeight: 600 }}>{g.tunerName}</td>
                  <td className="mono">{g.bikeIds.map((id) => db.bikes.find((b) => b.id === id)?.label).join(', ')}</td>
                  <td className="hint">
                    {[g.readTelemetry && 'telemetry', g.readMaps && 'maps', g.commentAccess && 'comment', g.exportAllowed && 'export', g.mapEditAllowed && 'map edit'].filter(Boolean).join(' · ')}
                  </td>
                  <td className="mono">{new Date(g.expiresAt).toLocaleString()}</td>
                  <td><Pill tone={grantIsActive(g) ? 'good' : 'critical'}>{g.revokedAt ? 'Revoked' : grantIsActive(g) ? 'Active' : 'Expired'}</Pill></td>
                  <td>
                    {grantIsActive(g) && canManage && (
                      <button className="btn small danger" onClick={() => update((d) => {
                        const x = d.grants.find((y) => y.id === g.id)!;
                        x.revokedAt = new Date().toISOString();
                        appendAudit(d, user!.id, 'grant.revoke', 'RemoteAccessGrant', x.id, `Access revoked for ${x.tunerName}.`);
                      })}>Revoke now</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Marketplace" actions={<Pill tone="warning">SHELL / FUTURE</Pill>}>
        <p className="hint" style={{ marginTop: 0 }}>
          Architecture only — nothing is buyable or publishable. Every future listing carries
          compatibility, author, version, validation level, required hardware/fuel, and a disclaimer.
          Unvalidated community maps are never presented as safe.
        </p>
        {db.listings.map((l) => (
          <div key={l.id} style={{ background: 'var(--raised)', borderRadius: 10, padding: '12px 16px' }}>
            <p style={{ margin: 0, fontWeight: 700 }}>{l.title} <Pill tone="warning">{l.validationLevel}</Pill></p>
            <p className="hint" style={{ margin: '4px 0 0' }}>
              {l.author} · v{l.version} · {l.compatibility} · requires {l.requiredHardware.join(' + ')} · {l.requiredFuel}
            </p>
            <p style={{ fontSize: 12, color: 'var(--warning)', margin: '6px 0 0', fontWeight: 650 }}>{l.disclaimer}</p>
          </div>
        ))}
      </Panel>
    </div>
  );
}
