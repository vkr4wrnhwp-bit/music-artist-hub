import React, { useState } from 'react';
import { appendAudit, checkCompatibility, computeReadiness, type Session } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Panel, Pill, readinessTone } from '../ui';

const OBJECTIVES = [
  'Smooth corner-exit delivery', 'Improve start consistency', 'Reduce RPM drop',
  'Improve deep-loam drive', 'Reduce hard-pack wheelspin', 'Improve top-end pull',
  'Reduce rider fatigue', 'Compare map slots', 'Compare trims', 'Compare gearing',
  'Investigate overheating', 'Investigate bog', 'Validate engine build',
];

const STEPS = ['Bike & rider', 'Focus', 'Track', 'Setup', 'Map', 'Hardware', 'Ready'];

export function NewSession() {
  const { db, user, update, allowed } = useApp();
  const [step, setStep] = useState(0);
  const [bikeId, setBikeId] = useState(db.focus?.bikeId ?? '');
  const [riderId, setRiderId] = useState(
    db.bikes.find((b) => b.id === (db.focus?.bikeId ?? ''))?.assignedRiderId ?? '',
  );
  const [trackId, setTrackId] = useState('');
  const [objective, setObjective] = useState(db.focus?.text ?? OBJECTIVES[0]);
  const [weather, setWeather] = useState({ ambientC: 27, humidityPct: 48, baroHpa: 1009, windKph: 8, trackTempC: 34 });
  const [cond, setCond] = useState({ surfaceType: 'Hard pack', preparation: 'Ripped and watered AM', moisture: 'Drying', ruts: 'Forming', bumps: 'Moderate' });
  const [setupConfirmed, setSetupConfirmed] = useState(false);
  const [mapConfirmed, setMapConfirmed] = useState(false);
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
  const map = db.maps.find((m) => m.id === rev?.mapId);
  const build = db.engineBuilds.find((x) => x.id === bike?.engineBuildId);
  const transfer = rev && bike ? db.transfers.find((t) => t.mapRevisionId === rev.id && t.bikeId === bike.id) : undefined;
  const compat = rev && bike ? checkCompatibility(rev.compatibility, db, bike) : null;

  const canNext = [
    !!bike && !!rider,
    !!objective.trim(),
    !!track,
    setupConfirmed,
    mapConfirmed && !!rev && !compat?.blocking,
    hwConfirmed && !!device,
    false,
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
      if (d.focus?.text !== objective || d.focus?.bikeId !== bike.id) {
        d.focus = { bikeId: bike.id, text: objective, setByUserId: user.id };
        appendAudit(d, user.id, 'focus.set', 'Bike', bike.id, `TRACE Focus: ${objective}`);
      }
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
    <div style={{ maxWidth: 720 }}>
      <div className="page-title"><h1>New session</h1><span className="sub">works fully offline</span></div>
      <div className="wiz-steps">
        {STEPS.map((s, i) => (
          <span key={s} className={`ws ${i === step ? 'now' : i < step ? 'done' : ''}`}>{i + 1} · {s}</span>
        ))}
      </div>

      {step === 0 && (
        <Panel title="Bike & rider">
          <div className="grid2">
            <div className="field"><label>Bike</label>
              <select value={bikeId} onChange={(e) => {
                setBikeId(e.target.value);
                setRiderId(db.bikes.find((b) => b.id === e.target.value)?.assignedRiderId ?? '');
              }}>
                <option value="">— select —</option>
                {db.bikes.filter((b) => !b.retired).map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
              </select>
            </div>
            <div className="field"><label>Rider</label>
              <select value={riderId} onChange={(e) => setRiderId(e.target.value)}>
                <option value="">— select —</option>
                {db.riders.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
          </div>
          {bike && readiness && (
            <p style={{ margin: '4px 0 0' }}>
              <Pill tone={readinessTone(readiness.status)}>{readiness.status}</Pill>
              {rider && <span className="hint" style={{ marginLeft: 10 }}>{rider.weightKg} kg · {rider.skillCategory} · prefers {rider.preferredDelivery.toLowerCase()}</span>}
            </p>
          )}
          {readiness && !readiness.readyForInstrumentedTest && (
            <div style={{ marginTop: 10 }}>
              <p style={{ color: 'var(--critical)', fontWeight: 650, fontSize: 13, margin: 0 }}>Not ready — failing gates:</p>
              <ul style={{ margin: '4px 0', paddingLeft: 18, fontSize: 13 }}>
                {readiness.gates.filter((g) => g.critical && !g.pass).map((g) => <li key={g.id}>{g.label}: {g.detail}</li>)}
              </ul>
              <a href={`#/bike/${bike!.id}`}>Resolve in bike profile →</a>
            </div>
          )}
        </Panel>
      )}

      {step === 1 && (
        <Panel title="TRACE Focus — what is this session for?">
          <Help id="objective">
            One session, one objective. TRACE biases setup and post-session analysis toward answering
            it — changing several variables at once makes every conclusion unusable.
          </Help>
          <div className="field"><label>Focus</label>
            <textarea rows={2} value={objective} onChange={(e) => setObjective(e.target.value)} />
          </div>
          <div className="btn-row">
            {OBJECTIVES.slice(0, 6).map((o) => (
              <button key={o} className="btn small ghost" onClick={() => setObjective(o)}>{o}</button>
            ))}
          </div>
          {db.focus?.text && db.focus.text === objective && <p className="hint">Carried over from today's focus — one tap to keep.</p>}
        </Panel>
      )}

      {step === 2 && (
        <Panel title="Track & conditions">
          <div className="field"><label>Track</label>
            <select value={trackId} onChange={(e) => setTrackId(e.target.value)}>
              <option value="">— select —</option>
              {db.tracks.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          {track && <p className="hint" style={{ marginBottom: 12 }}>{track.kind === 'motocross' ? 'Motocross' : 'SX test'} · {track.direction} · {track.surface} · {track.segments.length} sections</p>}
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

      {step === 3 && bike && (
        <Panel title="Confirm setup">
          <dl className="kv">
            <dt>Fuel</dt><dd>{db.fuels.find((f) => f.id === bike.setup.fuelId)?.name}</dd>
            <dt>Gearing</dt><dd className="mono">{bike.setup.gearing}</dd>
            <dt>Tires</dt><dd>{bike.setup.tireModel} · F {bike.setup.tirePressureFront} / R {bike.setup.tirePressureRear} bar</dd>
            <dt>Suspension</dt><dd>fork {bike.setup.forkHeightMm} mm · sag {bike.setup.sagMm} mm</dd>
            <dt>Clutch</dt><dd>{bike.setup.clutch}</dd>
            <dt>Engine</dt><dd className="mono">{build?.code}</dd>
          </dl>
          <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 14, fontSize: 14 }}>
            <input type="checkbox" checked={setupConfirmed} onChange={(e) => setSetupConfirmed(e.target.checked)} />
            The physical bike matches this record. <a href={`#/bike/${bike.id}`}>Edit</a>
          </label>
        </Panel>
      )}

      {step === 4 && bike && (
        <Panel title="Confirm map">
          {rev ? (
            <>
              <dl className="kv">
                <dt>Map</dt><dd className="mono">{map?.name}-{rev.rev} · Slot {bike.currentMapSlot}</dd>
                <dt>State</dt><dd>{rev.state.replaceAll('_', ' ')}</dd>
                <dt>Trims</dt><dd className="mono">{Object.entries(bike.trims).map(([k, v]) => `${k}:${v}`).join(' · ')}</dd>
                <dt>Transfer</dt>
                <dd>{transfer ? <Pill tone="good">Confirmed (SIM)</Pill> : <Pill tone="critical">Not confirmed</Pill>}</dd>
                <dt>Compatibility</dt>
                <dd>{compat && <Pill tone={compat.blocking ? 'critical' : 'good'}>{compat.verdict}</Pill>}</dd>
              </dl>
              <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 14, fontSize: 14 }}>
                <input type="checkbox" checked={mapConfirmed} onChange={(e) => setMapConfirmed(e.target.checked)} />
                This is the map physically loaded on the ECU.
              </label>
            </>
          ) : <p style={{ color: 'var(--critical)' }}>No map assigned — load one via the Tune area first.</p>}
        </Panel>
      )}

      {step === 5 && (
        <Panel title="Confirm logging hardware">
          {device ? (
            <>
              <dl className="kv">
                <dt>MX Node</dt><dd className="mono">{device.id} <Pill tone="sim">SIMULATED</Pill></dd>
                <dt>Battery / storage</dt><dd className="mono">{device.batteryPct}% · {device.storagePct}% used</dd>
                <dt>Mode</dt><dd>{device.mode}</dd>
                <dt>Channels</dt>
                <dd>{Object.entries(device.channelHealth).map(([c, q]) => (
                  <span key={c} style={{ marginRight: 6 }}>
                    <Pill tone={q === 'Missing' || q === 'Out of range' ? 'critical' : q === 'Intermittent' || q === 'Uncalibrated' ? 'serious' : 'neutral'}>{c}</Pill>
                  </span>
                ))}
                </dd>
              </dl>
              <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 14, fontSize: 14 }}>
                <input type="checkbox" checked={hwConfirmed} onChange={(e) => setHwConfirmed(e.target.checked)} />
                Hardware checks reviewed.
              </label>
            </>
          ) : <p style={{ color: 'var(--critical)' }}>No MX Node assigned to this bike — assign one in the bike profile.</p>}
        </Panel>
      )}

      {step === 6 && (
        <Panel title="Ready">
          <p style={{ fontSize: 16, fontWeight: 650, margin: '0 0 4px' }}>{bike?.label} · {rider?.name} · {track?.name}</p>
          <p className="focus-text" style={{ fontSize: 16, color: 'var(--ink-2)' }}>“{objective}”</p>
          {readiness && !readiness.readyForInstrumentedTest ? (
            <p style={{ color: 'var(--critical)', fontWeight: 650 }}>Blocked: bike is {readiness.status}.</p>
          ) : (
            <>
              <p className="hint" style={{ margin: '10px 0 16px' }}>
                Starting records a SIMULATED 12-minute MX Node run — deterministic seed, regenerated on
                demand, never stored as measured data.
              </p>
              <button className="btn primary big" onClick={start}>Start Session</button>
            </>
          )}
        </Panel>
      )}

      <div className="btn-row" style={{ marginTop: 4 }}>
        <button className="btn ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>← Back</button>
        {step < 6 && <button className="btn primary" disabled={!canNext[step]} onClick={() => setStep(step + 1)}>Next →</button>}
      </div>
    </div>
  );
}
