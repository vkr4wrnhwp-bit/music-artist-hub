import React, { useState } from 'react';
import { appendAudit, auditFor, computeReadiness } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Panel, Pill, Prov, readinessTone } from '../ui';

export function BikeProfile({ bikeId }: { bikeId: string }) {
  const { db, user, update, allowed } = useApp();
  const [tab, setTab] = useState<'overview' | 'setup' | 'engine' | 'ecu' | 'maintenance' | 'history'>('overview');
  const bike = db.bikes.find((b) => b.id === bikeId);
  if (!bike || !user) return <p>Bike not found.</p>;

  const model = db.bikeModels.find((m) => m.id === bike.bikeModelId);
  const ecuInst = db.ecuInstances.find((e) => e.id === bike.ecuInstanceId);
  const ecuDef = db.ecuDefinitions.find((d) => d.id === ecuInst?.ecuDefinitionId);
  const build = db.engineBuilds.find((x) => x.id === bike.engineBuildId);
  const rider = db.riders.find((r) => r.id === bike.assignedRiderId);
  const rev = db.mapRevisions.find((r) => r.id === bike.currentMapRevisionId);
  const map = db.maps.find((m) => m.id === rev?.mapId);
  const readiness = computeReadiness(db, bike);
  const device = db.devices.find((d) => d.id === bike.hardwareDeviceId);
  const topIssue = readiness.gates.find((g) => g.critical && !g.pass);

  const tabs = [
    ['overview', 'Overview'], ['setup', 'Setup'], ['engine', 'Engine'],
    ['ecu', 'ECU'], ['maintenance', 'Service'], ['history', 'History'],
  ] as const;

  return (
    <div>
      <section className="hero" style={{ padding: '24px 28px 22px' }}>
        <p className="eyebrow">{model ? `${model.modelYear} ${model.manufacturer} ${model.model}` : 'Bike'}</p>
        <h1 className="mono" style={{ fontSize: 30 }}>{bike.label}</h1>
        <div className="hero-row" style={{ marginTop: 14 }}>
          <span className="hero-kv">Status<b><Pill tone={readinessTone(readiness.status)}>{readiness.status}</Pill></b></span>
          <span className="hero-kv">Rider<b>{rider?.name ?? 'Unassigned'}</b></span>
          <span className="hero-kv">Map<b className="mono">{rev ? `${map?.name}-${rev.rev} · Slot ${bike.currentMapSlot}` : 'None'}</b></span>
          <span className="hero-kv">Engine<b className="mono">{bike.totalHours.toFixed(1)} h · {bike.hoursSinceRebuild.toFixed(1)} since rebuild</b></span>
          {topIssue && <span className="hero-kv">Blocking<b style={{ color: 'var(--critical)' }}>{topIssue.label}</b></span>}
        </div>
      </section>

      <div className="btn-row no-print" style={{ marginBottom: 18 }}>
        {tabs.map(([id, label]) => (
          <button key={id} className={`btn small ${tab === id ? 'primary' : 'ghost'}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="cols">
          <div>
            <Panel title="Identity (Phase 0 inventory)">
              <Help id="identity">
                A bike can't be tested until its exact hardware is confirmed by a person.
                <b> No field here is ever inferred</b> — model year and engine build change what a map means.
              </Help>
              <dl className="kv">
                <dt>Model</dt><dd>{model ? `${model.modelYear} ${model.manufacturer} ${model.model}` : '—'} {bike.modelYearConfirmed ? <Pill tone="good">Confirmed</Pill> : <Pill tone="critical">Unconfirmed</Pill>}</dd>
                <dt>VIN (partial)</dt><dd className="mono">{bike.vinPartial ?? '—'}</dd>
                <dt>ECU</dt><dd>{ecuDef ? <a href={`#/ecu/${ecuDef.id}`}>{ecuDef.model}</a> : 'Unknown'} {ecuDef && <Pill tone="sim">SIMULATED</Pill>}</dd>
                <dt>ECU serial</dt><dd className="mono">{ecuInst?.serialNumber ?? '—'}</dd>
                <dt>Firmware</dt><dd className="mono">{ecuDef?.firmware ?? '—'}</dd>
                <dt>Engine build</dt><dd className="mono">{build?.code ?? '—'} {build && <Prov p={build.provenance} />}</dd>
                <dt>Rev limit</dt><dd className="mono">{build?.revLimit.toLocaleString() ?? '—'} rpm</dd>
                <dt>Fuel</dt><dd>{db.fuels.find((f) => f.id === bike.setup.fuelId)?.name ?? '—'}</dd>
                <dt>Exhaust</dt><dd>{db.exhausts.find((e) => e.id === bike.setup.exhaustId)?.name ?? '—'}</dd>
              </dl>
              {!bike.identityConfirmed && allowed('bike.editIdentity') && (
                <div className="btn-row" style={{ marginTop: 10 }}>
                  <button
                    className="btn primary"
                    onClick={() => update((d) => {
                      const b = d.bikes.find((x) => x.id === bike.id)!;
                      b.identityConfirmed = true;
                      b.modelYearConfirmed = true;
                      appendAudit(d, user.id, 'bike.identity_confirmed', 'Bike', b.id, `${b.label}: Phase 0 identity confirmed.`);
                    })}
                  >
                    Confirm inventory complete
                  </button>
                </div>
              )}
            </Panel>
            <Panel title="Current map">
              <dl className="kv">
                <dt>Map</dt><dd className="mono">{rev ? <a href={`#/maps/${rev.id}`}>{map?.name}-{rev.rev}</a> : 'None'}</dd>
                <dt>Slot</dt><dd className="mono">{bike.currentMapSlot ?? '—'}</dd>
                <dt>State</dt><dd>{rev ? rev.state.replaceAll('_', ' ') : '—'}</dd>
                <dt>Trims</dt><dd className="mono">{Object.entries(bike.trims).map(([k, v]) => `${k}: ${v}`).join(' · ')}</dd>
                <dt>Transfer</dt>
                <dd>{db.transfers.some((t) => t.mapRevisionId === rev?.id && t.bikeId === bike.id)
                  ? <Pill tone="good">Confirmed (SIMULATED)</Pill>
                  : <Pill tone="warning">Not confirmed</Pill>}
                </dd>
              </dl>
            </Panel>
          </div>
          <Panel title="Readiness gates">
            <Help id="gates">
              The overall status is the <b>worst failing critical gate</b>. AI can never satisfy a gate —
              only confirmed records can.
            </Help>
            <div className="gates">
              {readiness.gates.map((g) => (
                <div key={g.id} className={`gate ${g.pass ? 'pass' : 'fail'}`}>
                  <span className="mark">{g.pass ? 'PASS' : 'FAIL'}</span>
                  <span className="lab">{g.label}{!g.critical && ' (advisory)'}</span>
                  <span className="det">{g.detail}</span>
                </div>
              ))}
            </div>
            <p className="hint" style={{ marginTop: 10 }}>
              Overall: <b>{readiness.readyForInstrumentedTest ? 'READY FOR INSTRUMENTED TEST' : 'NOT READY FOR INSTRUMENTED TEST'}</b>
            </p>
            {device ? (
              <p className="hint">Logger: {device.id} · fw {device.firmware} · battery {device.batteryPct}% · <Pill tone="sim">SIMULATED HARDWARE</Pill></p>
            ) : (
              (allowed('hardware.manage') || allowed('setup.edit')) && (
                <div className="btn-row" style={{ marginTop: 10 }}>
                  {db.devices.filter((d) => !d.assignedBikeId || !db.bikes.some((b) => b.hardwareDeviceId === d.id)).map((d) => (
                    <button key={d.id} className="btn small" onClick={() => update((dd) => {
                      const b = dd.bikes.find((x) => x.id === bike.id)!;
                      b.hardwareDeviceId = d.id;
                      const dev = dd.devices.find((x) => x.id === d.id)!;
                      dev.assignedBikeId = b.id;
                      appendAudit(dd, user.id, 'hardware.assign', 'Bike', b.id, `MX Node ${d.id} assigned (SIMULATED).`);
                    })}>Assign {d.id} (SIMULATED)</button>
                  ))}
                  <button className="btn small" onClick={() => update((dd) => {
                    const id = `node-${String(dd.devices.length + 1).padStart(2, '0')}`;
                    dd.devices.push({
                      id, orgId: dd.org.id, kind: 'MX_NODE', hardwareRev: 'SIM-A1', firmware: 'sim-0.9.2',
                      assignedBikeId: bike.id, batteryPct: 100, storagePct: 0,
                      channelHealth: { rpm: 'Simulated', tps: 'Simulated', speed: 'Simulated', slip: 'Simulated', coolant: 'Simulated' },
                      mode: 'test', radioDisabled: false, competitionApprovalStatus: 'Not reviewed',
                      enclosureRev: 'ENC-A0 (brief only)', mountRev: 'TBD', openIssues: [], simulated: true,
                    });
                    const b = dd.bikes.find((x) => x.id === bike.id)!;
                    b.hardwareDeviceId = id;
                    appendAudit(dd, user.id, 'hardware.assign', 'Bike', b.id, `New simulated MX Node ${id} provisioned and assigned.`);
                  })}>Provision new simulated node</button>
                </div>
              )
            )}
          </Panel>
        </div>
      )}

      {tab === 'setup' && <SetupTab bikeId={bike.id} />}

      {tab === 'maintenance' && (
        <div className="cols">
          <Panel title="Maintenance log">
            <div className="tbl-scroll">
              <table className="data">
                <thead><tr><th>Date</th><th>Kind</th><th>Hours</th><th>Note</th><th>By</th><th /></tr></thead>
                <tbody>
                  {db.maintenance.filter((m) => m.bikeId === bike.id).map((m) => (
                    <tr key={m.id}>
                      <td>{new Date(m.at).toLocaleDateString()}</td>
                      <td>{m.kind}</td>
                      <td className="num">{m.hoursAt.toFixed(1)}</td>
                      <td>{m.note}</td>
                      <td>{db.users.find((u) => u.id === m.byUserId)?.name ?? m.byUserId}</td>
                      <td><Prov p={m.provenance} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {allowed('maintenance.record') && <AddMaintenance bikeId={bike.id} />}
          </Panel>
          <Panel title="Faults & engine hours">
            <dl className="kv">
              <dt>Total hours</dt><dd className="mono">{bike.totalHours.toFixed(1)}</dd>
              <dt>Since rebuild</dt><dd className="mono">{bike.hoursSinceRebuild.toFixed(1)}</dd>
              <dt>Status</dt><dd><Pill tone={bike.maintenanceStatus === 'Current' ? 'good' : bike.maintenanceStatus === 'Due Soon' ? 'warning' : 'critical'}>{bike.maintenanceStatus}</Pill></dd>
            </dl>
            <Help id="hours">
              Sessions are only comparable when engine condition is comparable. A/B conclusions across a
              rebuild boundary are flagged, not trusted.
            </Help>
            <h4 style={{ margin: '12px 0 6px', fontSize: 13 }}>Fault records</h4>
            {db.faults.filter((f) => f.bikeId === bike.id).map((f) => (
              <p key={f.id} style={{ margin: '4px 0', fontSize: 13 }}>
                <Pill tone={f.resolved ? 'neutral' : 'serious'}>{f.code}</Pill> {f.note} <span className="hint">({f.source})</span>
              </p>
            ))}
            {db.faults.filter((f) => f.bikeId === bike.id).length === 0 && <p className="hint">No faults recorded.</p>}
          </Panel>
        </div>
      )}

      {tab === 'engine' && (
        <div className="cols">
          <Panel title="Engine build">
            {build ? (
              <dl className="kv">
                <dt>Build</dt><dd className="mono">{build.code} <Prov p={build.provenance} /></dd>
                <dt>Camshaft</dt><dd>{build.camshaft}</dd>
                <dt>Compression</dt><dd>{build.compression}</dd>
                <dt>Injector</dt><dd>{build.injector}</dd>
                <dt>Throttle body</dt><dd>{build.throttleBody}</dd>
                <dt>Rev limit</dt><dd className="mono">{build.revLimit.toLocaleString()} rpm</dd>
                <dt>Built by</dt><dd>{db.users.find((u) => u.id === build.builtBy)?.name ?? build.builtBy}</dd>
                <dt>Notes</dt><dd>{build.notes ?? '—'}</dd>
              </dl>
            ) : <p className="hint">No engine build assigned.</p>}
          </Panel>
          <Panel title="Hours & comparability">
            <dl className="kv">
              <dt>Total hours</dt><dd className="mono">{bike.totalHours.toFixed(1)}</dd>
              <dt>Since rebuild</dt><dd className="mono">{bike.hoursSinceRebuild.toFixed(1)}</dd>
            </dl>
            <Help id="hours">
              Sessions are only comparable when engine condition is comparable — A/B conclusions across
              a rebuild boundary are flagged, not trusted.
            </Help>
          </Panel>
        </div>
      )}

      {tab === 'ecu' && (
        <div className="cols">
          <Panel title="ECU identity">
            {ecuDef ? (
              <>
                <dl className="kv">
                  <dt>Definition</dt><dd><a href={`#/ecu/${ecuDef.id}`}>{ecuDef.model}</a> <Pill tone="sim">SIMULATED</Pill></dd>
                  <dt>Serial</dt><dd className="mono">{ecuInst?.serialNumber}</dd>
                  <dt>Firmware</dt><dd className="mono">{ecuDef.firmware}</dd>
                  <dt>Verification</dt><dd>{ecuDef.verification}</dd>
                  <dt>Map slots</dt><dd className="mono">{ecuDef.mapSlotCount ?? 'unknown'}</dd>
                  <dt>Trims</dt><dd className="mono">{ecuDef.globalTrims.join(' · ')}</dd>
                </dl>
                <div className="btn-row" style={{ marginTop: 12 }}>
                  <button className="btn small" onClick={() => nav(`ecu/${ecuDef.id}`)}>Full ECU profile →</button>
                </div>
              </>
            ) : <p className="hint">No ECU recorded — complete Phase 0 inventory.</p>}
          </Panel>
          <Panel title="Write access">
            <div className="write-disabled">DIRECT ECU WRITE DISABLED — AUTHORIZED VORTEX INTEGRATION NOT YET VALIDATED</div>
            <p className="hint" style={{ marginTop: 10 }}>
              Map changes travel through the companion workflow in the Tune area and are confirmed by a
              person.
            </p>
          </Panel>
        </div>
      )}

      {tab === 'history' && (
        <Panel title="Map history on this bike">
          <div className="tbl-scroll">
            <table className="data">
              <thead><tr><th>Revision</th><th>State</th><th>Slot</th><th>Transferred</th><th>Verified by 2nd</th><th>Sessions</th></tr></thead>
              <tbody>
                {db.transfers.filter((t) => t.bikeId === bike.id).map((t) => {
                  const r = db.mapRevisions.find((x) => x.id === t.mapRevisionId);
                  const m = db.maps.find((x) => x.id === r?.mapId);
                  return (
                    <tr key={t.id} className="click" onClick={() => nav(`maps/${t.mapRevisionId}`)}>
                      <td className="mono">{m?.name}-{r?.rev}</td>
                      <td>{r?.state.replaceAll('_', ' ')}</td>
                      <td className="num">{t.slot}</td>
                      <td>{new Date(t.transferredAt).toLocaleString()} <Pill tone="sim">SIM</Pill></td>
                      <td>{t.verifiedByUserId ? db.users.find((u) => u.id === t.verifiedByUserId)?.name : '—'}</td>
                      <td>{t.linkedSessionId ? <a href={`#/session/${t.linkedSessionId}`}>{t.linkedSessionId}</a> : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {tab === 'history' && (
        <Panel title="Sessions">
          <div className="tbl-scroll">
            <table className="data">
              <thead><tr><th>Date</th><th>Objective</th><th>Track</th><th>Rider</th><th>Map</th><th>Laps</th></tr></thead>
              <tbody>
                {db.sessions.filter((s) => s.bikeId === bike.id).map((s) => {
                  const r = db.mapRevisions.find((x) => x.id === s.setupSnapshot.mapRevisionId);
                  return (
                    <tr key={s.id} className="click" onClick={() => nav(`session/${s.id}`)}>
                      <td>{new Date(s.startedAt).toLocaleString()}</td>
                      <td>{s.objective}</td>
                      <td>{db.tracks.find((tr) => tr.id === s.trackId)?.name}</td>
                      <td>{db.riders.find((ri) => ri.id === s.riderId)?.name}</td>
                      <td className="mono">{r?.rev} / slot {s.setupSnapshot.mapSlot}</td>
                      <td className="num">{s.lapCount}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {tab === 'history' && (
        <Panel title="Audit timeline (this bike)">
          <AuditList entityIds={[bike.id, bike.currentMapRevisionId ?? '']} />
        </Panel>
      )}
    </div>
  );
}

function SetupTab({ bikeId }: { bikeId: string }) {
  const { db, user, update, allowed } = useApp();
  const bike = db.bikes.find((b) => b.id === bikeId)!;
  const [draft, setDraft] = useState({ ...bike.setup });
  const canEdit = allowed('setup.edit');
  return (
    <div className="cols">
      <Panel title="Physical setup">
        <div className="grid2">
          {([
            ['gearing', 'Gearing (F/R)'], ['tireModel', 'Tire model'], ['tireSizeRear', 'Rear tire size'],
            ['suspension', 'Suspension'], ['clutch', 'Clutch'],
          ] as const).map(([k, label]) => (
            <div className="field" key={k}>
              <label>{label}</label>
              <input disabled={!canEdit} value={draft[k]} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} />
            </div>
          ))}
          {([
            ['tirePressureFront', 'Front pressure (bar)'], ['tirePressureRear', 'Rear pressure (bar)'],
            ['forkHeightMm', 'Fork height (mm)'], ['sagMm', 'Sag (mm)'],
          ] as const).map(([k, label]) => (
            <div className="field" key={k}>
              <label>{label}</label>
              <input disabled={!canEdit} type="number" step="0.01" value={draft[k]}
                onChange={(e) => setDraft({ ...draft, [k]: parseFloat(e.target.value) || 0 })} />
            </div>
          ))}
          <div className="field">
            <label>Fuel</label>
            <select disabled={!canEdit} value={draft.fuelId} onChange={(e) => setDraft({ ...draft, fuelId: e.target.value })}>
              {db.fuels.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Exhaust</label>
            <select disabled={!canEdit} value={draft.exhaustId} onChange={(e) => setDraft({ ...draft, exhaustId: e.target.value })}>
              {db.exhausts.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </div>
        </div>
        {canEdit && (
          <div className="btn-row">
            <button className="btn primary" onClick={() => update((d) => {
              const b = d.bikes.find((x) => x.id === bikeId)!;
              b.setup = { ...draft };
              appendAudit(d, user!.id, 'setup.edit', 'Bike', b.id, `${b.label}: setup updated (MECHANIC ENTERED).`);
            })}>Save setup</button>
            <span className="hint">Changing fuel or exhaust re-runs map compatibility everywhere.</span>
          </div>
        )}
      </Panel>
      <Panel title="Trim switch positions">
        <Help id="trims">
          Global trims shift whole regions at once; a table change edits specific cells. Record the
          physical switch positions here so every session snapshot is truthful.
        </Help>
        {Object.entries(bike.trims).map(([k, v]) => (
          <div className="field" key={k}>
            <label>{k} trim</label>
            <input type="number" disabled={!allowed('trim.record')} defaultValue={v} min={0} max={10}
              onBlur={(e) => {
                const nv = parseInt(e.target.value, 10);
                if (Number.isFinite(nv) && nv !== v) {
                  update((d) => {
                    const b = d.bikes.find((x) => x.id === bikeId)!;
                    b.trims[k] = nv;
                    appendAudit(d, user!.id, 'trim.record', 'Bike', b.id, `${b.label}: ${k} trim ${v} → ${nv}.`);
                  });
                }
              }} />
          </div>
        ))}
        <p className="hint">Trim names come from the verified ECU definition — nothing else is shown.</p>
      </Panel>
    </div>
  );
}

function AddMaintenance({ bikeId }: { bikeId: string }) {
  const { user, update } = useApp();
  const [kind, setKind] = useState('Oil change');
  const [note, setNote] = useState('');
  return (
    <div className="btn-row" style={{ marginTop: 12 }}>
      <select value={kind} onChange={(e) => setKind(e.target.value)}>
        {['Oil change', 'Air filter', 'Top-end service', 'Bottom-end service', 'Clutch service', 'Injector service', 'Fuel-pump service', 'Sensor replacement', 'Wiring repair', 'ECU replacement', 'MX Node service'].map((k) => <option key={k}>{k}</option>)}
      </select>
      <input placeholder="Note" value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
      <button className="btn" onClick={() => {
        update((d) => {
          const b = d.bikes.find((x) => x.id === bikeId)!;
          d.maintenance.unshift({
            id: `mnt-${Date.now()}`, bikeId, at: new Date().toISOString(), kind,
            hoursAt: b.totalHours, note: note || '—', byUserId: user!.id, provenance: 'MECHANIC ENTERED',
          });
          if (kind === 'Oil change') b.maintenanceStatus = 'Current';
          appendAudit(d, user!.id, 'maintenance.record', 'Bike', bikeId, `${kind}: ${note || '—'}`);
        });
        setNote('');
      }}>Record</button>
    </div>
  );
}

export function AuditList({ entityIds }: { entityIds: string[] }) {
  const { db } = useApp();
  const events = db.audit.filter((e) => entityIds.includes(e.entityId)).sort((a, b) => b.at.localeCompare(a.at));
  if (!events.length) return <p className="hint">No audit events.</p>;
  return (
    <div className="tbl-scroll">
      <table className="data">
        <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Summary</th></tr></thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.id}>
              <td className="mono">{new Date(e.at).toLocaleString()}</td>
              <td>{db.users.find((u) => u.id === e.actorUserId)?.name ?? e.actorUserId}</td>
              <td className="mono">{e.action}</td>
              <td>{e.summary}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
