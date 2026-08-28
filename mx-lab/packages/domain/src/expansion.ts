/**
 * TRACE expansion domain types — Phases A–E.
 * Honest state labels are part of the data model: nothing computed by an
 * unvalidated algorithm may present itself as production truth.
 */
import type { Provenance } from './types';

export type FeatureState = 'REAL' | 'SIMULATED' | 'DEVELOPMENT' | 'SHELL' | 'DISABLED';

// ------------------------------------------------------------- confidence

/** Unified confidence model — never an arbitrary number. */
export interface ConfidenceInput {
  sampleSize: number;         // comparable sessions/records
  dataQualityOk: boolean;
  conditionSimilarity: number; // 0..1
  variablesChanged: number;    // uncontrolled variables in the evidence
}
export interface Confidence {
  pct: number;
  label: 'low' | 'moderate' | 'high';
  basis: string;
}

// ------------------------------------------------------------- compare

export interface ComparisonVariable {
  field: string;
  label: string;
  a: string;
  b: string;
  changed: boolean;
  /** true when a test plan said this must stay constant */
  shouldHoldConstant?: boolean;
  /** the variable the test intended to change */
  intended?: boolean;
}

export interface RankedContributor {
  label: string;
  weight: number;
  rationale: string;
}

// ------------------------------------------------------------- test planner

export interface TestVariant {
  id: string;              // 'A' | 'B' | 'C'
  label: string;
  mapRevisionId?: string;
  gearing?: string;
  tirePressureRear?: number;
  trims?: Record<string, number>;
  note?: string;
  sessionId?: string;      // linked once run
}

export type TestPlanKind = 'ab' | 'abc' | 'blind' | 'rider_preference' | 'start' | 'section' | 'durability';

export interface TestPlan {
  id: string;
  orgId: string;
  objective: string;
  kind: TestPlanKind;
  bikeId: string;
  riderId: string;
  trackId?: string;
  sectionId?: string;
  variants: TestVariant[];
  holdConstant: string[];
  status: 'planned' | 'running' | 'complete' | 'abandoned';
  createdByUserId: string;
  createdAt: string;
  conclusion?: string;
  decisionId?: string;
}

// ------------------------------------------------------------- digital twin

export type TwinSystem =
  | 'Engine' | 'ECU' | 'Intake' | 'Exhaust' | 'Fuel' | 'Fork' | 'Shock'
  | 'Front wheel' | 'Rear wheel' | 'Tires' | 'Brakes' | 'Gearing' | 'Chain'
  | 'Clutch' | 'Controls' | 'MX Node' | 'Sensors';

export interface TwinServiceEntry { at: string; note: string; hoursAt: number }

export interface DigitalTwinComponent {
  id: string;               // "S04"
  bikeId: string;
  system: TwinSystem;
  label: string;            // "Shock S04"
  rev: string;
  hours: number;
  installedAt: string;
  typicalServiceH?: number; // team's historical interval
  serviceHistory: TwinServiceEntry[];
  setupNote?: string;
  notes?: string;
  provenance: Provenance;
}

export interface ComponentLifeEstimate {
  componentId: string;
  status: 'OK' | 'Approaching service' | 'Service due' | 'Insufficient history';
  detail: string;
  kind: 'Scheduled service' | 'Predicted service' | 'Measured degradation' | 'AI estimate';
  state: FeatureState;      // DEVELOPMENT until validated on real components
}

export interface ReliabilityFactor { label: string; score: number; detail: string; critical: boolean; pass: boolean }
export interface BikeReliability {
  scorePct: number | null;  // null when a critical gate overrides
  overriddenBy?: string;
  factors: ReliabilityFactor[];
}

// ------------------------------------------------------------- rider intelligence

export interface RiderDNA {
  riderId: string;
  /** MEASURED — computed from telemetry */
  measured: {
    typicalRpmBand: [number, number];
    throttleAggressiveness: number;   // 0..1 mean |dTPS|
    clutchUsePctOfLap: number;
    avgMinCornerSpeed: number;
    lapConsistency: number;           // σ seconds
    sessions: number;
  };
  /** RIDER REPORTED */
  preferences: {
    delivery: string;
    engineBraking: string;
    initialHit: string;
  };
  /** AI INFERENCE — clearly separated */
  inferred: {
    setupSensitivity: 'low' | 'moderate' | 'high';
    trackTypeStrength: string;
    basis: string;
  };
  state: FeatureState;
}

export interface CoachingInsight {
  sessionId: string;
  riderId: string;
  text: string;
  evidence: string;
  shareableWithRider: boolean;
  provenance: 'CALCULATED';
  state: FeatureState;
}

export interface FatigueEstimate {
  sessionId: string;
  detected: boolean;
  onsetLap?: number;
  evidence: string[];
  disclaimer: 'DEVELOPMENT ESTIMATE — NOT MEDICAL OR SAFETY DIAGNOSIS';
  state: 'DEVELOPMENT';
}

// ------------------------------------------------------------- race operations

export interface PlannedSlot { label: string; sessionId?: string }
export interface RaceDay { date: string; label: string; slots: PlannedSlot[] }
export interface RaceEvent {
  id: string;
  orgId: string;
  name: string;
  trackId: string;
  days: RaceDay[];
  notes?: string;
}

export interface ChecklistItem {
  id: string;
  label: string;
  status: 'pass' | 'blocked' | 'manual';
  detail: string;
  checked?: boolean;        // for manual items
}

export interface CrewTask {
  id: string;
  orgId: string;
  assigneeUserId: string;
  title: string;
  bikeId?: string;
  status: 'assigned' | 'in_progress' | 'verified';
  createdAt: string;
}

export interface DecisionRecord {
  id: string;
  orgId: string;
  at: string;
  authorUserId: string;
  bikeId?: string;
  riderId?: string;
  sessionIds: string[];
  decision: string;
  rationale: string;
  outcome?: string;
  followUp?: string;
}

export interface Debrief {
  id: string;
  orgId: string;
  date: string;             // yyyy-mm-dd
  learned: string[];
  tomorrow: string[];
  approvedByUserId?: string;
  editedByUserId?: string;
}

// ------------------------------------------------------------- knowledge & search

export interface KnowledgeCitation {
  kind: 'session' | 'decision' | 'abtest' | 'insight' | 'maintenance' | 'debrief' | 'map';
  id: string;
  label: string;
  href: string;
}

export interface KnowledgeAnswer {
  answer: string[];         // paragraphs — composed only from real records
  citations: KnowledgeCitation[];
  confidence: Confidence;
  missing: string[];
  state: FeatureState;      // DEVELOPMENT — keyword retrieval, not validated NLU
}

export interface SearchHit {
  kind: string;
  id: string;
  title: string;
  detail: string;
  href: string;
}

// ------------------------------------------------------------- access & marketplace

export interface RemoteAccessGrant {
  id: string;
  orgId: string;
  tunerName: string;
  bikeIds: string[];
  readTelemetry: boolean;
  readMaps: boolean;
  commentAccess: boolean;
  exportAllowed: boolean;
  mapEditAllowed: boolean;
  createdByUserId: string;
  createdAt: string;
  expiresAt: string;
  revokedAt?: string;
  state: 'SIMULATED';       // enforcement is local-demo until the backend ships
}

export interface MarketplaceListing {
  id: string;
  title: string;
  author: string;
  version: string;
  validationLevel: 'Unvalidated' | 'Author tested' | 'TRACE verified';
  compatibility: string;
  requiredHardware: string[];
  requiredFuel: string;
  disclaimer: string;
  state: 'SHELL';
}

// ------------------------------------------------------------- setup intelligence

export interface SetupPerformanceRecord {
  key: string;              // human-readable setup key
  sessions: string[];
  riderId: string;
  bikeId: string;
  trackId: string;
  surface: string;
  gearing: string;
  tirePressureRear: number;
  mapRev: string;
  bestLap: number;
  meanLap: number;
  lapSigma: number;
  peakSlipP95: number;
}

export interface SetupRecommendation {
  mapRev: string;
  gearing: string;
  tirePressureRear: number;
  sagMm: number;
  reason: string;
  confidence: Confidence;
  comparableSessions: number;
  citations: KnowledgeCitation[];
  state: FeatureState;      // DEVELOPMENT — starting point only, needs confirmation
}
