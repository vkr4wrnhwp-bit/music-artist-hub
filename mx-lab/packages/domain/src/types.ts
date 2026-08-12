/**
 * MX LAB core domain types — Phase 1 (simulation only).
 *
 * Everything Vortex-specific is capability-driven: nothing in the app may
 * assume an ECU capability that is not present, with a verification status,
 * in the bike's ECUDefinition. Phase 1 never writes to an ECU.
 */

// ---------------------------------------------------------------- provenance

export type Provenance =
  | 'MEASURED'
  | 'RIDER REPORTED'
  | 'TUNER ENTERED'
  | 'MECHANIC ENTERED'
  | 'ENGINE BUILDER ENTERED'
  | 'IMPORTED'
  | 'CALCULATED'
  | 'AI INFERENCE'
  | 'SYSTEM'
  | 'SIMULATION';

// ---------------------------------------------------------------- org & users

export type Role =
  | 'org_admin'
  | 'team_manager'
  | 'crew_chief'
  | 'tuner'
  | 'mechanic'
  | 'engine_builder'
  | 'suspension_tech'
  | 'rider'
  | 'data_engineer'
  | 'hardware_engineer'
  | 'viewer';

export interface Organization {
  id: string;
  name: string;
}

export interface User {
  id: string;
  orgId: string;
  name: string;
  role: Role;
  /** demo only — production auth is an adapter boundary (see docs/architecture) */
  simulatedLogin: boolean;
}

// ---------------------------------------------------------------- ECU

export type EcuVerificationStatus =
  | 'Unverified'
  | 'Physically Inspected'
  | 'Documentation Verified'
  | 'Bench Verified'
  | 'Bike Verified'
  | 'Team Approved';

export interface EcuCapability {
  id: string;
  kind: 'telemetry_channel' | 'map_table' | 'global_trim' | 'map_slots' | 'diagnostic' | 'setting';
  label: string;
  detail?: string;
  /** where this claim came from — never 'assumed' */
  source: string;
  verification: EcuVerificationStatus;
}

export interface EcuDefinition {
  id: string;
  manufacturer: string; // "Vortex"
  family: string;       // e.g. "X10 family — pending verification"
  model: string;        // never hardcoded as fact until verified
  partNumber?: string;
  firmware: string;
  softwareVersion?: string;
  connector: string;    // description, with verification status below
  connectorVerification: EcuVerificationStatus;
  mapSlotCount?: number;         // only if capability verified
  globalTrims: string[];         // e.g. ['low','mid','high'] when verified
  capabilities: EcuCapability[];
  compatibleBikeModelIds: string[];
  verification: EcuVerificationStatus;
  lastVerified?: string;
  notes?: string;
  simulated: boolean;
}

export interface EcuInstance {
  id: string;
  ecuDefinitionId: string;
  serialNumber: string;
  installedBikeId?: string;
  simulated: boolean;
}

// ---------------------------------------------------------------- bike

export interface BikeModelDefinition {
  id: string;
  manufacturer: string;
  model: string;   // "YZ250F"
  modelYear: number;
}

export interface EngineBuild {
  id: string;
  code: string; // e.g. CMX250-B07
  bikeModelId: string;
  camshaft: string;
  compression: string;
  injector: string;
  throttleBody: string;
  revLimit: number;
  notes?: string;
  builtBy: string;
  provenance: Provenance;
}

export interface BikeSetup {
  fuelId: string;
  exhaustId: string;
  gearing: string;       // "13/50"
  suspension: string;
  tireModel: string;
  tireSizeRear: string;
  tirePressureFront: number;
  tirePressureRear: number;
  clutch: string;
  forkHeightMm: number;
  sagMm: number;
}

export type MaintenanceStatus = 'Current' | 'Due Soon' | 'Required';

export interface Bike {
  id: string;
  orgId: string;
  label: string;          // "CMX-250-04"
  bikeModelId: string;
  vinPartial?: string;
  ecuInstanceId?: string;
  engineBuildId?: string;
  assignedRiderId?: string;
  setup: BikeSetup;
  currentMapRevisionId?: string;
  currentMapSlot?: number;
  trims: Record<string, number>;   // keyed by ECU-defined trim names only
  totalHours: number;
  hoursSinceRebuild: number;
  maintenanceStatus: MaintenanceStatus;
  hardwareDeviceId?: string;
  identityConfirmed: boolean;      // Phase 0 inventory complete
  modelYearConfirmed: boolean;
  retired: boolean;
  openIssues: string[];
}

export interface Rider {
  id: string;
  orgId: string;
  name: string;
  userId?: string;
  weightKg: number;
  skillCategory: 'Pro' | 'Intermediate' | 'Amateur';
  limitationNotes?: string;
  preferredDelivery: string;
}

export interface RiderPreferenceProfile {
  riderId: string;
  preferredInitialHit: 'soft' | 'linear' | 'aggressive';
  preferredEngineBraking: 'low' | 'medium' | 'high';
  typicalThrottleRate: 'smooth' | 'moderate' | 'abrupt';
  surfaceNotes: Record<string, string>;
  learnedFrom: string[]; // session ids
  provenance: Provenance;
}

// ---------------------------------------------------------------- parts / config catalogs

export interface FuelDefinition { id: string; name: string; octane?: string; notes?: string }
export interface ExhaustConfiguration { id: string; name: string }

// ---------------------------------------------------------------- track

export interface TrackSegment { id: string; name: string; startFrac: number; endFrac: number }

export interface Track {
  id: string;
  name: string;
  kind: 'motocross' | 'supercross_test';
  direction: 'CW' | 'CCW';
  surface: string;
  segments: TrackSegment[];
  /** normalized closed path for the track-view (x,y in 0..1) */
  path: Array<[number, number]>;
  elevationM?: number;
}

export interface WeatherSnapshot {
  ambientC: number;
  humidityPct: number;
  baroHpa: number;
  windKph: number;
  trackTempC?: number;
  notes?: string;
  provenance: Provenance;
}

export interface TrackCondition {
  surfaceType: string;
  preparation: string;
  moisture: string;
  ruts: string;
  bumps: string;
  provenance: Provenance;
}

// ---------------------------------------------------------------- maps

export interface MapAxisDef {
  id: string;
  label: string;
  unit: string;
  breakpoints: number[];
  source: string;
  verification: EcuVerificationStatus;
}

export interface MapTableDef {
  id: string;              // 'fuel', 'ignition'
  label: string;
  unit: string;
  xAxisId: string;
  yAxisId: string;
  cellType: 'number';
  allowedMin: number;
  allowedMax: number;
  precision: number;       // display decimals
  correctionType: 'offset' | 'absolute';
  interpolation?: string;
  source: string;
  verification: EcuVerificationStatus;
}

export type MapRevisionState =
  | 'DRAFT'
  | 'TUNER_REVIEW'
  | 'APPROVED_FOR_TEST'
  | 'EXPORTED'
  | 'TRANSFER_CONFIRMED'
  | 'TESTED'
  | 'ACCEPTED'
  | 'REJECTED'
  | 'REVISED'
  | 'TEAM_BASELINE'
  | 'RETIRED';

/** compatibility identity a revision was authored against (section 7) */
export interface CompatibilityKey {
  manufacturer: string;
  model: string;
  modelYear: number;
  ecuDefinitionId: string;
  ecuFirmware: string;
  engineBuildId: string;
  fuelId: string;
  exhaustId: string;
  revLimit: number;
  mapFormat: string;
  envelopeVersion: string;
}

export interface MapRevision {
  id: string;
  mapId: string;
  rev: string;                       // "R07"
  state: MapRevisionState;
  parentRevisionId?: string;
  tables: Record<string, number[][]>; // tableDefId -> rows[y][x]
  globalTrims: Record<string, number>;
  authorUserId: string;
  notes: string;
  compatibility: CompatibilityKey;
  createdAt: string;
  approvedByUserId?: string;
  approvedAt?: string;
  testedInSessionIds: string[];
  provenance: Provenance;
}

export type MapPrivacy = 'private' | 'team' | 'authorized_tuner' | 'marketplace_eligible';

export interface MapDefinition {
  id: string;
  orgId: string;
  name: string;                 // "CMX250-HARDPACK"
  purpose: string;
  ecuDefinitionId: string;
  tableDefs: MapTableDef[];
  axes: MapAxisDef[];
  headRevisionId?: string;
  /** private map library metadata */
  tags: string[];
  privacy: MapPrivacy;
}

export interface MapSlotAssignment {
  slot: number;
  mapRevisionId?: string;
  purpose?: string;
  approvalState?: MapRevisionState;
  lastTestedSessionId?: string;
  note?: string;
}

export interface ValidatedTuningEnvelope {
  id: string;
  ecuDefinitionId: string;
  version: string;
  /** per table: max |cell delta| a tuner has validated for a single A/B step */
  maxStepDelta: Record<string, number>;
  definedByUserId: string;
  note: string;
}

export type CompatibilityVerdict =
  | 'Compatible'
  | 'Compatible with warning'
  | 'Requires tuner review'
  | 'Engine build mismatch'
  | 'ECU mismatch'
  | 'Firmware mismatch'
  | 'Model-year mismatch'
  | 'Fuel mismatch'
  | 'Exhaust mismatch'
  | 'Unverified';

export interface CompatibilityResult {
  verdict: CompatibilityVerdict;
  blocking: boolean;
  details: string[];
}

export interface ExternalTransferConfirmation {
  id: string;
  mapRevisionId: string;
  bikeId: string;
  ecuInstanceId: string;
  slot: number;
  externalSoftware: string;        // official Vortex tool used by the tuner
  performedByUserId: string;
  verifiedByUserId?: string;       // optional second person
  transferredAt: string;
  independentlyConfirmed: boolean;
  simulated: boolean;
  linkedSessionId?: string;
}

// ---------------------------------------------------------------- sessions & telemetry

export interface HardwareCheck {
  deviceId: string;
  firmware: string;
  batteryPct: number;
  storagePct: number;
  gps: SignalQuality;
  imu: SignalQuality;
  ecuData: SignalQuality;
  calibrationCurrent: boolean;
  mode: 'test' | 'competition';
  radioDisabled: boolean;
  simulated: boolean;
}

export type SignalQuality =
  | 'Connected'
  | 'Missing'
  | 'Intermittent'
  | 'Out of range'
  | 'Uncalibrated'
  | 'Low confidence'
  | 'Simulated'
  | 'Validated';

export interface TelemetryChannelDef {
  id: string;
  name: string;
  source: string;
  unit: string;
  sampleRateHz: number;
  dataType: 'f32';
  scale: number;
  offset: number;
  validMin: number;
  validMax: number;
  quality: SignalQuality;
  timestampSource: string;
  verification: EcuVerificationStatus;
  testOnly?: boolean;
}

export interface SetupSnapshot {
  mapRevisionId: string;
  mapSlot: number;
  trims: Record<string, number>;
  setup: BikeSetup;
  engineBuildId: string;
  hoursAtSession: number;
}

export type SessionStatus = 'draft' | 'ready' | 'running' | 'complete';

export interface Session {
  id: string;
  orgId: string;
  bikeId: string;
  riderId: string;
  trackId: string;
  objective: string;
  status: SessionStatus;
  startedAt: string;
  durationS: number;
  weather: WeatherSnapshot;
  trackCondition: TrackCondition;
  setupSnapshot: SetupSnapshot;
  hardwareCheck: HardwareCheck;
  /** deterministic simulation seed — telemetry is regenerated, never faked as measured */
  simSeed: number;
  lapCount: number;
  createdByUserId: string;
  abTestId?: string;
  simulated: boolean;
}

export interface Lap {
  n: number;
  startS: number;
  endS: number;
  timeS: number;
}

export type MarkerCategory =
  | 'Bog' | 'Abrupt hit' | 'Too soft' | 'Wheelspin' | 'Loss of drive'
  | 'Flat top-end' | 'Excessive engine braking' | 'Insufficient engine braking'
  | 'Hard starting' | 'Inconsistent launch' | 'Overheating' | 'Popping on deceleration'
  | 'Throttle-response delay' | 'Harsh landing response' | 'Missed shift'
  | 'Clutch issue' | 'Suspension issue' | 'Other' | 'Unreviewed';

export interface EventMarker {
  id: string;
  sessionId: string;
  tS: number;              // seconds into session
  lap: number;
  trackFrac: number;       // 0..1 along path
  segmentId?: string;
  category: MarkerCategory;
  note?: string;
  voiceNote?: string;      // future — recorded transcript placeholder
  confidence?: number;     // rider 1..5
  severity?: number;       // rider 1..5
  repeatability?: number;  // rider 1..5
  provenance: Provenance;
}

export interface RiderFeedback {
  id: string;
  sessionId: string;
  riderId: string;
  answers: {
    whatHappened: string;
    where: string;
    howOften: string;
    betterOrWorse: 'better' | 'worse' | 'same' | 'n/a';
    confidenceEffect: string;
    fatigueEffect: string;
    startsEffect: string;
    compensated: string;
    changedOverSession: string;
  };
  sliders: {
    initialHit: number; midrange: number; topEnd: number;
    throttleResponse: number; engineBraking: number; traction: number;
    predictability: number; starting: number; fatigue: number; confidence: number;
  };
  preferredOverPrevious?: boolean;
  provenance: Provenance;
}

// ---------------------------------------------------------------- starts

export interface StartAttempt {
  id: string;
  sessionId: string;
  n: number;
  surface: string;
  moisture: string;
  gatePick: string;
  initialRpm: number;
  minRpmAfterRelease: number;
  rpmRecoveryS: number;
  estWheelspinPct: number;
  timeTo30MphS: number;
  timeTo100FtS: number;
  secondPhaseG: number;
  shiftPoint1Rpm: number;
  riderRating: number; // 1..5
  tunerNote?: string;
  provenance: Provenance;
}

// ---------------------------------------------------------------- AI race engineer

export type CauseCategory =
  | 'Fueling' | 'Ignition' | 'Torque transition' | 'Engine braking' | 'Rev limit'
  | 'Gearing' | 'Clutch' | 'Suspension' | 'Tire' | 'Track condition'
  | 'Rider input' | 'Sensor' | 'Mechanical' | 'Temperature' | 'Electrical' | 'Unknown';

export interface RankedCause {
  category: CauseCategory;
  rationale: string;
  weight: number; // 0..1
}

export interface DataQualityFlag {
  channelId: string;
  quality: SignalQuality;
  note: string;
}

export type RecommendationStatus =
  | 'AWAITING_TUNER_REVIEW'
  | 'ACCEPTED_FOR_TEST'
  | 'REJECTED'
  | 'REVISED'
  | 'CLOSED';

export interface AIRecommendation {
  id: string;
  orgId: string;
  sessionId: string;
  markerId?: string;
  riderStatement: string;
  observedEvent: string;
  measuredEvidence: string[];
  dataQuality: DataQualityFlag[];
  dataQualityStatus: 'OK' | 'DEGRADED' | 'BLOCKED';
  likelyCause: RankedCause;
  alternativeCauses: RankedCause[];
  nonMapChecks: string[];
  affectedRegion?: { tableId: string; xRange: [number, number]; yRange: [number, number]; description: string };
  proposedTest: string;
  expectedObservable: string;
  riskFlags: string[];
  missingData: string[];
  /** capped when data quality is degraded; never presented as certainty */
  confidencePct: number;
  status: RecommendationStatus;
  tunerDecisionNote?: string;
  decidedByUserId?: string;
  resultNote?: string;
  createdAt: string;
  provenance: 'AI INFERENCE';
}

export interface ABTest {
  id: string;
  orgId: string;
  name: string;
  recommendationId?: string;
  revisionAId: string;
  revisionBId: string;
  sessionAId?: string;
  sessionBId?: string;
  holdConstant: string[];
  outcome?: 'A' | 'B' | 'inconclusive';
  riderPreferred?: 'A' | 'B';
  telemetrySupportsPreference?: boolean;
  conclusion?: string;
  decidedByUserId?: string;
}

// ---------------------------------------------------------------- hardware

export interface HardwareDevice {
  id: string;
  orgId: string;
  kind: 'MX_NODE';
  hardwareRev: string;
  firmware: string;
  assignedBikeId?: string;
  batteryPct: number;
  storagePct: number;
  lastSync?: string;
  lastSessionId?: string;
  channelHealth: Record<string, SignalQuality>;
  mode: 'test' | 'competition';
  radioDisabled: boolean;
  competitionApprovalStatus: 'Not reviewed' | 'Review requested' | 'Approved by team' | 'Sanctioning inquiry open';
  enclosureRev: string;
  mountRev: string;
  openIssues: string[];
  simulated: true; // Phase 1: every device is simulated, no exceptions
}

// ---------------------------------------------------------------- CNC

export type CncPartStatus = 'Concept' | 'Design' | 'Review' | 'Prototype' | 'Testing' | 'Released' | 'Superseded';

export interface CncPartRevision {
  rev: string;
  date: string;
  change: string;
  status: CncPartStatus;
  inspectionStatus: 'Pending' | 'Passed' | 'Failed';
}

export interface CncPart {
  id: string;
  partNumber: string;
  name: string;
  category: 'Enclosure' | 'Mount' | 'Dock' | 'Control' | 'Sensor mount' | 'Fixture';
  bikeModelId?: string;      // model-year specific where applicable
  material: string;
  finish: string;
  weightG?: number;
  costUsd?: number;
  supplier?: string;
  cadRef: string;
  drawingRef: string;
  cncProgramRef?: string;
  bom: Array<{ item: string; qty: number; note?: string }>;
  installedBikeIds: string[];
  failureNotes: string[];
  revisions: CncPartRevision[];
  briefDoc: string;          // docs/cnc/*.md reference
}

// ---------------------------------------------------------------- maintenance

export interface MaintenanceRecord {
  id: string;
  bikeId: string;
  at: string;
  kind: string;
  hoursAt: number;
  note: string;
  byUserId: string;
  provenance: Provenance;
}

export interface FaultRecord {
  id: string;
  bikeId: string;
  at: string;
  source: string;
  code: string;
  note: string;
  resolved: boolean;
}

// ---------------------------------------------------------------- audit

export interface AuditEvent {
  id: string;
  orgId: string;
  at: string;
  actorUserId: string;
  action: string;
  entityType: string;
  entityId: string;
  summary: string;
  meta?: Record<string, unknown>;
}

// ---------------------------------------------------------------- future flash (architecture only)

/**
 * Exists so Phase 4 has a schema slot. It can never run in Phase 1–3.
 * Any attempt to execute must surface the DISABLED message verbatim.
 */
export interface FutureFlashJob {
  id: string;
  status: 'DISABLED';
  message: 'AUTHORIZED DIRECT ECU INTEGRATION HAS NOT BEEN IMPLEMENTED';
}

// ---------------------------------------------------------------- database shape

/** TRACE Focus — the single explicit objective the team is testing right now. */
export interface TraceFocus {
  bikeId: string;
  text: string;
  setByUserId: string;
}

export interface Db {
  schemaVersion: number;
  org: Organization;
  /** optional: absent in archives created before TRACE Focus shipped */
  focus?: TraceFocus;
  users: User[];
  riders: Rider[];
  riderPrefs: RiderPreferenceProfile[];
  bikeModels: BikeModelDefinition[];
  bikes: Bike[];
  ecuDefinitions: EcuDefinition[];
  ecuInstances: EcuInstance[];
  engineBuilds: EngineBuild[];
  fuels: FuelDefinition[];
  exhausts: ExhaustConfiguration[];
  tracks: Track[];
  maps: MapDefinition[];
  mapRevisions: MapRevision[];
  mapSlots: Record<string, MapSlotAssignment[]>; // bikeId -> slots
  envelopes: ValidatedTuningEnvelope[];
  transfers: ExternalTransferConfirmation[];
  sessions: Session[];
  markers: EventMarker[];
  feedback: RiderFeedback[];
  startAttempts: StartAttempt[];
  recommendations: AIRecommendation[];
  abTests: ABTest[];
  devices: HardwareDevice[];
  cncParts: CncPart[];
  maintenance: MaintenanceRecord[];
  faults: FaultRecord[];
  audit: AuditEvent[];
  telemetryChannels: TelemetryChannelDef[];
  // ---- expansion (schema v2) ----
  testPlans: import('./expansion').TestPlan[];
  decisions: import('./expansion').DecisionRecord[];
  events: import('./expansion').RaceEvent[];
  crewTasks: import('./expansion').CrewTask[];
  twin: import('./expansion').DigitalTwinComponent[];
  debriefs: import('./expansion').Debrief[];
  grants: import('./expansion').RemoteAccessGrant[];
  listings: import('./expansion').MarketplaceListing[];
}
