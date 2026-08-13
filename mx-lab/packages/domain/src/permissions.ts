import type { Role } from './types';

/**
 * Central permission matrix. UI and engines both consult this — an action
 * absent from a role's set is denied everywhere, including in tests.
 */
export type Action =
  | 'bike.create' | 'bike.editIdentity' | 'bike.assignRider' | 'bike.retire'
  | 'setup.edit' | 'maintenance.record' | 'trim.record'
  | 'ecu.editDefinition' | 'ecu.verify'
  | 'map.view' | 'map.createRevision' | 'map.editDraft' | 'map.submitForReview'
  | 'map.approveForTest' | 'map.reject' | 'map.promoteBaseline' | 'map.retire'
  | 'map.export'
  | 'envelope.define'
  | 'transfer.confirm' | 'transfer.verifySecond'
  | 'session.create' | 'session.run' | 'session.view'
  | 'feedback.submit' | 'marker.review'
  | 'ai.review' | 'ai.decide'
  | 'abtest.conclude'
  | 'telemetry.configure' | 'telemetry.calibrate'
  | 'hardware.manage' | 'cnc.manage'
  | 'report.export'
  | 'user.manage' | 'audit.view';

const ALL_VIEW: Action[] = ['map.view', 'session.view', 'audit.view'];

const MATRIX: Record<Role, Action[]> = {
  org_admin: [
    ...ALL_VIEW, 'bike.create', 'bike.editIdentity', 'bike.assignRider', 'bike.retire',
    'setup.edit', 'maintenance.record', 'trim.record', 'ecu.editDefinition', 'ecu.verify',
    'map.createRevision', 'map.editDraft', 'map.submitForReview', 'map.approveForTest',
    'map.reject', 'map.promoteBaseline', 'map.retire', 'map.export', 'envelope.define',
    'transfer.confirm', 'transfer.verifySecond', 'session.create', 'session.run',
    'feedback.submit', 'marker.review', 'ai.review', 'ai.decide', 'abtest.conclude',
    'telemetry.configure', 'telemetry.calibrate', 'hardware.manage', 'cnc.manage',
    'report.export', 'user.manage',
  ],
  team_manager: [
    ...ALL_VIEW, 'bike.assignRider', 'session.create', 'report.export',
    'user.manage', 'abtest.conclude',
  ],
  crew_chief: [
    ...ALL_VIEW, 'bike.assignRider', 'session.create', 'session.run',
    'report.export', 'abtest.conclude', 'marker.review',
  ],
  tuner: [
    ...ALL_VIEW, 'map.createRevision', 'map.editDraft', 'map.submitForReview',
    'map.approveForTest', 'map.reject', 'map.promoteBaseline', 'map.retire', 'map.export',
    'envelope.define', 'ai.review', 'ai.decide', 'abtest.conclude',
    'session.create', 'session.run', 'marker.review', 'report.export',
    'bike.create', 'bike.editIdentity',
  ],
  mechanic: [
    ...ALL_VIEW, 'setup.edit', 'maintenance.record', 'trim.record',
    'transfer.confirm', 'session.run', 'bike.editIdentity',
  ],
  engine_builder: [...ALL_VIEW, 'setup.edit', 'maintenance.record'],
  suspension_tech: [...ALL_VIEW, 'setup.edit', 'maintenance.record'],
  rider: ['session.view', 'feedback.submit', 'marker.review'],
  data_engineer: [
    ...ALL_VIEW, 'telemetry.configure', 'telemetry.calibrate', 'report.export',
  ],
  hardware_engineer: [
    ...ALL_VIEW, 'hardware.manage', 'cnc.manage', 'telemetry.calibrate', 'report.export',
  ],
  viewer: ALL_VIEW,
};

export function can(role: Role, action: Action): boolean {
  return MATRIX[role]?.includes(action) ?? false;
}

/** Riders can never approve maps, edit ECU definitions, confirm transfers, or delete audit history. */
export const RIDER_FORBIDDEN: Action[] = [
  'map.approveForTest', 'ecu.editDefinition', 'transfer.confirm', 'envelope.define',
];

export function assertCan(role: Role, action: Action): void {
  if (!can(role, action)) {
    throw new Error(`Permission denied: role "${role}" may not perform "${action}"`);
  }
}
