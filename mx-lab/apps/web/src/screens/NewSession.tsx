import React, { useState } from 'react';
import { appendAudit, computeReadiness, type Session } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Panel, Pill, readinessTone } from '../ui';

const OBJECTIVES = [
  'Smooth corner-exit delivery', 'Improve start consistency', 'Reduce RPM drop',
  'Improve deep-loam drive', 'Reduce hard-pack wheelspin', 'Improve top-end pull',
  'Reduce rider fatigue', 'Compare map slots', 'Compare trims', 'Compare gearing',
  'Investigate overheating', 'Investigate bog', 'Validate engine build',
];

const STEPS = ['Bike', 'Rider', 'Track', 'Conditions', 'Setup', 'Hardware', 'Objective', 'Start'];

export function NewSession() {
  const { db, user, update, allowed } = useApp();
  const [step, setStep] = useState(0);
  const [bikeId, setBikeId] = useState('');
  const [riderId, setRiderId] = useState('');
  const [trackId, setTrackId] = useState('');
  const [objective, setObjective] = useState(OBJECTIVES[0]);
  const [weather, setWeather] = useState({ ambientC: 27, humidityPct: 48, baroHpa: 1009, windKph: 8, trackTempC: 34 });
  const [cond, setCond] = useState({ surfaceType: 'Hard pack', preparation: 'Ripped and watered AM', moisture: 'Drying', ruts: 'Forming', bumps: 'Moderate' });
  const [setupConfirmed, setSetupConfirmed] = useState(false);
  const [hwConfirmed, setHwConfirmed] = useState(false);

  if (!user || !allowed('session.create')) {
    return <Panel title="New test session"><p>Your role cannot create sessions. Ask a crew chief, tuner, or team manager.</p></Panel>;
  }

  const bike = db.bikes.find((b) => b.id === bikeId);
  const rider = db.riders.find((r) => r.id === riderId);
  const track = db.tracks.find((t) => t.id === trackId);
  const readiness = bike ? computeReadiness(db, bike) : null;
  const device = db.devices.find((d) => d.id === bike?.hardwareDeviceId);
  const rev = db.mapRevisions.find((r) => r.id === bike?.currentMapRevisionId);
  const build = db.engineBuilds.find((x) => x.id === bike?.engineBuildId);

  const canNext = [
    !!bike, !!rider, !!track, true, setupConfirmed, hwConfirmed && !!device, !!objective, false,
  ];

  const start = () => {
    if (!bike || !rider || !track || !device || !rev || !build) return;
    const id = `sess-${Date.now()}`;
    update((d) => {
      const s: Session = {
        id, orgId: d.org.id, bikeId: bike.id, riderId: rider.id, trackId: track.id,
        objective, status: 'complete', startedAt: new Date().toISOString(), durationS: 720,
        weather: { ...weather, provenance: 'MEASURED' },
        trackCondition: { ...cond, provenance: 'MECHANIC ENTERED' },
        setupSnapshot: {
          mapRevisionId: rev.id, mapSlot: bike.currentMapSlot ?? 0, trims: { ...bike.trims },
          setup: { ...bike.setup }, engineBuildId: build.id, hoursAtSession: bike.totalHours,
        },
        hardwareCheck: {
          deviceId: device.id, firmware: device.firmware, batteryPct: device.batteryPct,
          storagePct: device.storagePct, gps: 'Simulated', imu: 'Simulated', ecuData: 'Simulated',
          calibrationCurrent: !Object.values(device.channelHealth).includes('Uncalibrated'),
          mode: device.mode, radioDisabled: device.radioDisabled, simulated: true,
        },
        simSeed: Math.floor(Math.random() * 1e9), lapCount: 7,
        createdByUserId: user.id, simulated: true,
      };
      d.sessions.push(s);
      const b = d.bikes.find((x) => x.id === bike.id)!;
      b.totalHours = +(b.totalHours + 0.35).toFixed(1);
      b.hoursSinceRebuild = +(b.hoursSinceRebuild + 0.35).toFixed(1);
      const revd = d.mapRevisions.find((r) => r.id === rev.id)!;
      revd.testedInSessionIds.push(id);
      if (revd.state === 'TRANSFER_CONFIRMED') revd.state = 'TESTED';
      const xfer = d.transfers.find((t) => t.mapRevisionId === rev.id && t.bikeId === bike.id && !t.linkedSessionId);
      if (xfer) xfer.linkedSessionId = id;
      appendAudit(d, user.id, 'session.create', 'Session', id,
        `Session on ${bike.label} at ${track.name}: ${objective} (SIMULATED MX Node run).`);
    });
    nav(`session/${id}`);
  };

  return (
    <div>
      <div className="page-title"><h1>New test session</h1><span className="sub">works fully offline — nothing here needs a connection</span></div>
      <div className="wiz-steps">
        {STEPS.map((s, i) => (
          <span key={s} className={`ws ${i === step ? 'now' : i < step ? 'done' : ''}`}>{i + 1}. {s}</span>
        ))}
      </div>

      {step === 0 && (
        <Panel title="Step 1 — Select motorcycle">
          <div className="field"><label>Bike</label>
            <select value={bikeId} onChange={(e) => setBikeId(e.target.value)}>
              <option value="">— select —</option>
              {db.bikes.filter((b) => !b.retired).map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
            </select>
          </div>
          {bike && readiness && (
            <>
              <dl className="kv">
                <dt>Model</dt><dd>{db.bikeModels.find((m) => m.id === bike.bikeModelId)?.modelYear} {db.bikeModels.find((m) => m.id === bike.bikeModelId)?.model}</dd>
                <dt>ECU</dt><dd>{db.ecuDefinitions.find((x) => x.id === db.ecuInstances.find((e) => e.id === bike.ecuInstanceId)?.ecuDefinitionId)?.model}</dd>
                <dt>Map / slot</dt><dd className="mono">{rev?.rev ?? 'none'} / {bike.currentMapSlot}</dd>
                <dt>Trims</dt><dd className="mono">{Object.entries(bike.trims).map(([k, v]) => `${k}:${v}`).join(' ')}</dd>
                <dt>Hours</dt><dd className="mono">{bike.totalHours.toFixed(1)} ({bike.hoursSinceRebuild.toFixed(1)} since rebuild)</dd>
                <dt>Maintenance</dt><dd>{bike.maintenanceStatus}</dd>
                <dt>Readiness</dt><dd><Pill tone={readinessTone(readiness.status)}>{readiness.status}</Pill></dd>
              </dl>
              {!readiness.readyForInstrumentedTest && (
                <div style={{ marginTop: 8 }}>
                  <p style={{ color: 'var(--critical-text)', fontWeight: 600, fontSize: 13 }}>
                    This bike is not ready for an instrumented test. Failing gates:
                  </p>
                  <ul style={{ margin: '4px 0', paddingLeft: 18, fontSize: 13 }}>
                    {readiness.gates.filter((g) => g.critical && !g.pass).map((g) => <li key={g.id}>{g.label}: {g.detail}</li>)}
                  </ul>
                  <a href={`#/bike/${bike.id}`}>Open bike profile to resolve →</a>
                </div>
              )}
            </>
          )}
        </Panel>
      )}

      {step === 1 && (
        <Panel title="Step 2 — Select rider">
          <div className="field"><label>Rider</label>
            <select value={riderId} onChange={(e) => setRiderId(e.target.value)}>
              <option value="">— select —</option>
              {db.riders.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
          {rider && (
            <dl className="kv">
              <dt>Weight</dt><dd className="mono">{rider.weightKg} kg</dd>
              <dt>Skill</dt><dd>{rider.skillCategory}</dd>
              <dt>Preferred delivery</dt><dd>{rider.preferredDelivery}</dd>
              <dt>Limitations</dt><dd>{rider.limitationNotes ?? 'None recorded'}</dd>
            </dl>
          )}
        </Panel>
      )}

      {step === 2 && (
        <Panel title="Step 3 — Select track">
          <div className="field"><label>Track</label>
            <select value={trackId} onChange={(e) => setTrackId(e.target.value)}>
              <option value="">— select —</option>
              {db.tracks.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          {track && (
            <dl className="kv">
              <dt>Type</dt><dd>{track.kind === 'motocross' ? 'Motocross' : 'Supercross test'} · {track.direction}</dd>
              <dt>Surface</dt><dd>{track.surface}</dd>
              <dt>Sections</dt><dd>{track.segments.map((s) => s.name).join(' · ')}</dd>
              <dt>Elevation</dt><dd className="mono">{track.elevationM ?? '—'} m</dd>
            </dl>
          )}
        </Panel>
      )}

      {step === 3 && (
        <Panel title="Step 4 — Conditions">
          <div className="grid3">
            {([['ambientC', 'Ambient °C'], ['humidityPct', 'Humidity %'], ['baroHpa', 'Baro hPa'], ['windKph', 'Wind kph'], ['trackTempC', 'Track °C']] as const).map(([k, l]) => (
              <div className="field" key={k}><label>{l}</label>
                <input type="number" value={weather[k]} onChange={(e) => setWeather({ ...weather, [k]: parseFloat(e.target.value) || 0 })} />
              </div>
            ))}
          </div>
          <div className="grid3">
            {([['surfaceType', 'Surface'], ['preparation', 'Preparation'], ['moisture', 'Moisture'], ['ruts', 'Ruts'], ['bumps', 'Bumps']] as const).map(([k, l]) => (
              <div className="field" key={k}><label>{l}</label>
                <input value={cond[k]} onChange={(e) => setCond({ ...cond, [k]: e.target.value })} />
              </div>
            ))}
          </div>
        </Panel>
      )}

      {step === 4 && bike && (
        <Panel title="Step 5 — Confirm motorcycle setup">
          <Help id="setup-confirm">
            The session snapshots this exact setup. If anything on the bike differs from these values,
            fix the record first — a session with a wrong snapshot poisons every comparison built on it.
          </Help>
          <dl className="kv">
            <dt>Fuel</dt><dd>{db.fuels.find((f) => f.id === bike.setup.fuelId)?.name}</dd>
            <dt>Gearing</dt><dd className="mono">{bike.setup.gearing}</dd>
            <dt>Tire</dt><dd>{bike.setup.tireModel} {bike.setup.tireSizeRear} · F {bike.setup.tirePressureFront} / R {bike.setup.tirePressureRear} bar</dd>
            <dt>Suspension</dt><dd>{bike.setup.suspension} · fork {bike.setup.forkHeightMm} mm · sag {bike.setup.sagMm} mm</dd>
            <dt>Clutch</dt><dd>{bike.setup.clutch}</dd>
            <dt>Engine</dt><dd className="mono">{build?.code}</dd>
            <dt>Exhaust</dt><dd>{db.exhausts.find((e) => e.id === bike.setup.exhaustId)?.name}</dd>
            <dt>Map / slot / trims</dt><dd className="mono">{rev?.rev} / {bike.currentMapSlot} / {Object.entries(bike.trims).map(([k, v]) => `${k}:${v}`).join(' ')}</dd>
          </dl>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, fontSize: 13.5 }}>
            <input type="checkbox" checked={setupConfirmed} onChange={(e) => setSetupConfirmed(e.target.checked)} />
            I confirm the physical bike matches this record. <a href={`#/bike/${bike.id}`}>Edit setup</a>
          </label>
        </Panel>
      )}

      {step === 5 && (
        <Panel title="Step 6 — Confirm logging hardware">
          {device ? (
            <>
              <dl className="kv">
                <dt>MX Node</dt><dd className="mono">{device.id} <Pill tone="sim">SIMULATED HARDWARE</Pill></dd>
                <dt>Firmware</dt><dd className="mono">{device.firmware}</dd>
                <dt>Battery</dt><dd className="mono">{device.batteryPct}%</dd>
                <dt>Storage</dt><dd className="mono">{device.storagePct}% used</dd>
                <dt>Mode</dt><dd>{device.mode === 'test' ? 'Test mode (expanded sensors)' : 'Competition mode'}</dd>
                <dt>Channels</dt>
                <dd>{Object.entries(device.channelHealth).map(([c, q]) => (
                  <span key={c} style={{ marginRight: 8 }}>
                    <Pill tone={q === 'Missing' || q === 'Out of range' ? 'critical' : q === 'Intermittent' || q === 'Uncalibrated' ? 'serious' : 'neutral'}>{c}: {q}</Pill>
                  </span>
                ))}
                </dd>
              </dl>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, fontSize: 13.5 }}>
                <input type="checkbox" checked={hwConfirmed} onChange={(e) => setHwConfirmed(e.target.checked)} />
                Hardware checks reviewed.
              </label>
            </>
          ) : <p style={{ color: 'var(--critical-text)' }}>No MX Node assigned to this bike — assign one in the Hardware module first.</p>}
        </Panel>
      )}

      {step === 6 && (
        <Panel title="Step 7 — Define the test objective">
          <div className="field"><label>Objective</label>
            <select value={objective} onChange={(e) => setObjective(e.target.value)}>
              {OBJECTIVES.map((o) => <option key={o}>{o}</option>)}
            </select>
          </div>
          <Help id="objective">
            One objective per session. Changing several variables at once makes every conclusion
            unusable — the A/B engine will refuse to attribute differences.
          </Help>
        </Panel>
      )}

      {step === 7 && (
        <Panel title="Step 8 — Start session">
          <p style={{ fontSize: 14 }}>
            <b>{bike?.label}</b> · {rider?.name} · {track?.name} — “{objective}”
          </p>
          {readiness && !readiness.readyForInstrumentedTest ? (
            <p style={{ color: 'var(--critical-text)', fontWeight: 600 }}>Blocked: bike is {readiness.status}. Resolve the failing gates first.</p>
          ) : (
            <>
              <p className="hint">
                Starting records a SIMULATED 12-minute MX Node run (deterministic seed, regenerated on
                demand — no fake measured data is stored). The bike's current map revision is associated
                with this session automatically.
              </p>
              <button className="btn primary" onClick={start}>Start session (SIMULATED)</button>
            </>
          )}
        </Panel>
      )}

      <div className="btn-row" style={{ marginTop: 6 }}>
        <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)}>← Back</button>
        {step < 7 && <button className="btn primary" disabled={!canNext[step]} onClick={() => setStep(step + 1)}>Next →</button>}
      </div>
    </div>
  );
}
