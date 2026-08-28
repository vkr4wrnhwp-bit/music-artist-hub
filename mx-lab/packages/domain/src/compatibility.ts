import type { Bike, CompatibilityKey, CompatibilityResult, Db, EcuInstance } from './types';

/**
 * A map revision is authored against an exact compatibility key (section 7).
 * A revision approved for one bike is never automatically available to
 * another: every assignment re-runs this check, and blocking mismatches
 * prevent transfer confirmation.
 */
export function bikeCompatibilityKey(db: Db, bike: Bike): Partial<CompatibilityKey> {
  const model = db.bikeModels.find((m) => m.id === bike.bikeModelId);
  const ecuInst: EcuInstance | undefined = db.ecuInstances.find((e) => e.id === bike.ecuInstanceId);
  const ecuDef = db.ecuDefinitions.find((d) => d.id === ecuInst?.ecuDefinitionId);
  const build = db.engineBuilds.find((b) => b.id === bike.engineBuildId);
  return {
    manufacturer: model?.manufacturer,
    model: model?.model,
    modelYear: model?.modelYear,
    ecuDefinitionId: ecuDef?.id,
    ecuFirmware: ecuDef?.firmware,
    engineBuildId: build?.id,
    fuelId: bike.setup.fuelId,
    exhaustId: bike.setup.exhaustId,
    revLimit: build?.revLimit,
  };
}

export function checkCompatibility(revKey: CompatibilityKey, db: Db, bike: Bike): CompatibilityResult {
  const actual = bikeCompatibilityKey(db, bike);
  const details: string[] = [];

  const missing = (['manufacturer', 'model', 'modelYear', 'ecuDefinitionId', 'ecuFirmware', 'engineBuildId'] as const)
    .filter((k) => actual[k] === undefined);
  if (missing.length) {
    return {
      verdict: 'Unverified',
      blocking: true,
      details: [`Bike identity incomplete: ${missing.join(', ')} not confirmed. Complete Phase 0 inventory first.`],
    };
  }

  const fail = (verdict: CompatibilityResult['verdict'], detail: string): CompatibilityResult => ({
    verdict, blocking: true, details: [detail, ...details],
  });

  if (actual.ecuDefinitionId !== revKey.ecuDefinitionId) {
    return fail('ECU mismatch', `Revision authored for ECU definition ${revKey.ecuDefinitionId}; bike has ${actual.ecuDefinitionId}.`);
  }
  if (actual.ecuFirmware !== revKey.ecuFirmware) {
    return fail('Firmware mismatch', `Revision authored for firmware ${revKey.ecuFirmware}; bike ECU reports ${actual.ecuFirmware}.`);
  }
  if (actual.modelYear !== revKey.modelYear || actual.model !== revKey.model) {
    return fail('Model-year mismatch', `Revision authored for ${revKey.modelYear} ${revKey.model}; bike is ${actual.modelYear} ${actual.model}.`);
  }
  if (actual.engineBuildId !== revKey.engineBuildId) {
    return fail('Engine build mismatch', `Revision authored for engine build ${revKey.engineBuildId}; bike has ${actual.engineBuildId}.`);
  }
  if (actual.fuelId !== revKey.fuelId) {
    return fail('Fuel mismatch', `Revision authored for fuel ${revKey.fuelId}; bike is running ${actual.fuelId}.`);
  }

  if (actual.exhaustId !== revKey.exhaustId) {
    details.push(`Exhaust differs (${revKey.exhaustId} → ${actual.exhaustId}). Tuner must review before test.`);
    return { verdict: 'Requires tuner review', blocking: false, details };
  }
  if (actual.revLimit !== revKey.revLimit) {
    details.push(`Rev limit differs (${revKey.revLimit} → ${actual.revLimit}).`);
    return { verdict: 'Compatible with warning', blocking: false, details };
  }
  return { verdict: 'Compatible', blocking: false, details: ['All compatibility keys match.'] };
}
