import { checkCompatibility } from './compatibility';
import type { Bike, Db } from './types';

/**
 * Readiness gates (section 19). Overall status equals the worst unresolved
 * critical gate. AI inference can never satisfy a gate — every gate below is
 * computed from confirmed records only.
 */
export interface GateResult {
  id: string;
  label: string;
  critical: boolean;
  pass: boolean;
  detail: string;
}

export type ReadinessStatus =
  | 'Not Inventoried'
  | 'Identity Incomplete'
  | 'Hardware Unknown'
  | 'Map Unknown'
  | 'Maintenance Required'
  | 'Sensor Fault'
  | 'Awaiting Approval'
  | 'Ready for Test'
  | 'Competition Review Required'
  | 'Retired';

export interface Readiness {
  status: ReadinessStatus;
  gates: GateResult[];
  readyForInstrumentedTest: boolean;
}

export function computeReadiness(db: Db, bike: Bike): Readiness {
  const gates: GateResult[] = [];
  const add = (id: string, label: string, critical: boolean, pass: boolean, detail: string) =>
    gates.push({ id, label, critical, pass, detail });

  if (bike.retired) {
    return { status: 'Retired', gates: [], readyForInstrumentedTest: false };
  }

  const model = db.bikeModels.find((m) => m.id === bike.bikeModelId);
  const ecuInst = db.ecuInstances.find((e) => e.id === bike.ecuInstanceId);
  const ecuDef = db.ecuDefinitions.find((d) => d.id === ecuInst?.ecuDefinitionId);
  const build = db.engineBuilds.find((b) => b.id === bike.engineBuildId);
  const device = db.devices.find((d) => d.id === bike.hardwareDeviceId);
  const rev = db.mapRevisions.find((r) => r.id === bike.currentMapRevisionId);

  add('identity', 'Bike identity confirmed', true, bike.identityConfirmed,
    bike.identityConfirmed ? 'Inventory complete.' : 'Phase 0 inventory not confirmed.');
  add('modelYear', 'Model year confirmed', true, bike.modelYearConfirmed && !!model,
    model ? `${model.modelYear} ${model.manufacturer} ${model.model}` : 'No model definition.');
  add('ecu', 'Vortex ECU confirmed', true, !!ecuDef && ecuDef.verification !== 'Unverified',
    ecuDef ? `${ecuDef.model} — ${ecuDef.verification}` : 'No ECU recorded for this bike.');
  add('firmware', 'ECU firmware confirmed', true, !!ecuDef?.firmware,
    ecuDef?.firmware ? `Firmware ${ecuDef.firmware}` : 'Firmware unknown.');
  add('engine', 'Engine build confirmed', true, !!build,
    build ? build.code : 'No engine build assigned.');
  add('fuel', 'Fuel confirmed', true, !!bike.setup.fuelId,
    bike.setup.fuelId || 'Fuel not recorded.');
  add('mapAssigned', 'Map assigned', true, !!rev,
    rev ? `${rev.rev} in slot ${bike.currentMapSlot ?? '?'}` : 'No current map revision.');

  if (rev) {
    const compat = checkCompatibility(rev.compatibility, db, bike);
    add('mapCompatible', 'Map compatible', true, !compat.blocking,
      `${compat.verdict}: ${compat.details[0] ?? ''}`);
    const approvedStates = ['APPROVED_FOR_TEST', 'EXPORTED', 'TRANSFER_CONFIRMED', 'TESTED', 'ACCEPTED', 'TEAM_BASELINE'];
    add('mapApproved', 'Map approved', true, approvedStates.includes(rev.state),
      `Revision state: ${rev.state.replaceAll('_', ' ')}`);
    const transfer = db.transfers.find((t) => t.mapRevisionId === rev.id && t.bikeId === bike.id);
    add('transfer', 'External transfer confirmed', true, !!transfer,
      transfer
        ? `Confirmed by ${transfer.performedByUserId} via ${transfer.externalSoftware}${transfer.simulated ? ' (SIMULATED)' : ''}`
        : 'Loaded revision has no transfer confirmation.');
  }

  add('maintenance', 'Maintenance current', true, bike.maintenanceStatus !== 'Required',
    `Status: ${bike.maintenanceStatus}`);

  add('hardware', 'MX Node mounted', true, !!device,
    device ? `${device.id} (${device.simulated ? 'SIMULATED' : 'real'})` : 'No logging hardware assigned.');
  if (device) {
    const unhealthy = Object.entries(device.channelHealth)
      .filter(([, q]) => q === 'Missing' || q === 'Out of range' || q === 'Intermittent');
    add('sensors', 'Sensor package healthy', true, unhealthy.length === 0,
      unhealthy.length ? unhealthy.map(([c, q]) => `${c}: ${q}`).join('; ') : 'All channels reporting.');
    const uncal = Object.entries(device.channelHealth).filter(([, q]) => q === 'Uncalibrated');
    add('calibration', 'Calibration current', true, uncal.length === 0,
      uncal.length ? uncal.map(([c]) => `${c} uncalibrated`).join('; ') : 'Calibration current.');
    add('storage', 'Storage available', true, device.storagePct < 90,
      `${device.storagePct}% used`);
    add('competition', 'Competition approval reviewed', false,
      device.mode !== 'competition' || device.competitionApprovalStatus !== 'Not reviewed',
      device.mode === 'competition' ? device.competitionApprovalStatus : 'Test mode — not applicable.');
  }

  const failing = gates.filter((g) => !g.pass);
  const failingCritical = failing.filter((g) => g.critical);
  const readyForInstrumentedTest = failingCritical.length === 0;

  let status: ReadinessStatus = 'Ready for Test';
  const worst = failingCritical[0];
  if (worst) {
    status =
      worst.id === 'identity' ? (bike.identityConfirmed ? 'Identity Incomplete' : 'Not Inventoried')
      : worst.id === 'modelYear' || worst.id === 'ecu' || worst.id === 'firmware' || worst.id === 'engine' || worst.id === 'fuel' ? 'Identity Incomplete'
      : worst.id === 'hardware' ? 'Hardware Unknown'
      : worst.id === 'mapAssigned' || worst.id === 'mapCompatible' ? 'Map Unknown'
      : worst.id === 'mapApproved' || worst.id === 'transfer' ? 'Awaiting Approval'
      : worst.id === 'maintenance' ? 'Maintenance Required'
      : worst.id === 'sensors' || worst.id === 'calibration' || worst.id === 'storage' ? 'Sensor Fault'
      : 'Identity Incomplete';
  } else if (failing.some((g) => g.id === 'competition')) {
    status = 'Competition Review Required';
  }

  return { status, gates, readyForInstrumentedTest };
}
