import { buildRecommendation, compareSessions, decideRecommendation, telemetrySupportsPreference } from './aiEngineer';
import { appendAudit } from './audit';
import { SCHEMA_VERSION } from './store';
import type {
  Bike, Db, EcuDefinition, EventMarker, MapRevision, Session, StartAttempt,
  TelemetryChannelDef, Track, User,
} from './types';

/**
 * SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE.
 * Every entity here is fictional. ECU definitions are simulated stand-ins:
 * no real Vortex model, firmware, channel list, or map format is asserted.
 */

export const DEMO_BANNER = 'SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE';

const RPM_BP = [2000, 3500, 5000, 6500, 8000, 9500, 11000, 12500];
const TPS_BP = [0, 10, 20, 40, 60, 80, 100];

function shapedTable(fn: (rpm: number, tps: number) => number): number[][] {
  return RPM_BP.map((rpm) => TPS_BP.map((tps) => +fn(rpm, tps).toFixed(1)));
}
const zeros = () => shapedTable(() => 0);

function demoUsers(orgId: string): User[] {
  const mk = (id: string, name: string, role: User['role']): User =>
    ({ id, orgId, name, role, simulatedLogin: true });
  return [
    mk('u-admin', 'Alex Ferro', 'org_admin'),
    mk('u-manager', 'Sam Calloway', 'team_manager'),
    mk('u-chief', 'Dana Merrick', 'crew_chief'),
    mk('u-tuner', 'Jules Ortiz', 'tuner'),
    mk('u-mech', 'Casey Trần', 'mechanic'),
    mk('u-builder', 'Rowan Diaz', 'engine_builder'),
    mk('u-susp', 'Kit Yamada', 'suspension_tech'),
    mk('u-rider1', 'Blake Harmon', 'rider'),
    mk('u-rider2', 'Devon Cole', 'rider'),
    mk('u-data', 'Priya Nair', 'data_engineer'),
    mk('u-hw', 'Marlo Beck', 'hardware_engineer'),
    mk('u-view', 'Guest Viewer', 'viewer'),
  ];
}

function targetChannels(): TelemetryChannelDef[] {
  const mk = (id: string, name: string, unit: string, hz: number, min: number, max: number,
    testOnly = false): TelemetryChannelDef => ({
    id, name, unit, sampleRateHz: hz, dataType: 'f32', scale: 1, offset: 0,
    validMin: min, validMax: max, source: 'Simulated MX Node (target channel — real availability requires Vortex verification)',
    quality: 'Simulated', timestampSource: 'session clock', verification: 'Unverified', testOnly,
  });
  return [
    mk('rpm', 'Engine RPM', 'rpm', 10, 0, 14500),
    mk('tps', 'Throttle position', '%', 10, 0, 100),
    mk('speed', 'GPS speed', 'kph', 10, 0, 140),
    mk('accel', 'Longitudinal acceleration', 'g', 10, -2, 2),
    mk('coolant', 'Coolant temperature', '°C', 1, 0, 130),
    mk('iat', 'Intake-air temperature', '°C', 1, -10, 60),
    mk('battv', 'Battery voltage', 'V', 1, 8, 16),
    mk('slip', 'Rear slip estimate', '%', 10, 0, 100, true),
    mk('clutch', 'Clutch position', '%', 10, 0, 100, true),
    mk('fork', 'Fork travel', 'mm', 10, 0, 310, true),
    mk('shock', 'Shock travel', 'mm', 10, 0, 150, true),
    mk('gear', 'Gear estimate', '', 10, 0, 5),
  ];
}

function demoEcuDefs(): EcuDefinition[] {
  const caps = (src: string): EcuDefinition['capabilities'] => [
    { id: 'cap-fuel', kind: 'map_table', label: 'Fuel offset table', source: src, verification: 'Physically Inspected' },
    { id: 'cap-ign', kind: 'map_table', label: 'Ignition offset table', source: src, verification: 'Physically Inspected' },
    { id: 'cap-trims', kind: 'global_trim', label: 'Low / Mid / High global trims', source: src, verification: 'Physically Inspected' },
    { id: 'cap-slots', kind: 'map_slots', label: '10 map slots (configurable example — not a universal Vortex rule)', source: src, verification: 'Physically Inspected' },
    { id: 'cap-diag', kind: 'diagnostic', label: 'Fault-code readout', source: src, verification: 'Unverified' },
  ];
  return [
    {
      id: 'ecu-sim-250', manufacturer: 'Vortex (simulated definition)', family: 'Pending physical verification',
      model: 'SIM-DEMO-250 — exact model pending verification', firmware: 'SIM-FW-2.4.1',
      softwareVersion: 'SIM-SW-1.9', connector: 'Pending harness inspection', connectorVerification: 'Unverified',
      mapSlotCount: 10, globalTrims: ['Low', 'Mid', 'High'],
      capabilities: caps('Simulated demo definition — replace after Phase 0 inventory'),
      compatibleBikeModelIds: ['model-yz250f-2026'], verification: 'Physically Inspected',
      lastVerified: '2026-07-30', notes: 'SIMULATED. Created to exercise the workflow only.', simulated: true,
    },
    {
      id: 'ecu-sim-450', manufacturer: 'Vortex (simulated definition)', family: 'Pending physical verification',
      model: 'SIM-DEMO-450 — exact model pending verification', firmware: 'SIM-FW-3.0.2',
      softwareVersion: 'SIM-SW-2.1', connector: 'Pending harness inspection', connectorVerification: 'Unverified',
      mapSlotCount: 10, globalTrims: ['Low', 'Mid', 'High'],
      capabilities: caps('Simulated demo definition — replace after Phase 0 inventory'),
      compatibleBikeModelIds: ['model-yz450f-2025'], verification: 'Physically Inspected',
      lastVerified: '2026-07-30', notes: 'SIMULATED. Created to exercise the workflow only.', simulated: true,
    },
  ];
}

function demoTracks(): Track[] {
  // hand-drawn closed loops, normalized 0..1
  const mxPath: Array<[number, number]> = [
    [0.08, 0.62], [0.12, 0.42], [0.22, 0.28], [0.38, 0.22], [0.52, 0.26], [0.60, 0.38],
    [0.55, 0.50], [0.44, 0.55], [0.42, 0.66], [0.52, 0.74], [0.68, 0.74], [0.82, 0.66],
    [0.90, 0.52], [0.88, 0.34], [0.78, 0.22], [0.66, 0.16], [0.50, 0.12], [0.32, 0.10],
    [0.18, 0.14], [0.09, 0.28], [0.06, 0.46], [0.08, 0.62],
  ];
  const sxPath: Array<[number, number]> = [
    [0.10, 0.70], [0.10, 0.30], [0.25, 0.18], [0.45, 0.18], [0.55, 0.30], [0.45, 0.42],
    [0.30, 0.44], [0.30, 0.58], [0.48, 0.62], [0.66, 0.56], [0.72, 0.40], [0.66, 0.24],
    [0.80, 0.16], [0.92, 0.28], [0.92, 0.55], [0.80, 0.72], [0.60, 0.80], [0.35, 0.82],
    [0.16, 0.80], [0.10, 0.70],
  ];
  return [
    {
      id: 'track-pinegrove', name: 'Pine Grove MX (fictional)', kind: 'motocross', direction: 'CW',
      surface: 'Hard pack over clay', elevationM: 210, path: mxPath,
      segments: [
        { id: 'seg-start', name: 'Start straight', startFrac: 0, endFrac: 0.09 },
        { id: 'seg-c2', name: 'Corner 2 sweeper', startFrac: 0.09, endFrac: 0.2 },
        { id: 'seg-whoops', name: 'Whoop section', startFrac: 0.2, endFrac: 0.34 },
        { id: 'seg-c6', name: 'Corner 6 rut exit', startFrac: 0.34, endFrac: 0.48 },
        { id: 'seg-back', name: 'Back straight', startFrac: 0.48, endFrac: 0.68 },
        { id: 'seg-c9', name: 'Corner 9 off-camber', startFrac: 0.68, endFrac: 0.84 },
        { id: 'seg-finish', name: 'Finish table', startFrac: 0.84, endFrac: 1 },
      ],
    },
    {
      id: 'track-sxtest', name: 'Ridgeline SX Test Track (fictional)', kind: 'supercross_test', direction: 'CCW',
      surface: 'Groomed loam', elevationM: 180, path: sxPath,
      segments: [
        { id: 'sx-start', name: 'Gate & holeshot lane', startFrac: 0, endFrac: 0.1 },
        { id: 'sx-rhythm1', name: 'Rhythm lane 1', startFrac: 0.1, endFrac: 0.32 },
        { id: 'sx-bowl', name: 'Bowl turn', startFrac: 0.32, endFrac: 0.44 },
        { id: 'sx-whoops', name: 'Whoops', startFrac: 0.44, endFrac: 0.62 },
        { id: 'sx-rhythm2', name: 'Rhythm lane 2', startFrac: 0.62, endFrac: 0.86 },
        { id: 'sx-finish', name: 'Finish jump', startFrac: 0.86, endFrac: 1 },
      ],
    },
  ];
}

export function createSeededDb(): Db {
  const orgId = 'org-demo';
  const users = demoUsers(orgId);
  const ecuDefs = demoEcuDefs();
  const tracks = demoTracks();

  const db: Db = {
    schemaVersion: SCHEMA_VERSION,
    org: { id: orgId, name: 'TRACE Demo Team (fictional)' },
    focus: { bikeId: 'bike-250', text: 'Improve drive from Corner 6 without reducing midrange.', setByUserId: 'u-chief' },
    users,
    riders: [
      { id: 'rider-1', orgId, name: 'Blake Harmon', userId: 'u-rider1', weightKg: 72, skillCategory: 'Pro', preferredDelivery: 'Linear bottom, strong mid' },
      { id: 'rider-2', orgId, name: 'Devon Cole', userId: 'u-rider2', weightKg: 66, skillCategory: 'Pro', preferredDelivery: 'Soft first touch, aggressive top' },
    ],
    riderPrefs: [
      { riderId: 'rider-1', preferredInitialHit: 'linear', preferredEngineBraking: 'medium', typicalThrottleRate: 'moderate', surfaceNotes: { 'hard pack': 'wants traction over hit' }, learnedFrom: [], provenance: 'RIDER REPORTED' },
      { riderId: 'rider-2', preferredInitialHit: 'soft', preferredEngineBraking: 'low', typicalThrottleRate: 'abrupt', surfaceNotes: { loam: 'comfortable with aggressive delivery' }, learnedFrom: [], provenance: 'RIDER REPORTED' },
    ],
    bikeModels: [
      { id: 'model-yz250f-2026', manufacturer: 'Yamaha', model: 'YZ250F', modelYear: 2026 },
      { id: 'model-yz450f-2025', manufacturer: 'Yamaha', model: 'YZ450F', modelYear: 2025 },
    ],
    bikes: [],
    ecuDefinitions: ecuDefs,
    ecuInstances: [
      { id: 'ecuinst-250', ecuDefinitionId: 'ecu-sim-250', serialNumber: 'SIM-SN-0042', installedBikeId: 'bike-250', simulated: true },
      { id: 'ecuinst-450', ecuDefinitionId: 'ecu-sim-450', serialNumber: 'SIM-SN-0117', installedBikeId: 'bike-450', simulated: true },
    ],
    engineBuilds: [
      { id: 'build-250-b07', code: 'CMX250-B07', bikeModelId: 'model-yz250f-2026', camshaft: 'Stage 1 (fictional)', compression: 'Stock', injector: 'Stock', throttleBody: 'Stock 44 mm', revLimit: 13500, builtBy: 'u-builder', provenance: 'ENGINE BUILDER ENTERED', notes: 'Fresh top end at 15.2 h.' },
      { id: 'build-250-b08', code: 'CMX250-B08', bikeModelId: 'model-yz250f-2026', camshaft: 'Stage 1 (fictional)', compression: 'High-comp piston (fictional)', injector: 'Stock', throttleBody: 'Stock 44 mm', revLimit: 13500, builtBy: 'u-builder', provenance: 'ENGINE BUILDER ENTERED', notes: 'Bench build — not yet installed.' },
      { id: 'build-450-b03', code: 'CMX450-B03', bikeModelId: 'model-yz450f-2025', camshaft: 'Stock', compression: 'Stock', injector: 'Stock', throttleBody: 'Stock 44 mm', revLimit: 11900, builtBy: 'u-builder', provenance: 'ENGINE BUILDER ENTERED', notes: 'Race engine, 3.4 h since rebuild.' },
    ],
    fuels: [
      { id: 'fuel-team-01', name: 'Team Fuel 01 (fictional race fuel)' },
      { id: 'fuel-pump-93', name: 'Pump 93 octane' },
    ],
    exhausts: [
      { id: 'exh-cfg-01', name: 'Exhaust configuration 01 (stock)' },
      { id: 'exh-cfg-02', name: 'Exhaust configuration 02 (race system, fictional)' },
    ],
    tracks,
    maps: [],
    mapRevisions: [],
    mapSlots: {},
    envelopes: [
      { id: 'env-250', ecuDefinitionId: 'ecu-sim-250', version: 'ENV-1', maxStepDelta: { fuel: 3, ignition: 1.5 }, definedByUserId: 'u-tuner', note: 'Single A/B step limits validated by tuner for the simulated demo definition.' },
      { id: 'env-450', ecuDefinitionId: 'ecu-sim-450', version: 'ENV-1', maxStepDelta: { fuel: 3, ignition: 1.5 }, definedByUserId: 'u-tuner', note: 'Single A/B step limits validated by tuner for the simulated demo definition.' },
    ],
    transfers: [],
    sessions: [],
    markers: [],
    feedback: [],
    startAttempts: [],
    recommendations: [],
    abTests: [],
    devices: [
      {
        id: 'node-01', orgId, kind: 'MX_NODE', hardwareRev: 'SIM-A1', firmware: 'sim-0.9.2',
        assignedBikeId: 'bike-250', batteryPct: 87, storagePct: 22, lastSync: '2026-08-11T17:40:00Z',
        channelHealth: { rpm: 'Simulated', tps: 'Simulated', speed: 'Simulated', slip: 'Simulated', coolant: 'Simulated' },
        mode: 'test', radioDisabled: false, competitionApprovalStatus: 'Not reviewed',
        enclosureRev: 'ENC-A0 (brief only)', mountRev: 'MNT-250-A0 (brief only)', openIssues: [], simulated: true,
      },
      {
        id: 'node-02', orgId, kind: 'MX_NODE', hardwareRev: 'SIM-A1', firmware: 'sim-0.9.2',
        assignedBikeId: 'bike-450', batteryPct: 64, storagePct: 41, lastSync: '2026-08-11T18:05:00Z',
        channelHealth: { rpm: 'Simulated', tps: 'Simulated', speed: 'Simulated', slip: 'Missing', coolant: 'Simulated' },
        mode: 'test', radioDisabled: false, competitionApprovalStatus: 'Not reviewed',
        enclosureRev: 'ENC-A0 (brief only)', mountRev: 'MNT-450-A0 (brief only)',
        openIssues: ['Rear wheel-speed sensor harness damaged — slip estimate unavailable (SIMULATED fault)'], simulated: true,
      },
    ],
    cncParts: [
      {
        id: 'cnc-enc-01', partNumber: 'MXL-ENC-001', name: 'MX Node billet enclosure', category: 'Enclosure',
        material: '6061-T6 (candidate)', finish: 'Type III anodize (candidate)', cadRef: 'CAD/enc-001 (placeholder)',
        drawingRef: 'DWG/enc-001 (placeholder)', bom: [{ item: 'Enclosure body', qty: 1 }, { item: 'Lid', qty: 1 }, { item: 'O-ring seal', qty: 2, note: 'replaceable' }],
        installedBikeIds: [], failureNotes: [], briefDoc: 'docs/cnc/enclosure-brief.md',
        revisions: [{ rev: 'A0', date: '2026-08-01', change: 'Initial design brief', status: 'Concept', inspectionStatus: 'Pending' }],
      },
      {
        id: 'cnc-mnt-250', partNumber: 'MXL-MNT-250-2026', name: 'MX Node mount — YZ250F 2026', category: 'Mount',
        bikeModelId: 'model-yz250f-2026', material: '6061-T6 (candidate)', finish: 'Anodize (candidate)',
        cadRef: 'CAD/mnt-250 (placeholder)', drawingRef: 'DWG/mnt-250 (placeholder)',
        bom: [{ item: 'Mount plate', qty: 1 }, { item: 'Isolator bushing', qty: 4 }],
        installedBikeIds: [], failureNotes: [], briefDoc: 'docs/cnc/mount-yz250f.md',
        revisions: [{ rev: 'A0', date: '2026-08-01', change: 'Survey pending — dimensions TBD on bike', status: 'Concept', inspectionStatus: 'Pending' }],
      },
      {
        id: 'cnc-mnt-450', partNumber: 'MXL-MNT-450-2025', name: 'MX Node mount — YZ450F 2025', category: 'Mount',
        bikeModelId: 'model-yz450f-2025', material: '6061-T6 (candidate)', finish: 'Anodize (candidate)',
        cadRef: 'CAD/mnt-450 (placeholder)', drawingRef: 'DWG/mnt-450 (placeholder)',
        bom: [{ item: 'Mount plate', qty: 1 }, { item: 'Isolator bushing', qty: 4 }],
        installedBikeIds: [], failureNotes: [], briefDoc: 'docs/cnc/mount-yz450f.md',
        revisions: [{ rev: 'A0', date: '2026-08-01', change: 'Separate design from YZ250F — no shared assumptions', status: 'Concept', inspectionStatus: 'Pending' }],
      },
      {
        id: 'cnc-dock-01', partNumber: 'MXL-DCK-001', name: 'Pit docking station', category: 'Dock',
        material: '6061-T6 + polymer (candidate)', finish: 'Anodize (candidate)', cadRef: 'CAD/dock-001 (placeholder)',
        drawingRef: 'DWG/dock-001 (placeholder)', bom: [{ item: 'Dock frame', qty: 1 }, { item: 'Blind-mate connector', qty: 1, note: 'candidate family, TBD' }],
        installedBikeIds: [], failureNotes: [], briefDoc: 'docs/cnc/pit-dock-brief.md',
        revisions: [{ rev: 'A0', date: '2026-08-05', change: 'Initial brief', status: 'Concept', inspectionStatus: 'Pending' }],
      },
      {
        id: 'cnc-mark-01', partNumber: 'MXL-MRK-001', name: 'Rider MARK button housing', category: 'Control',
        material: '6061-T6 (candidate)', finish: 'Anodize (candidate)', cadRef: 'CAD/mark-001 (placeholder)',
        drawingRef: 'DWG/mark-001 (placeholder)', bom: [{ item: 'Housing', qty: 1 }, { item: 'Sealed switch', qty: 1, note: 'replaceable' }],
        installedBikeIds: [], failureNotes: [], briefDoc: 'docs/cnc/mark-button-and-sensor-mounts.md',
        revisions: [{ rev: 'A0', date: '2026-08-05', change: 'Initial brief', status: 'Concept', inspectionStatus: 'Pending' }],
      },
      {
        id: 'cnc-fix-01', partNumber: 'MXL-FIX-001', name: 'Vortex bench development fixture', category: 'Fixture',
        material: 'Aluminum extrusion + 6061 plates (candidate)', finish: 'None', cadRef: 'CAD/fix-001 (placeholder)',
        drawingRef: 'DWG/fix-001 (placeholder)', bom: [{ item: 'Base plate', qty: 1 }, { item: 'Fused power module', qty: 1, note: 'current-limited' }, { item: 'Emergency disconnect', qty: 1 }],
        installedBikeIds: [], failureNotes: [], briefDoc: 'docs/cnc/bench-fixture-brief.md',
        revisions: [{ rev: 'A0', date: '2026-08-05', change: 'Initial brief', status: 'Concept', inspectionStatus: 'Pending' }],
      },
    ],
    maintenance: [
      { id: 'mnt-1', bikeId: 'bike-250', at: '2026-08-02T14:00:00Z', kind: 'Oil change', hoursAt: 16.8, note: 'Team oil, filter replaced.', byUserId: 'u-mech', provenance: 'MECHANIC ENTERED' },
      { id: 'mnt-2', bikeId: 'bike-250', at: '2026-07-20T10:00:00Z', kind: 'Top-end service', hoursAt: 15.2, note: 'Piston + rings, build revision B07.', byUserId: 'u-builder', provenance: 'ENGINE BUILDER ENTERED' },
      { id: 'mnt-3', bikeId: 'bike-450', at: '2026-08-05T09:00:00Z', kind: 'Air filter', hoursAt: 21.0, note: 'Warning: oil change due within 1.0 h.', byUserId: 'u-mech', provenance: 'MECHANIC ENTERED' },
    ],
    faults: [
      { id: 'fault-1', bikeId: 'bike-450', at: '2026-08-08T16:22:00Z', source: 'MX Node (SIMULATED)', code: 'SNS-RWS-OPEN', note: 'Rear wheel-speed circuit open — sensor harness suspect.', resolved: false },
    ],
    audit: [],
    telemetryChannels: targetChannels(),
    testPlans: [],
    decisions: [],
    events: [],
    crewTasks: [],
    twin: [],
    debriefs: [],
    grants: [],
    listings: [],
    importedTraces: {},
  };

  // ---- bikes -------------------------------------------------------------
  const bike250: Bike = {
    id: 'bike-250', orgId, label: 'CMX-250-04', bikeModelId: 'model-yz250f-2026',
    vinPartial: 'SIM-VIN-…9F04', ecuInstanceId: 'ecuinst-250', engineBuildId: 'build-250-b07',
    assignedRiderId: 'rider-1',
    setup: {
      fuelId: 'fuel-team-01', exhaustId: 'exh-cfg-02', gearing: '13/50',
      suspension: 'A-kit, 2026 valving (fictional)', tireModel: 'Race tire (fictional)', tireSizeRear: '110/90-19',
      tirePressureFront: 0.85, tirePressureRear: 0.85, clutch: 'Hydraulic, stock master',
      forkHeightMm: 5, sagMm: 105,
    },
    currentMapSlot: 4, trims: { Low: 5, Mid: 5, High: 6 },
    totalHours: 18.6, hoursSinceRebuild: 3.4, maintenanceStatus: 'Current',
    hardwareDeviceId: 'node-01', identityConfirmed: true, modelYearConfirmed: true,
    retired: false, openIssues: [],
  };
  const bike450: Bike = {
    id: 'bike-450', orgId, label: 'CMX-450-01', bikeModelId: 'model-yz450f-2025',
    vinPartial: 'SIM-VIN-…2K01', ecuInstanceId: 'ecuinst-450', engineBuildId: 'build-450-b03',
    assignedRiderId: 'rider-2',
    setup: {
      fuelId: 'fuel-team-01', exhaustId: 'exh-cfg-01', gearing: '13/49',
      suspension: 'A-kit (fictional)', tireModel: 'Race tire (fictional)', tireSizeRear: '120/80-19',
      tirePressureFront: 0.83, tirePressureRear: 0.87, clutch: 'Cable, stiffer springs',
      forkHeightMm: 3, sagMm: 103,
    },
    currentMapSlot: 2, trims: { Low: 4, Mid: 5, High: 5 },
    totalHours: 21.2, hoursSinceRebuild: 3.4, maintenanceStatus: 'Due Soon',
    hardwareDeviceId: 'node-02', identityConfirmed: true, modelYearConfirmed: true,
    retired: false, openIssues: ['Rear wheel-speed harness (SIMULATED fault)'],
  };
  db.bikes.push(bike250, bike450);

  // ---- maps ---------------------------------------------------------------
  const axes = [
    { id: 'ax-rpm', label: 'RPM', unit: 'rpm', breakpoints: RPM_BP, source: 'Simulated demo definition', verification: 'Physically Inspected' as const },
    { id: 'ax-tps', label: 'Throttle', unit: '%', breakpoints: TPS_BP, source: 'Simulated demo definition', verification: 'Physically Inspected' as const },
  ];
  const tableDefs = [
    { id: 'fuel', label: 'Fuel offset', unit: '%', xAxisId: 'ax-tps', yAxisId: 'ax-rpm', cellType: 'number' as const, allowedMin: -15, allowedMax: 15, precision: 1, correctionType: 'offset' as const, source: 'Simulated demo definition', verification: 'Physically Inspected' as const },
    { id: 'ignition', label: 'Ignition offset', unit: '°', xAxisId: 'ax-tps', yAxisId: 'ax-rpm', cellType: 'number' as const, allowedMin: -6, allowedMax: 6, precision: 1, correctionType: 'offset' as const, source: 'Simulated demo definition', verification: 'Physically Inspected' as const },
  ];
  db.maps.push(
    { id: 'map-250-hardpack', orgId, name: 'CMX250-HARDPACK', purpose: 'Hard-pack race map (fictional)', ecuDefinitionId: 'ecu-sim-250', tableDefs, axes, tags: ['hard pack', 'YZ250F', '2026', 'race'], privacy: 'team' },
    { id: 'map-450-base', orgId, name: 'CMX450-BASE', purpose: 'Baseline race map (fictional)', ecuDefinitionId: 'ecu-sim-450', tableDefs, axes, tags: ['baseline', 'YZ450F', '2025'], privacy: 'team' },
  );

  const compat250 = {
    manufacturer: 'Yamaha', model: 'YZ250F', modelYear: 2026, ecuDefinitionId: 'ecu-sim-250',
    ecuFirmware: 'SIM-FW-2.4.1', engineBuildId: 'build-250-b07', fuelId: 'fuel-team-01',
    exhaustId: 'exh-cfg-02', revLimit: 13500, mapFormat: 'sim-grid-v1', envelopeVersion: 'ENV-1',
  };
  const compat450 = {
    manufacturer: 'Yamaha', model: 'YZ450F', modelYear: 2025, ecuDefinitionId: 'ecu-sim-450',
    ecuFirmware: 'SIM-FW-3.0.2', engineBuildId: 'build-450-b03', fuelId: 'fuel-team-01',
    exhaustId: 'exh-cfg-01', revLimit: 11900, mapFormat: 'sim-grid-v1', envelopeVersion: 'ENV-1',
  };

  const rev = (id: string, mapId: string, revName: string, state: MapRevision['state'],
    tables: Record<string, number[][]>, notes: string, parent?: string,
    compat = compat250): MapRevision => ({
    id, mapId, rev: revName, state, parentRevisionId: parent, tables,
    globalTrims: { Low: 5, Mid: 5, High: 6 }, authorUserId: 'u-tuner', notes,
    compatibility: compat, createdAt: '2026-07-15T12:00:00Z', testedInSessionIds: [],
    provenance: 'TUNER ENTERED',
  });

  const r05 = rev('rev-250-r05', 'map-250-hardpack', 'R05', 'RETIRED',
    { fuel: zeros(), ignition: zeros() }, 'Prior baseline, superseded by R07.');
  const r06 = rev('rev-250-r06', 'map-250-hardpack', 'R06', 'TESTED',
    {
      fuel: shapedTable((rpm, tps) => (tps >= 20 && tps <= 60 && rpm >= 5000 && rpm <= 9500 ? 1.5 : 0)),
      ignition: zeros(),
    }, 'A-side of corner-exit A/B. Small enrichment in reopening region.', 'rev-250-r05');
  const r07 = rev('rev-250-r07', 'map-250-hardpack', 'R07', 'TEAM_BASELINE',
    {
      fuel: shapedTable((rpm, tps) => (tps >= 20 && tps <= 60 && rpm >= 5000 && rpm <= 9500 ? 2.5 : tps >= 10 && tps < 20 ? 1 : 0)),
      ignition: shapedTable((rpm, tps) => (tps >= 20 && tps <= 40 && rpm >= 6500 && rpm <= 9500 ? -0.5 : 0)),
    }, 'B-side of corner-exit A/B — accepted and promoted to team baseline.', 'rev-250-r06');
  r07.approvedByUserId = 'u-tuner';
  r07.approvedAt = '2026-08-06T15:00:00Z';
  const r450 = rev('rev-450-r03', 'map-450-base', 'R03', 'TRANSFER_CONFIRMED',
    { fuel: shapedTable((rpm, tps) => (tps >= 60 && rpm >= 6500 ? 1.0 : 0)), ignition: zeros() },
    'Current 450 race map (fictional).', undefined, compat450);
  r450.approvedByUserId = 'u-tuner';
  r450.approvedAt = '2026-08-01T15:00:00Z';
  db.mapRevisions.push(r05, r06, r07, r450);
  db.maps[0].headRevisionId = r07.id;
  db.maps[1].headRevisionId = r450.id;
  bike250.currentMapRevisionId = r07.id;
  bike450.currentMapRevisionId = r450.id;

  db.mapSlots['bike-250'] = Array.from({ length: 10 }, (_, i) => ({
    slot: i + 1,
    mapRevisionId: i + 1 === 4 ? r07.id : i + 1 === 3 ? r06.id : undefined,
    purpose: i + 1 === 4 ? 'Race — hard pack' : i + 1 === 3 ? 'A/B reference (A side)' : undefined,
  }));
  db.mapSlots['bike-450'] = Array.from({ length: 10 }, (_, i) => ({
    slot: i + 1,
    mapRevisionId: i + 1 === 2 ? r450.id : undefined,
    purpose: i + 1 === 2 ? 'Race baseline' : undefined,
  }));

  // ---- transfers (simulated external Vortex workflow confirmations) -------
  db.transfers.push(
    {
      id: 'xfer-r06', mapRevisionId: r06.id, bikeId: 'bike-250', ecuInstanceId: 'ecuinst-250', slot: 3,
      externalSoftware: 'Official Vortex programming workflow (SIMULATED)', performedByUserId: 'u-mech',
      verifiedByUserId: 'u-tuner', transferredAt: '2026-08-05T13:10:00Z', independentlyConfirmed: true,
      simulated: true, linkedSessionId: 'sess-4',
    },
    {
      id: 'xfer-r07', mapRevisionId: r07.id, bikeId: 'bike-250', ecuInstanceId: 'ecuinst-250', slot: 4,
      externalSoftware: 'Official Vortex programming workflow (SIMULATED)', performedByUserId: 'u-mech',
      verifiedByUserId: 'u-tuner', transferredAt: '2026-08-05T16:40:00Z', independentlyConfirmed: true,
      simulated: true, linkedSessionId: 'sess-5',
    },
    {
      id: 'xfer-r450', mapRevisionId: r450.id, bikeId: 'bike-450', ecuInstanceId: 'ecuinst-450', slot: 2,
      externalSoftware: 'Official Vortex programming workflow (SIMULATED)', performedByUserId: 'u-mech',
      transferredAt: '2026-08-01T11:00:00Z', independentlyConfirmed: false, simulated: true,
    },
  );

  // ---- sessions ------------------------------------------------------------
  const weather = (c: number) => ({ ambientC: c, humidityPct: 48, baroHpa: 1009, windKph: 9, trackTempC: c + 8, provenance: 'MEASURED' as const });
  const condition = { surfaceType: 'Hard pack', preparation: 'Ripped and watered AM', moisture: 'Drying', ruts: 'Formed in 6 corners', bumps: 'Moderate braking bumps', provenance: 'MECHANIC ENTERED' as const };
  const hw = (deviceId: string, slipQuality: 'Simulated' | 'Missing' = 'Simulated') => ({
    deviceId, firmware: 'sim-0.9.2', batteryPct: 88, storagePct: 25,
    gps: 'Simulated' as const, imu: 'Simulated' as const, ecuData: 'Simulated' as const,
    calibrationCurrent: slipQuality !== 'Missing', mode: 'test' as const, radioDisabled: false, simulated: true,
  });
  const snap250 = (revId: string, slot: number) => ({
    mapRevisionId: revId, mapSlot: slot, trims: { Low: 5, Mid: 5, High: 6 },
    setup: bike250.setup, engineBuildId: 'build-250-b07', hoursAtSession: 17.9,
  });

  const mkSession = (id: string, bikeId: string, riderId: string, trackId: string, objective: string,
    startedAt: string, seedNum: number, snap: Session['setupSnapshot'], device: string): Session => ({
    id, orgId, bikeId, riderId, trackId, objective, status: 'complete', startedAt,
    durationS: 720, weather: weather(27), trackCondition: condition, setupSnapshot: snap,
    hardwareCheck: hw(device), simSeed: seedNum, lapCount: 7, createdByUserId: 'u-chief', simulated: true,
  });

  const s1 = mkSession('sess-1', 'bike-250', 'rider-1', 'track-pinegrove', 'Validate engine build B07 shakedown', '2026-08-03T15:00:00Z', 101, snap250(r05.id, 4), 'node-01');
  const s2 = mkSession('sess-2', 'bike-450', 'rider-2', 'track-pinegrove', 'Baseline 450 on hard pack', '2026-08-03T16:30:00Z', 202, { mapRevisionId: r450.id, mapSlot: 2, trims: { Low: 4, Mid: 5, High: 5 }, setup: bike450.setup, engineBuildId: 'build-450-b03', hoursAtSession: 19.8 }, 'node-02');
  const s3 = mkSession('sess-3', 'bike-250', 'rider-1', 'track-sxtest', 'Improve start consistency', '2026-08-04T14:00:00Z', 303, snap250(r05.id, 4), 'node-01');
  const s4 = mkSession('sess-4', 'bike-250', 'rider-1', 'track-pinegrove', 'A/B corner-exit delivery — A side (R06)', '2026-08-05T14:00:00Z', 404, snap250(r06.id, 3), 'node-01');
  const s5 = mkSession('sess-5', 'bike-250', 'rider-1', 'track-pinegrove', 'A/B corner-exit delivery — B side (R07)', '2026-08-05T17:00:00Z', 405, snap250(r07.id, 4), 'node-01');
  const s6 = mkSession('sess-6', 'bike-450', 'rider-2', 'track-pinegrove', 'Investigate corner-exit hit after ruts', '2026-08-11T15:30:00Z', 606, { mapRevisionId: r450.id, mapSlot: 2, trims: { Low: 4, Mid: 5, High: 5 }, setup: bike450.setup, engineBuildId: 'build-450-b03', hoursAtSession: 21.0 }, 'node-02');
  s6.hardwareCheck = { ...hw('node-02'), calibrationCurrent: false };
  db.sessions.push(s1, s2, s3, s4, s5, s6);
  r06.testedInSessionIds.push(s4.id);
  r07.testedInSessionIds.push(s5.id);

  // ---- markers --------------------------------------------------------------
  const markers: EventMarker[] = [
    { id: 'mark-1', sessionId: s4.id, tS: 305, lap: 4, trackFrac: 0.41, segmentId: 'seg-c6', category: 'Abrupt hit', note: 'Hits hard after the rut, spins, then hooks up.', confidence: 4, severity: 4, repeatability: 4, provenance: 'RIDER REPORTED' },
    { id: 'mark-2', sessionId: s5.id, tS: 298, lap: 4, trackFrac: 0.41, segmentId: 'seg-c6', category: 'Wheelspin', note: 'Still a little spin but way more manageable.', confidence: 4, severity: 2, repeatability: 3, provenance: 'RIDER REPORTED' },
    { id: 'mark-3', sessionId: s6.id, tS: 312, lap: 4, trackFrac: 0.41, segmentId: 'seg-c6', category: 'Abrupt hit', note: 'The 450 hits too hard after the rut, spins, and then hooks up.', confidence: 5, severity: 4, repeatability: 4, provenance: 'RIDER REPORTED' },
    { id: 'mark-4', sessionId: s3.id, tS: 120, lap: 1, trackFrac: 0.05, segmentId: 'sx-start', category: 'Inconsistent launch', note: 'Two starts bogged off the gate.', confidence: 3, severity: 3, repeatability: 2, provenance: 'RIDER REPORTED' },
  ];
  db.markers.push(...markers);

  // ---- rider feedback ---------------------------------------------------------
  db.feedback.push(
    {
      id: 'fb-s4', sessionId: s4.id, riderId: 'rider-1',
      answers: {
        whatHappened: 'Abrupt hit on reopening out of Corner 6, rear spins then grabs.',
        where: 'Corner 6 rut exit', howOften: 'Most laps',
        betterOrWorse: 'same', confidenceEffect: 'Backing off mid-corner',
        fatigueEffect: 'Slightly more arm pump', startsEffect: 'None',
        compensated: 'Short-shifted to third earlier', changedOverSession: 'Worse as ruts deepened',
      },
      sliders: { initialHit: 7, midrange: 6, topEnd: 6, throttleResponse: 5, engineBraking: 5, traction: 4, predictability: 4, starting: 6, fatigue: 5, confidence: 5 },
      provenance: 'RIDER REPORTED',
    },
    {
      id: 'fb-s5', sessionId: s5.id, riderId: 'rider-1',
      answers: {
        whatHappened: 'Reopening is smoother; can stay on the main line.',
        where: 'Corner 6 rut exit', howOften: 'Occasional',
        betterOrWorse: 'better', confidenceEffect: 'Committing to the inside rut again',
        fatigueEffect: 'Reduced', startsEffect: 'None',
        compensated: 'No', changedOverSession: 'Consistent all session',
      },
      sliders: { initialHit: 6, midrange: 7, topEnd: 6, throttleResponse: 7, engineBraking: 5, traction: 7, predictability: 8, starting: 6, fatigue: 7, confidence: 8 },
      preferredOverPrevious: true,
      provenance: 'RIDER REPORTED',
    },
  );

  // ---- start attempts (session 3) ----------------------------------------------
  const startRnd = (i: number) => {
    const r = (n: number) => {
      // small deterministic jitter per attempt
      const x = Math.sin((i + 1) * 7919 * n) * 10000;
      return x - Math.floor(x);
    };
    return r;
  };
  const starts: StartAttempt[] = Array.from({ length: 12 }, (_, i) => {
    const r = startRnd(i);
    const spin = 8 + r(2) * 22;
    const drop = 1800 + r(3) * 900;
    return {
      id: `start-${i + 1}`, sessionId: s3.id, n: i + 1, surface: 'Groomed loam gate', moisture: i < 6 ? 'Damp' : 'Drying',
      gatePick: `Gate ${3 + (i % 4)}`, initialRpm: 8200 + Math.round(r(1) * 600),
      minRpmAfterRelease: 8200 + Math.round(r(1) * 600) - Math.round(drop),
      rpmRecoveryS: +(0.5 + r(4) * 0.5).toFixed(2), estWheelspinPct: +spin.toFixed(1),
      timeTo30MphS: +(1.95 + spin * 0.012 + r(5) * 0.15).toFixed(2),
      timeTo100FtS: +(2.6 + spin * 0.012 + r(5) * 0.18).toFixed(2),
      secondPhaseG: +(0.62 + r(6) * 0.1).toFixed(2),
      shiftPoint1Rpm: 11200 + Math.round(r(7) * 700),
      riderRating: Math.max(1, Math.min(5, Math.round(5 - spin / 8))),
      provenance: 'SIMULATION',
    };
  });
  db.startAttempts.push(...starts);

  // ---- AI recommendations, decisions, A/B ---------------------------------------
  const tuner = users.find((u) => u.id === 'u-tuner')!;

  // 1) the historical recommendation that led to the accepted A/B (R06→R07)
  const recAccepted = buildRecommendation(db, s4, markers[0],
    'The 250 hits hard after the Corner 6 rut, spins, and then hooks up.');
  recAccepted.id = 'rec-accepted';
  recAccepted.createdAt = '2026-08-05T15:10:00Z';
  db.recommendations.push(recAccepted);
  decideRecommendation(db, tuner, recAccepted, 'ACCEPTED_FOR_TEST',
    'Evidence supports a torque-transition review. Authored R07 with +1.0 % in the reopening region, inside the validated envelope.');
  recAccepted.resultNote = 'A/B completed: rider preferred R07; telemetry agreed. R07 promoted to team baseline.';

  // 2) a rejected recommendation (start bog — evidence pointed to clutch, not map)
  const recRejected = buildRecommendation(db, s3, markers[3],
    'Bogged off the gate on two starts.');
  recRejected.id = 'rec-rejected';
  recRejected.createdAt = '2026-08-04T18:20:00Z';
  db.recommendations.push(recRejected);
  decideRecommendation(db, tuner, recRejected, 'REJECTED',
    'Start telemetry shows wheelspin variance tracks release technique and gate moisture, not launch delivery. No map change; clutch-release drill scheduled.');

  // 3) a live one awaiting tuner review (sensor-degraded 450 session)
  const recOpen = buildRecommendation(db, s6, markers[2],
    'The 450 hits too hard after the rut, spins, and then hooks up.');
  recOpen.id = 'rec-open';
  db.recommendations.push(recOpen);

  // Honest demo data: the telemetry-agreement flag and conclusion are COMPUTED
  // from the simulated traces, never asserted — so the stored narrative can
  // never contradict what Compare recomputes live.
  const abRows = compareSessions(db, s4, s5);
  const abSupports = telemetrySupportsPreference(abRows, 'B');
  db.abTests.push({
    id: 'ab-corner6', orgId, name: 'Corner 6 exit delivery — R06 vs R07',
    recommendationId: recAccepted.id, revisionAId: r06.id, revisionBId: r07.id,
    sessionAId: s4.id, sessionBId: s5.id,
    holdConstant: ['gearing', 'tire', 'suspension', 'clutch', 'trims'],
    outcome: 'B', riderPreferred: 'B', telemetrySupportsPreference: abSupports,
    conclusion: abSupports
      ? 'R07 promoted to team baseline: rider preference and telemetry agreed at Corner 6.'
      : 'R07 promoted to team baseline on rider preference: R07 was substantially easier to ride at Corner 6 late in the moto, even though headline lap metrics favored R06. Both readings are preserved.',
    decidedByUserId: 'u-tuner',
  });
  // ---- expansion seed: gearing/pressure variation sessions -------------------
  const s7 = mkSession('sess-7', 'bike-250', 'rider-1', 'track-sxtest', 'Start comparison — 13/49 gearing', '2026-08-07T14:00:00Z', 707,
    { ...snap250(r07.id, 4), setup: { ...bike250.setup, gearing: '13/49' } }, 'node-01');
  const s8 = mkSession('sess-8', 'bike-250', 'rider-1', 'track-sxtest', 'Start comparison — 13/50 gearing', '2026-08-07T16:00:00Z', 708,
    { ...snap250(r07.id, 4), setup: { ...bike250.setup, gearing: '13/50' } }, 'node-01');
  const s9 = mkSession('sess-9', 'bike-450', 'rider-2', 'track-pinegrove', 'Rear pressure test on drying hard pack', '2026-08-09T15:00:00Z', 909,
    { mapRevisionId: r450.id, mapSlot: 2, trims: { Low: 4, Mid: 5, High: 5 }, setup: { ...bike450.setup, tirePressureRear: 0.92 }, engineBuildId: 'build-450-b03', hoursAtSession: 20.4 }, 'node-02');
  db.sessions.push(s7, s8, s9);
  r07.testedInSessionIds.push(s7.id, s8.id);

  // ---- digital twin components -------------------------------------------------
  const twin = (bikeId: string, id: string, system: Db['twin'][number]['system'], label: string, hours: number, typicalServiceH?: number, note?: string): Db['twin'][number] => ({
    id, bikeId, system, label, rev: 'A', hours, installedAt: '2026-07-20T10:00:00Z',
    typicalServiceH, serviceHistory: [{ at: '2026-08-02T14:00:00Z', note: 'Inspected at oil change', hoursAt: Math.max(0, hours - 2) }],
    setupNote: note, notes: undefined, provenance: 'MECHANIC ENTERED',
  });
  db.twin.push(
    twin('bike-250', 'E07', 'Engine', 'Engine CMX250-B07', 3.4, 25),
    twin('bike-250', 'ECU-250', 'ECU', 'Vortex SIM-DEMO-250', 18.6),
    twin('bike-250', 'EX02', 'Exhaust', 'Exhaust config 02', 12.1, 60),
    twin('bike-250', 'F07', 'Fork', 'Fork set F07', 16.2, 20, 'A-kit, 2026 valving'),
    twin('bike-250', 'S04', 'Shock', 'Shock S04', 11.3, 20, 'Current setup S11'),
    twin('bike-250', 'WF1', 'Front wheel', 'Front wheel WF1', 18.6, 40),
    twin('bike-250', 'WR2', 'Rear wheel', 'Rear wheel WR2', 9.4, 40),
    twin('bike-250', 'T-R', 'Tires', 'Rear race tire', 0.8, 1.2, 'Falls off ≈45 min on hard pack'),
    twin('bike-250', 'BRK1', 'Brakes', 'Brake set B1', 18.6, 30),
    twin('bike-250', 'GRC1', 'Gearing', 'Sprockets 13/50 + chain C3', 6.1, 15),
    twin('bike-250', 'CL2', 'Clutch', 'Clutch pack CL2', 7.2, 8.5, 'Rider is moderate on clutches'),
    twin('bike-250', 'CTRL1', 'Controls', 'Controls set 1', 18.6),
    twin('bike-250', 'NODE01', 'MX Node', 'MX Node node-01 (SIMULATED)', 14.0),
    twin('bike-450', 'E03', 'Engine', 'Engine CMX450-B03', 3.4, 25),
    twin('bike-450', 'F45', 'Fork', 'Fork set F45', 21.2, 20),
    twin('bike-450', 'S45', 'Shock', 'Shock S45', 21.2, 20),
    twin('bike-450', 'CL45', 'Clutch', 'Clutch pack CL45', 9.1, 8.5),
    twin('bike-450', 'T-R45', 'Tires', 'Rear race tire', 1.1, 1.2),
    twin('bike-450', 'NODE02', 'MX Node', 'MX Node node-02 (SIMULATED)', 16.5),
  );

  // ---- test plans ---------------------------------------------------------------
  db.testPlans.push(
    {
      id: 'plan-corner6', orgId, objective: 'Improve drive from Corner 6 without reducing midrange',
      kind: 'ab', bikeId: 'bike-250', riderId: 'rider-1', trackId: 'track-pinegrove', sectionId: 'seg-c6',
      variants: [
        { id: 'A', label: 'A — R06', mapRevisionId: r06.id, gearing: '13/50', tirePressureRear: 0.85, sessionId: 'sess-4' },
        { id: 'B', label: 'B — R07', mapRevisionId: r07.id, gearing: '13/50', tirePressureRear: 0.85, sessionId: 'sess-5' },
      ],
      holdConstant: ['gearing', 'pressureR', 'tire', 'suspension', 'sag', 'clutch', 'fuel'],
      status: 'complete', createdByUserId: 'u-tuner', createdAt: '2026-08-05T12:00:00Z',
      conclusion: 'R07 reduced peak slip and improved lap consistency at Corner 6; promoted to team baseline.',
      decisionId: 'dec-r07',
    },
    {
      id: 'plan-gearing', orgId, objective: 'Improve start consistency without hurting second-phase drive',
      kind: 'start', bikeId: 'bike-250', riderId: 'rider-1', trackId: 'track-sxtest',
      variants: [
        { id: 'A', label: 'A — 13/49', mapRevisionId: r07.id, gearing: '13/49', tirePressureRear: 0.85, sessionId: 'sess-7' },
        { id: 'B', label: 'B — 13/50', mapRevisionId: r07.id, gearing: '13/50', tirePressureRear: 0.85, sessionId: 'sess-8' },
      ],
      holdConstant: ['map', 'pressureR', 'tire', 'suspension', 'clutch', 'fuel'],
      status: 'complete', createdByUserId: 'u-tuner', createdAt: '2026-08-07T12:00:00Z',
      conclusion: '13/49 hurt start consistency; 13/50 retained. No map change indicated.',
    },
    {
      id: 'plan-next', orgId, objective: 'Confirm R07 late-moto stability at race distance',
      kind: 'durability', bikeId: 'bike-250', riderId: 'rider-1', trackId: 'track-pinegrove',
      variants: [
        { id: 'A', label: 'A — R07 20-min moto', mapRevisionId: r07.id, gearing: '13/50', tirePressureRear: 0.85 },
      ],
      holdConstant: ['map', 'gearing', 'pressureR', 'suspension'],
      status: 'planned', createdByUserId: 'u-chief', createdAt: '2026-08-11T18:00:00Z',
    },
  );

  // ---- decisions ------------------------------------------------------------------
  db.decisions.push(
    {
      id: 'dec-r07', orgId, at: '2026-08-05T19:30:00Z', authorUserId: 'u-tuner',
      bikeId: 'bike-250', riderId: 'rider-1', sessionIds: ['sess-4', 'sess-5'],
      decision: 'Promote R07 to team baseline for hard pack.',
      rationale: 'Rider preferred R07 and telemetry agreed: lower peak slip at Corner 6 and better lap consistency, with midrange unchanged.',
      outcome: 'R07 is the hard-pack baseline.', followUp: 'Retest R07 at full race distance before the next event.',
    },
    {
      id: 'dec-gearing', orgId, at: '2026-08-07T18:00:00Z', authorUserId: 'u-chief',
      bikeId: 'bike-250', riderId: 'rider-1', sessionIds: ['sess-7', 'sess-8'],
      decision: 'Stay on 13/50 gearing.',
      rationale: '13/49 hurt start consistency in the SX start comparison; second-phase gains did not materialize.',
      outcome: '13/50 retained.',
    },
  );

  // ---- race weekend -----------------------------------------------------------------
  db.events.push({
    id: 'event-pinegrove', orgId, name: 'Pine Grove National (fictional)', trackId: 'track-pinegrove',
    days: [
      { date: '2026-08-14', label: 'Friday — Press / Test', slots: [{ label: 'Test session' }] },
      { date: '2026-08-15', label: 'Saturday — Qualifying', slots: [{ label: 'Practice', sessionId: 'sess-4' }, { label: 'Timed qualifying', sessionId: 'sess-5' }] },
      { date: '2026-08-16', label: 'Sunday — Motos', slots: [{ label: 'Warm-up' }, { label: 'Moto 1' }, { label: 'Moto 2' }] },
    ],
    notes: 'SIMULATED demonstration event.',
  });

  // ---- crew tasks --------------------------------------------------------------------
  db.crewTasks.push(
    { id: 'task-1', orgId, assigneeUserId: 'u-mech', title: 'Rear wheel change + pressure set 0.85 bar', bikeId: 'bike-250', status: 'in_progress', createdAt: '2026-08-12T08:10:00Z' },
    { id: 'task-2', orgId, assigneeUserId: 'u-susp', title: 'Shock S45: +2 rebound per rider note', bikeId: 'bike-450', status: 'assigned', createdAt: '2026-08-12T08:12:00Z' },
    { id: 'task-3', orgId, assigneeUserId: 'u-tuner', title: 'Prepare R08 draft for race-distance test', bikeId: 'bike-250', status: 'assigned', createdAt: '2026-08-12T08:15:00Z' },
    { id: 'task-4', orgId, assigneeUserId: 'u-data', title: 'Review Corner 6 exit consistency vs baseline', status: 'verified', createdAt: '2026-08-11T17:00:00Z' },
  );

  // ---- stored debrief ------------------------------------------------------------------
  db.debriefs.push({
    id: 'debrief-0805', orgId, date: '2026-08-05',
    learned: [
      'R07 improved hard-pack corner-exit drive; rider preference and telemetry agreed.',
      'Rider 1 preferred the smoother reopening even before seeing lap times.',
    ],
    tomorrow: ['Run the 13/49 vs 13/50 start comparison.', 'Watch rear tire condition after 45 minutes.'],
    approvedByUserId: 'u-chief',
  });

  // ---- remote access + marketplace shell ---------------------------------------------------
  db.grants.push({
    id: 'grant-1', orgId, tunerName: 'External Tuner X (fictional)', bikeIds: ['bike-450'],
    readTelemetry: true, readMaps: true, commentAccess: true, exportAllowed: false, mapEditAllowed: false,
    createdByUserId: 'u-manager', createdAt: '2026-08-11T09:00:00Z', expiresAt: '2026-09-30T09:00:00Z',
    state: 'SIMULATED',
  });
  db.listings.push({
    id: 'listing-shell-1', title: 'Hard-pack baseline pack — YZ250F (example)', author: 'TRACE (example)',
    version: '0.0', validationLevel: 'Unvalidated',
    compatibility: '2026 YZ250F · simulated ECU definition only',
    requiredHardware: ['Vortex ECU (verified definition)', 'TRACE MX Node'], requiredFuel: 'Team Fuel 01',
    disclaimer: 'SHELL — marketplace is future architecture. Nothing here is a valid or safe tune.',
    state: 'SHELL',
  });

  // align the decision + plan narrative with the computed A/B agreement
  const decR07 = db.decisions.find((d) => d.id === 'dec-r07');
  if (decR07) {
    decR07.rationale = abSupports
      ? 'Rider preferred R07 and telemetry agreed: smoother Corner 6 reopening with midrange unchanged.'
      : 'Rider preferred R07 for control and confidence at Corner 6; headline lap metrics favored R06. Decision prioritized late-moto rideability — both readings recorded.';
  }
  const planC6 = db.testPlans.find((p) => p.id === 'plan-corner6');
  if (planC6) planC6.conclusion = db.abTests[0].conclusion;

  // ---- audit seed ------------------------------------------------------------
  appendAudit(db, 'u-admin', 'org.seeded', 'Organization', orgId, 'Simulated demonstration dataset created.');
  appendAudit(db, 'u-tuner', 'map.approved_for_test', 'MapRevision', r07.id, 'R07 approved for test after review of rec-accepted.');
  appendAudit(db, 'u-mech', 'transfer.confirm', 'MapRevision', r07.id, 'External Vortex transfer confirmed (SIMULATED), slot 4, second-person verified by u-tuner.');
  appendAudit(db, 'u-tuner', 'map.team_baseline', 'MapRevision', r07.id, 'R07 promoted to team baseline after A/B ab-corner6.');
  appendAudit(db, 'u-tuner', 'map.compat_check', 'MapRevision', r450.id, 'Attempted evaluation of 450 revision against CMX-250-04: blocked — ECU mismatch (expected demo of compatibility gate).');

  return db;
}
