import React from 'react';
import { DIRECT_WRITE_LABEL, FUTURE_FLASH_DISABLED_MESSAGE } from '@mxlab/domain';
import { useApp } from '../state';
import { Help, Panel, Pill } from '../ui';

export function EcuProfile({ ecuDefId }: { ecuDefId: string }) {
  const { db } = useApp();
  const def = db.ecuDefinitions.find((d) => d.id === ecuDefId);
  if (!def) return <p>ECU definition not found.</p>;
  const inst = db.ecuInstances.find((i) => i.ecuDefinitionId === def.id);
  const bike = db.bikes.find((b) => b.id === inst?.installedBikeId);

  const verTone = (v: string) =>
    v === 'Team Approved' || v === 'Bike Verified' ? 'good'
      : v === 'Bench Verified' || v === 'Documentation Verified' || v === 'Physically Inspected' ? 'warning'
        : 'critical';

  return (
    <div>
      <div className="page-title">
        <h1>{def.model}</h1>
        <span className="sub">{def.manufacturer} · installed on {bike ? bike.label : 'no bike'}</span>
        <Pill tone="sim">SIMULATED DEFINITION</Pill>
      </div>
      <Help id="ecu">
        Nothing in MX LAB assumes what this ECU can do. Every capability below carries a
        <b> verification status and a source</b>; unverified capabilities never render controls anywhere
        in the app. Real Vortex identities are captured during Phase 0 inventory.
      </Help>
      <div className="cols">
        <div>
          <Panel title="Identity">
            <dl className="kv">
              <dt>Family</dt><dd>{def.family}</dd>
              <dt>Model</dt><dd>{def.model}</dd>
              <dt>Serial</dt><dd className="mono">{inst?.serialNumber ?? '—'}</dd>
              <dt>Firmware</dt><dd className="mono">{def.firmware}</dd>
              <dt>Software</dt><dd className="mono">{def.softwareVersion ?? '—'}</dd>
              <dt>Connector</dt><dd>{def.connector} <Pill tone={verTone(def.connectorVerification)}>{def.connectorVerification}</Pill></dd>
              <dt>Map slots</dt><dd className="mono">{def.mapSlotCount ?? 'unknown'}</dd>
              <dt>Global trims</dt><dd className="mono">{def.globalTrims.join(' · ') || 'none verified'}</dd>
              <dt>Verification</dt><dd><Pill tone={verTone(def.verification)}>{def.verification}</Pill> {def.lastVerified && <span className="hint">last {def.lastVerified}</span>}</dd>
            </dl>
            {def.notes && <p className="hint">{def.notes}</p>}
          </Panel>
          <Panel title="Write access">
            <div className="write-disabled">{DIRECT_WRITE_LABEL}</div>
            <p className="hint" style={{ marginTop: 8 }}>
              Phase 1 never writes to an ECU. Map changes travel through the companion workflow: the
              tuner performs the change in the official Vortex software and confirms it here. The Phase 4
              flash-job slot exists in the schema with status <b>DISABLED</b>: “{FUTURE_FLASH_DISABLED_MESSAGE}”.
            </p>
          </Panel>
        </div>
        <Panel title="Verified capabilities">
          <div className="tbl-scroll">
            <table className="data">
              <thead><tr><th>Capability</th><th>Kind</th><th>Verification</th><th>Source</th></tr></thead>
              <tbody>
                {def.capabilities.map((c) => (
                  <tr key={c.id}>
                    <td>{c.label}</td>
                    <td className="mono">{c.kind}</td>
                    <td><Pill tone={verTone(c.verification)}>{c.verification}</Pill></td>
                    <td className="hint">{c.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint">
            Verification ladder: Unverified → Physically Inspected → Documentation Verified → Bench
            Verified → Bike Verified → Team Approved. See docs/vortex/integration-boundary.md.
          </p>
        </Panel>
      </div>
    </div>
  );
}
