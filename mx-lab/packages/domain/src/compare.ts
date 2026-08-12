import { compareSessions } from './aiEngineer';
import type { Db, Session } from './types';
import type { ComparisonVariable, Confidence, ConfidenceInput, RankedContributor } from './expansion';

/** Unified confidence — computed, never arbitrary (expansion spec). */
export function confidenceFrom(inp: ConfidenceInput): Confidence {
  let pct = 20;
  pct += Math.min(40, inp.sampleSize * 8);                 // sample size dominates
  pct += Math.round(inp.conditionSimilarity * 20);
  pct -= inp.variablesChanged * 8;                          // uncontrolled variables cost
  if (!inp.dataQualityOk) pct = Math.min(pct, 50);
  pct = Math.max(5, Math.min(90, pct));
  const label = pct >= 65 ? 'high' : pct >= 40 ? 'moderate' : 'low';
  return {
    pct, label,
    basis: `${inp.sampleSize} comparable record${inp.sampleSize === 1 ? '' : 's'} · ${inp.variablesChanged} uncontrolled variable${inp.variablesChanged === 1 ? '' : 's'} · data quality ${inp.dataQualityOk ? 'OK' : 'degraded'}`,
  };
}

/** Full configuration diff between two sessions (WHAT CHANGED). */
export function compareSetups(db: Db, a: Session, b: Session, holdConstant: string[] = [], intendedFields: string[] = []): ComparisonVariable[] {
  const revA = db.mapRevisions.find((r) => r.id === a.setupSnapshot.mapRevisionId);
  const revB = db.mapRevisions.find((r) => r.id === b.setupSnapshot.mapRevisionId);
  const out: ComparisonVariable[] = [];
  const add = (field: string, label: string, va: string | number | undefined, vb: string | number | undefined) => {
    const A = String(va ?? '—');
    const B = String(vb ?? '—');
    out.push({
      field, label, a: A, b: B, changed: A !== B,
      shouldHoldConstant: holdConstant.includes(field) && A !== B,
      intended: intendedFields.includes(field) && A !== B,
    });
  };
  add('map', 'Map', revA?.rev, revB?.rev);
  add('slot', 'Map slot', a.setupSnapshot.mapSlot, b.setupSnapshot.mapSlot);
  add('trims', 'Trims', Object.entries(a.setupSnapshot.trims).map(([k, v]) => `${k}:${v}`).join(' '), Object.entries(b.setupSnapshot.trims).map(([k, v]) => `${k}:${v}`).join(' '));
  add('engineBuild', 'Engine build', a.setupSnapshot.engineBuildId, b.setupSnapshot.engineBuildId);
  add('fuel', 'Fuel', a.setupSnapshot.setup.fuelId, b.setupSnapshot.setup.fuelId);
  add('gearing', 'Gearing', a.setupSnapshot.setup.gearing, b.setupSnapshot.setup.gearing);
  add('tire', 'Rear tire', a.setupSnapshot.setup.tireModel, b.setupSnapshot.setup.tireModel);
  add('pressureR', 'Rear pressure (bar)', a.setupSnapshot.setup.tirePressureRear, b.setupSnapshot.setup.tirePressureRear);
  add('pressureF', 'Front pressure (bar)', a.setupSnapshot.setup.tirePressureFront, b.setupSnapshot.setup.tirePressureFront);
  add('suspension', 'Suspension', a.setupSnapshot.setup.suspension, b.setupSnapshot.setup.suspension);
  add('sag', 'Sag (mm)', a.setupSnapshot.setup.sagMm, b.setupSnapshot.setup.sagMm);
  add('forkHeight', 'Fork height (mm)', a.setupSnapshot.setup.forkHeightMm, b.setupSnapshot.setup.forkHeightMm);
  add('clutch', 'Clutch', a.setupSnapshot.setup.clutch, b.setupSnapshot.setup.clutch);
  add('weather', 'Ambient', `${a.weather.ambientC}°C ${a.weather.humidityPct}%RH`, `${b.weather.ambientC}°C ${b.weather.humidityPct}%RH`);
  add('trackCond', 'Track condition', `${a.trackCondition.surfaceType}, ${a.trackCondition.moisture}`, `${b.trackCondition.surfaceType}, ${b.trackCondition.moisture}`);
  add('hours', 'Engine hours', a.setupSnapshot.hoursAtSession.toFixed(1), b.setupSnapshot.hoursAtSession.toFixed(1));
  add('hardware', 'Logger', a.hardwareCheck.deviceId, b.hardwareCheck.deviceId);
  return out;
}

/** WHAT CHANGED? — automatic diff of a session against the previous relevant baseline. */
export function whatChanged(db: Db, session: Session): {
  baseline: Session | null;
  vars: ComparisonVariable[];
  warnings: string[];
} {
  const baseline = [...db.sessions]
    .filter((s) => s.bikeId === session.bikeId && s.startedAt < session.startedAt && s.status === 'complete')
    .sort((x, y) => y.startedAt.localeCompare(x.startedAt))[0] ?? null;
  if (!baseline) return { baseline: null, vars: [], warnings: ['No previous session on this bike — nothing to diff.'] };

  // did this session belong to a test plan with hold-constant rules?
  const plan = db.testPlans.find((p) => p.variants.some((v) => v.sessionId === session.id));
  const intended = plan ? planIntendedFields(plan) : [];
  const hold = plan ? plan.holdConstant : [];
  const vars = compareSetups(db, baseline, session, hold, intended);

  const warnings: string[] = [];
  const violations = vars.filter((v) => v.shouldHoldConstant);
  if (violations.length) {
    warnings.push(`Variables that should have remained constant changed: ${violations.map((v) => v.label).join(', ')}. Result attribution will be weaker.`);
  }
  const uncontrolled = vars.filter((v) => v.changed && !v.intended && !['weather', 'trackCond', 'hours'].includes(v.field));
  if (!plan && uncontrolled.length > 1) {
    warnings.push(`${uncontrolled.length} configuration variables changed at once with no test plan — this was uncontrolled testing.`);
  }
  if (session.setupSnapshot.engineBuildId !== baseline.setupSnapshot.engineBuildId) {
    warnings.push('Engine build changed — sessions are not comparable as an A/B.');
  }
  return { baseline, vars, warnings };
}

/** which config fields differ between a test plan's variants (the intended change) */
export function planIntendedFields(plan: { variants: Array<{ mapRevisionId?: string; gearing?: string; tirePressureRear?: number; trims?: Record<string, number> }> }): string[] {
  const fields: string[] = [];
  const vs = plan.variants;
  if (new Set(vs.map((v) => v.mapRevisionId ?? '')).size > 1) fields.push('map');
  if (new Set(vs.map((v) => v.gearing ?? '')).size > 1) fields.push('gearing');
  if (new Set(vs.map((v) => v.tirePressureRear ?? '')).size > 1) fields.push('pressureR');
  if (new Set(vs.map((v) => JSON.stringify(v.trims ?? {}))).size > 1) fields.push('trims');
  return fields;
}

/** A test plan changing more than one field between variants is uncontrolled. */
export function detectUncontrolled(plan: Parameters<typeof planIntendedFields>[0]): string[] {
  const intended = planIntendedFields(plan);
  if (intended.length <= 1) return [];
  const names: Record<string, string> = { map: 'map', gearing: 'gearing', pressureR: 'tire pressure', trims: 'trims' };
  return [`WARNING — ${intended.map((f) => names[f] ?? f).join(' and ')} changed between variants. Result attribution will be weaker.`];
}

/** WHAT PROBABLY CAUSED IT — rank changed variables against observed deltas. */
export function rankContributors(db: Db, a: Session, b: Session, vars: ComparisonVariable[]): RankedContributor[] {
  const changed = vars.filter((v) => v.changed);
  const metrics = compareSessions(db, a, b);
  const slip = metrics.find((m) => m.metric.startsWith('Peak slip'));
  const out: RankedContributor[] = [];
  for (const v of changed) {
    switch (v.field) {
      case 'map':
        out.push({ label: `Map ${v.a} → ${v.b}`, weight: 0.5, rationale: slip && slip.b < slip.a ? 'Slip decreased with the map change — delivery is the leading candidate.' : 'Delivery change is the intended variable of this comparison.' });
        break;
      case 'gearing':
        out.push({ label: `Gearing ${v.a} → ${v.b}`, weight: 0.35, rationale: 'Final drive shifts RPM at every corner exit; affects drive and starts.' });
        break;
      case 'pressureR':
        out.push({ label: `Rear pressure ${v.a} → ${v.b}`, weight: 0.3, rationale: 'Contact patch change alters traction — confounds any map conclusion.' });
        break;
      case 'suspension': case 'sag': case 'forkHeight':
        out.push({ label: `${v.label} ${v.a} → ${v.b}`, weight: 0.28, rationale: 'Chassis change affects the same corners a map change would.' });
        break;
      case 'trackCond': case 'weather':
        out.push({ label: `${v.label} ${v.a} → ${v.b}`, weight: 0.22, rationale: 'Environment drift — not attributable to the machine.' });
        break;
      case 'hours':
        out.push({ label: `Engine hours ${v.a} → ${v.b}`, weight: 0.1, rationale: 'Engine condition drift is small but nonzero.' });
        break;
      default:
        if (!['slot', 'hardware'].includes(v.field)) {
          out.push({ label: `${v.label} ${v.a} → ${v.b}`, weight: 0.15, rationale: 'Changed between the sessions.' });
        }
    }
  }
  return out.sort((x, y) => y.weight - x.weight);
}
