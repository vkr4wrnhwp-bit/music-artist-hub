import React, { useState } from 'react';
import { appendAudit, type Bike } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Panel } from '../ui';

/** Phase 0 inventory entry: a new bike starts NOT INVENTORIED and cannot be
 *  tested until a person confirms its identity fields. */
export function RegisterBike() {
  const { db, user, update, allowed } = useApp();
  const [label, setLabel] = useState('');
  const [modelId, setModelId] = useState(db.bikeModels[0]?.id ?? '');
  const [ecuDefId, setEcuDefId] = useState(db.ecuDefinitions[0]?.id ?? '');
  const [serial, setSerial] = useState('');
  const [buildId, setBuildId] = useState('');
  const [riderId, setRiderId] = useState('');

  if (!user || !allowed('bike.create')) {
    return <Panel title="Register bike"><p>Your role cannot register bikes.</p></Panel>;
  }
  const builds = db.engineBuilds.filter((b) => b.bikeModelId === modelId);

  const create = () => {
    if (!label.trim() || !serial.trim() || !buildId) return;
    const bikeId = `bike-${Date.now()}`;
    update((d) => {
      const instId = `ecuinst-${Date.now()}`;
      d.ecuInstances.push({ id: instId, ecuDefinitionId: ecuDefId, serialNumber: serial.trim(), installedBikeId: bikeId, simulated: true });
      const bike: Bike = {
        id: bikeId, orgId: d.org.id, label: label.trim(), bikeModelId: modelId,
        ecuInstanceId: instId, engineBuildId: buildId, assignedRiderId: riderId || undefined,
        setup: {
          fuelId: d.fuels[0].id, exhaustId: d.exhausts[1]?.id ?? d.exhausts[0].id, gearing: '13/50',
          suspension: 'Stock', tireModel: 'Race tire (fictional)', tireSizeRear: '110/90-19',
          tirePressureFront: 0.85, tirePressureRear: 0.85, clutch: 'Stock',
          forkHeightMm: 5, sagMm: 105,
        },
        trims: Object.fromEntries((d.ecuDefinitions.find((e) => e.id === ecuDefId)?.globalTrims ?? []).map((t) => [t, 5])),
        totalHours: 0, hoursSinceRebuild: 0, maintenanceStatus: 'Current',
        identityConfirmed: false, modelYearConfirmed: false, retired: false, openIssues: [],
      };
      d.bikes.push(bike);
      d.mapSlots[bikeId] = Array.from({ length: 10 }, (_, i) => ({ slot: i + 1 }));
      appendAudit(d, user.id, 'bike.create', 'Bike', bikeId,
        `${bike.label} registered — Phase 0 inventory open (identity unconfirmed).`);
    });
    nav(`bike/${bikeId}`);
  };

  return (
    <div>
      <div className="page-title"><h1>Register bike (Phase 0 inventory)</h1></div>
      <Help id="register">
        Registration only opens the record. The bike stays <b>Not Inventoried</b> until a person
        confirms the identity on the physical machine — exact ECU, firmware, engine build, fuel.
      </Help>
      <Panel title="Identity">
        <div className="grid2">
          <div className="field"><label>Bike ID / label</label>
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. CMX-250-05" />
          </div>
          <div className="field"><label>Model</label>
            <select value={modelId} onChange={(e) => { setModelId(e.target.value); setBuildId(''); }}>
              {db.bikeModels.map((m) => <option key={m.id} value={m.id}>{m.modelYear} {m.manufacturer} {m.model}</option>)}
            </select>
          </div>
          <div className="field"><label>Vortex ECU definition (simulated)</label>
            <select value={ecuDefId} onChange={(e) => setEcuDefId(e.target.value)}>
              {db.ecuDefinitions.map((e) => <option key={e.id} value={e.id}>{e.model} · fw {e.firmware}</option>)}
            </select>
          </div>
          <div className="field"><label>ECU serial number</label>
            <input value={serial} onChange={(e) => setSerial(e.target.value)} placeholder="from the physical unit" />
          </div>
          <div className="field"><label>Engine build</label>
            <select value={buildId} onChange={(e) => setBuildId(e.target.value)}>
              <option value="">— select —</option>
              {builds.map((b) => <option key={b.id} value={b.id}>{b.code}</option>)}
            </select>
          </div>
          <div className="field"><label>Assigned rider (optional)</label>
            <select value={riderId} onChange={(e) => setRiderId(e.target.value)}>
              <option value="">— none —</option>
              {db.riders.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
        </div>
        <button className="btn primary" disabled={!label.trim() || !serial.trim() || !buildId} onClick={create}>
          Register — opens as Not Inventoried
        </button>
      </Panel>
    </div>
  );
}
