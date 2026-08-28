import React from 'react';
import { appendAudit, DIRECT_WRITE_LABEL } from '@mxlab/domain';
import { useApp } from '../state';
import { Help, Panel, Pill } from '../ui';

const COMPETITION_NOTICE =
  'COMPETITION USE REQUIRES APPROVAL FROM THE APPLICABLE SANCTIONING BODY. SOFTWARE CONFIGURATION DOES NOT ESTABLISH LEGALITY.';

export function Hardware() {
  const { db, user, update, allowed } = useApp();
  const canManage = allowed('hardware.manage');

  return (
    <div>
      <div className="page-title">
        <h1>MX Node hardware</h1>
        <span className="sub">passive loggers only — a node failure can never affect the motorcycle</span>
        <Pill tone="sim">ALL PHASE 1 DEVICES ARE SIMULATED</Pill>
      </div>
      <Help id="hardware">
        The MX Node is a passive listener on a verified data output. It has no path — electrical or
        software — to fueling, ignition, throttle, or map slots. Phase 2 replaces these simulated
        devices behind the same read-only adapter interface (docs/hardware/adapter-spec.md).
      </Help>
      <div className="write-disabled" style={{ marginBottom: 16 }}>{DIRECT_WRITE_LABEL}</div>

      <div className="cols">
        {db.devices.map((dev) => {
          const bike = db.bikes.find((b) => b.id === dev.assignedBikeId);
          return (
            <Panel key={dev.id} title={`${dev.id} — ${bike?.label ?? 'unassigned'}`} actions={<Pill tone="sim">SIMULATED HARDWARE</Pill>}>
              <dl className="kv">
                <dt>Hardware rev</dt><dd className="mono">{dev.hardwareRev}</dd>
                <dt>Firmware</dt><dd className="mono">{dev.firmware}</dd>
                <dt>Battery</dt><dd className="mono">{dev.batteryPct}%</dd>
                <dt>Storage</dt><dd className="mono">{dev.storagePct}% used</dd>
                <dt>Last sync</dt><dd>{dev.lastSync ? new Date(dev.lastSync).toLocaleString() : '—'}</dd>
                <dt>Enclosure / mount</dt><dd className="mono">{dev.enclosureRev} · {dev.mountRev}</dd>
                <dt>Mode</dt>
                <dd>
                  <Pill tone={dev.mode === 'competition' ? 'warning' : 'neutral'}>{dev.mode.toUpperCase()}</Pill>{' '}
                  {canManage && (
                    <button className="btn small" onClick={() => update((d) => {
                      const x = d.devices.find((v) => v.id === dev.id)!;
                      x.mode = x.mode === 'test' ? 'competition' : 'test';
                      appendAudit(d, user!.id, 'hardware.mode', 'HardwareDevice', x.id, `Mode set to ${x.mode}.`);
                    })}>Switch to {dev.mode === 'test' ? 'competition' : 'test'}</button>
                  )}
                </dd>
                {dev.mode === 'competition' && (
                  <>
                    <dt>Radio</dt>
                    <dd>
                      <Pill tone={dev.radioDisabled ? 'good' : 'critical'}>{dev.radioDisabled ? 'Physically disabled (confirmed)' : 'NOT confirmed disabled'}</Pill>{' '}
                      {canManage && !dev.radioDisabled && (
                        <button className="btn small" onClick={() => update((d) => {
                          const x = d.devices.find((v) => v.id === dev.id)!;
                          x.radioDisabled = true;
                          appendAudit(d, user!.id, 'hardware.radio_disable', 'HardwareDevice', x.id, 'Radio-disable confirmed (SIMULATED).');
                        })}>Confirm radio disabled</button>
                      )}
                    </dd>
                    <dt>Competition approval</dt><dd><Pill tone={dev.competitionApprovalStatus === 'Approved by team' ? 'good' : 'warning'}>{dev.competitionApprovalStatus}</Pill></dd>
                  </>
                )}
              </dl>
              <h4 style={{ margin: '10px 0 6px', fontSize: 13 }}>Channel health</h4>
              <div className="btn-row">
                {Object.entries(dev.channelHealth).map(([c, q]) => (
                  <Pill key={c} tone={q === 'Missing' || q === 'Out of range' ? 'critical' : q === 'Intermittent' || q === 'Uncalibrated' ? 'serious' : 'neutral'}>{c}: {q}</Pill>
                ))}
              </div>
              {dev.openIssues.length > 0 && (
                <p style={{ fontSize: 13, marginTop: 8, color: 'var(--serious-text)' }}>Open: {dev.openIssues.join('; ')}</p>
              )}
              {dev.mode === 'competition' && (
                <p className="hint" style={{ marginTop: 10, fontWeight: 700 }}>{COMPETITION_NOTICE}</p>
              )}
            </Panel>
          );
        })}
      </div>

      <Panel title="Target telemetry channels (to validate against real Vortex hardware)">
        <Help id="channels">
          These are <b>targets, not guarantees</b>. Real channel availability, rates, and scaling must be
          verified per ECU during Phase 2 bench work — see docs/testing/known-unknowns.md.
        </Help>
        <div className="tbl-scroll">
          <table className="data">
            <thead><tr><th>Channel</th><th>Unit</th><th>Rate</th><th>Range</th><th>Quality</th><th>Verification</th><th>Test-only</th></tr></thead>
            <tbody>
              {db.telemetryChannels.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td className="mono">{c.unit || '—'}</td>
                  <td className="num">{c.sampleRateHz} Hz</td>
                  <td className="num">{c.validMin}–{c.validMax}</td>
                  <td><Pill tone="sim">{c.quality}</Pill></td>
                  <td>{c.verification}</td>
                  <td>{c.testOnly ? 'Yes — not for competition' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

export function CncModule() {
  const { db } = useApp();
  return (
    <div>
      <div className="page-title">
        <h1>CNC hardware program</h1>
        <span className="sub">data quality, durability, and workflow first — no engine parts</span>
      </div>
      <Help id="cnc">
        Each part links to its engineering brief in docs/cnc/. Dimensions marked TBD require measurement
        on the physical bike, per model year — the YZ250F and YZ450F mounts are deliberately separate
        designs. No unvalidated production G-code is generated.
      </Help>
      <Panel title="Part registry">
        <div className="tbl-scroll">
          <table className="data">
            <thead><tr><th>P/N</th><th>Name</th><th>Category</th><th>Bike model</th><th>Material</th><th>Rev</th><th>Status</th><th>Brief</th></tr></thead>
            <tbody>
              {db.cncParts.map((p) => {
                const latest = p.revisions[p.revisions.length - 1];
                const model = db.bikeModels.find((m) => m.id === p.bikeModelId);
                return (
                  <tr key={p.id}>
                    <td className="mono">{p.partNumber}</td>
                    <td>{p.name}</td>
                    <td>{p.category}</td>
                    <td>{model ? `${model.modelYear} ${model.model}` : 'Universal (justified per brief)'}</td>
                    <td>{p.material}</td>
                    <td className="mono">{latest?.rev}</td>
                    <td><Pill tone={latest?.status === 'Released' ? 'good' : 'neutral'}>{latest?.status}</Pill></td>
                    <td className="mono" style={{ fontSize: 11.5 }}>{p.briefDoc}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="cols">
        {db.cncParts.map((p) => (
          <Panel key={p.id} title={`${p.partNumber} — BOM & revisions`}>
            <table className="data">
              <thead><tr><th>BOM item</th><th>Qty</th><th>Note</th></tr></thead>
              <tbody>
                {p.bom.map((b, i) => <tr key={i}><td>{b.item}</td><td className="num">{b.qty}</td><td>{b.note ?? '—'}</td></tr>)}
              </tbody>
            </table>
            <h4 style={{ margin: '10px 0 4px', fontSize: 13 }}>Revision history</h4>
            {p.revisions.map((r) => (
              <p key={r.rev} style={{ margin: '2px 0', fontSize: 13 }}>
                <b className="mono">{r.rev}</b> · {r.date} — {r.change} <Pill tone="neutral">{r.status}</Pill>
              </p>
            ))}
          </Panel>
        ))}
      </div>
    </div>
  );
}
