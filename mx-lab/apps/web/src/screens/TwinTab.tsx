import React, { useMemo, useState } from 'react';
import {
  bikeReliability, compareSetups, componentLife, twinFor, type DigitalTwinComponent,
} from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Panel, Pill, Prov, themeHeat } from '../ui';

/**
 * Digital Twin — interactive schematic of the bike. Tap a component for its
 * identity, hours, life estimate, and service history; overlay a session
 * A→B configuration comparison on the machine itself.
 */
const HOTSPOTS: Array<{ system: DigitalTwinComponent['system']; x: number; y: number }> = [
  { system: 'Front wheel', x: 84, y: 58 },
  { system: 'Fork', x: 72, y: 30 },
  { system: 'Controls', x: 60, y: 12 },
  { system: 'Brakes', x: 92, y: 76 },
  { system: 'Engine', x: 44, y: 56 },
  { system: 'ECU', x: 52, y: 26 },
  { system: 'Exhaust', x: 22, y: 48 },
  { system: 'Clutch', x: 58, y: 64 },
  { system: 'Gearing', x: 34, y: 70 },
  { system: 'Chain', x: 22, y: 78 },
  { system: 'Rear wheel', x: 12, y: 58 },
  { system: 'Shock', x: 32, y: 38 },
  { system: 'Tires', x: 6, y: 80 },
  { system: 'MX Node', x: 38, y: 16 },
  { system: 'Sensors', x: 20, y: 26 },
  { system: 'Fuel', x: 60, y: 42 },
  { system: 'Intake', x: 44, y: 40 },
];

export function TwinTab({ bikeId }: { bikeId: string }) {
  const { db } = useApp();
  const th = themeHeat();
  const comps = twinFor(db, bikeId);
  const bike = db.bikes.find((b) => b.id === bikeId)!;
  const [sel, setSel] = useState<string | null>(
    comps.find((c) => componentLife(c).status === 'Service due')?.id
    ?? comps.find((c) => componentLife(c).status === 'Approaching service')?.id
    ?? comps[0]?.id ?? null,
  );
  const selected = comps.find((c) => c.id === sel);
  const reliability = useMemo(() => bikeReliability(db, bike), [db, bike]);

  const sessions = db.sessions.filter((s) => s.bikeId === bikeId).sort((a, b) => a.startedAt.localeCompare(b.startedAt));
  const [cmpA, setCmpA] = useState(sessions[sessions.length - 2]?.id ?? '');
  const [cmpB, setCmpB] = useState(sessions[sessions.length - 1]?.id ?? '');
  const a = db.sessions.find((s) => s.id === cmpA);
  const b = db.sessions.find((s) => s.id === cmpB);
  const overlay = a && b ? compareSetups(db, a, b).filter((v) => v.changed && !['weather', 'trackCond', 'hours', 'slot', 'hardware'].includes(v.field)) : [];

  const lifeTone = (c: DigitalTwinComponent) => {
    const s = componentLife(c).status;
    return s === 'Service due' ? th.neg : s === 'Approaching service' ? '#e8b93b' : th.muted;
  };

  return (
    <div>
      <Help id="twin">
        Every part of the machine is a record: identity, hours, service history, and a
        DEVELOPMENT-labeled life estimate. Tap a node on the schematic.
      </Help>
      <div className="cols wide-left">
        <div>
          <Panel title={`Digital twin — ${bike.label}`}>
            <div className="chart-box">
              <svg viewBox="0 0 100 90" role="img" aria-label="Bike component schematic">
                {/* schematic frame lines connecting systems — engineering diagram, not clip-art */}
                <path d="M 12 58 L 32 38 L 44 40 L 72 30 L 84 58 M 44 40 L 44 56 L 34 70 L 12 58 M 44 56 L 58 64"
                  fill="none" stroke={th.hairline} strokeWidth="1.2" />
                <circle cx="12" cy="58" r="11" fill="none" stroke={th.muted} strokeWidth="1.4" />
                <circle cx="84" cy="58" r="11" fill="none" stroke={th.muted} strokeWidth="1.4" />
                {HOTSPOTS.map((h) => {
                  const comp = comps.find((c) => c.system === h.system);
                  if (!comp) return null;
                  const active = comp.id === sel;
                  return (
                    <g key={comp.id} style={{ cursor: 'pointer' }} onClick={() => setSel(comp.id)}>
                      <circle cx={h.x} cy={h.y} r={active ? 4.6 : 3.4}
                        fill={active ? th.accent : lifeTone(comp)}
                        stroke={active ? th.ink : 'none'} strokeWidth="0.8" />
                      <text x={h.x} y={h.y - 5.5} textAnchor="middle" fontSize="3.4"
                        fill={active ? th.ink : th.muted} style={{ fontWeight: 650 }}>
                        {h.system}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
            <p className="hint">Amber = approaching service · red = service due. Positions are schematic.</p>
          </Panel>

          <Panel title="Session A → B on this bike">
            <div className="grid2">
              <div className="field"><label>A</label>
                <select value={cmpA} onChange={(e) => setCmpA(e.target.value)}>
                  {sessions.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective.slice(0, 34)}</option>)}
                </select>
              </div>
              <div className="field"><label>B</label>
                <select value={cmpB} onChange={(e) => setCmpB(e.target.value)}>
                  {sessions.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective.slice(0, 34)}</option>)}
                </select>
              </div>
            </div>
            {overlay.length ? (
              <table className="data">
                <tbody>
                  {overlay.map((v) => (
                    <tr key={v.field}><td style={{ color: 'var(--muted)' }}>{v.label}</td><td className="mono">{v.a} → <b>{v.b}</b></td></tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="hint">No configuration changes between the selected sessions.</p>}
            {a && b && (
              <div className="btn-row" style={{ marginTop: 10 }}>
                <button className="btn small" onClick={() => nav(`compare/${a.id}/${b.id}`)}>Full TRACE Compare →</button>
              </div>
            )}
          </Panel>
        </div>

        <div>
          {selected && (
            <Panel title={selected.label} actions={<Prov p={selected.provenance} />}>
              <dl className="kv">
                <dt>Component</dt><dd className="mono">{selected.id} · rev {selected.rev}</dd>
                <dt>System</dt><dd>{selected.system}</dd>
                <dt>Hours</dt><dd className="mono">{selected.hours.toFixed(1)}</dd>
                <dt>Installed</dt><dd>{new Date(selected.installedAt).toLocaleDateString()}</dd>
                {selected.setupNote && <><dt>Setup</dt><dd>{selected.setupNote}</dd></>}
              </dl>
              {(() => {
                const life = componentLife(selected);
                const tone = life.status === 'Service due' ? 'critical' : life.status === 'Approaching service' ? 'warning' : life.status === 'OK' ? 'good' : 'neutral';
                return (
                  <div style={{ marginTop: 10 }}>
                    <Pill tone={tone}>{life.status}</Pill>{' '}<Pill tone="warning">{life.state}</Pill>
                    <p className="hint" style={{ marginTop: 6 }}>{life.detail} <span style={{ color: 'var(--muted)' }}>({life.kind})</span></p>
                  </div>
                );
              })()}
              <p className="eyebrow" style={{ marginTop: 14 }}>Service history</p>
              {selected.serviceHistory.map((s, i) => (
                <p key={i} style={{ fontSize: 13, margin: '2px 0' }}>
                  <span className="mono" style={{ color: 'var(--muted)' }}>{new Date(s.at).toLocaleDateString()}</span> — {s.note} ({s.hoursAt.toFixed(1)} h)
                </p>
              ))}
            </Panel>
          )}

          <Panel title="Race readiness score">
            {reliability.scorePct === null ? (
              <>
                <p style={{ fontSize: 20, fontWeight: 800, color: 'var(--critical)', margin: 0 }}>OVERRIDDEN</p>
                <p className="hint">{reliability.overriddenBy} — a failed critical gate always overrides the number.</p>
              </>
            ) : (
              <p className="pit-stat" style={{ fontSize: 40, margin: 0 }}>{reliability.scorePct}%<small>race readiness (never a substitute for the gates)</small></p>
            )}
            <div className="gates" style={{ marginTop: 12 }}>
              {reliability.factors.map((f) => (
                <div key={f.label} className={`gate ${f.pass ? 'pass' : 'fail'}`}>
                  <span className="mark mono">{f.score}</span>
                  <span className="lab">{f.label}{f.critical ? '' : ' (advisory)'}</span>
                  <span className="det">{f.detail}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
