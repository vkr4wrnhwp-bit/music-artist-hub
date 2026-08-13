import { confidenceFrom } from './compare';
import { simulateSession } from './simulator';
import type { Db } from './types';
import type { KnowledgeAnswer, KnowledgeCitation, SearchHit } from './expansion';

/**
 * TRACE Knowledge + universal search.
 * Retrieval is structured-records-first with metadata filters; the answer is
 * COMPOSED from real records with citations, never generated free-form.
 * Labeled DEVELOPMENT: keyword intent matching, not validated NLU.
 */

export function searchAll(db: Db, query: string): SearchHit[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const hits: SearchHit[] = [];
  const push = (kind: string, id: string, title: string, detail: string, href: string) =>
    hits.push({ kind, id, title, detail, href });
  const m = (s: string | undefined) => (s ?? '').toLowerCase().includes(q);

  for (const b of db.bikes) {
    if (m(b.label) || m(b.setup.gearing)) push('Bike', b.id, b.label, `${b.setup.gearing} · ${b.maintenanceStatus}`, `#/bike/${b.id}`);
  }
  for (const r of db.riders) if (m(r.name)) push('Rider', r.id, r.name, r.preferredDelivery, '#/analyze/riders');
  for (const s of db.sessions) {
    if (m(s.objective) || m(s.trackCondition.surfaceType) || m(s.setupSnapshot.setup.gearing)) {
      push('Session', s.id, s.objective, `${new Date(s.startedAt).toLocaleDateString()} · ${db.bikes.find((b) => b.id === s.bikeId)?.label}`, `#/session/${s.id}`);
    }
  }
  for (const r of db.mapRevisions) {
    const map = db.maps.find((x) => x.id === r.mapId);
    if (m(r.rev) || m(map?.name) || m(r.notes)) push('Map', r.id, `${map?.name}-${r.rev}`, r.state.replaceAll('_', ' '), `#/maps/${r.id}`);
  }
  for (const c of db.twin) if (m(c.label) || m(c.id)) push('Component', c.id, c.label, `${c.hours.toFixed(1)} h · ${db.bikes.find((b) => b.id === c.bikeId)?.label}`, `#/bike/${c.bikeId}`);
  for (const d of db.decisions) if (m(d.decision) || m(d.rationale)) push('Decision', d.id, d.decision.slice(0, 70), new Date(d.at).toLocaleDateString(), '#/more/knowledge');
  for (const f of db.faults) if (m(f.code) || m(f.note)) push('Fault', f.id, f.code, f.note, `#/bike/${f.bikeId}`);
  for (const e of db.events) if (m(e.name)) push('Event', e.id, e.name, db.tracks.find((t) => t.id === e.trackId)?.name ?? '', '#/sessions/weekend');
  for (const t of db.tracks) if (m(t.name)) push('Track', t.id, t.name, t.surface, '#/analyze');
  for (const rec of db.recommendations) if (m(rec.observedEvent) || m(rec.likelyCause.category)) push('Insight', rec.id, rec.observedEvent, `${rec.confidencePct}% · ${rec.status.replaceAll('_', ' ')}`, `#/engineer/${rec.id}`);
  return hits.slice(0, 30);
}

const cite = {
  session: (db: Db, id: string): KnowledgeCitation => {
    const s = db.sessions.find((x) => x.id === id)!;
    return { kind: 'session', id, label: `${new Date(s.startedAt).toLocaleDateString()} · ${s.objective}`, href: `#/session/${id}` };
  },
  decision: (id: string, label: string): KnowledgeCitation => ({ kind: 'decision', id, label, href: '#/more/knowledge' }),
  abtest: (id: string, label: string): KnowledgeCitation => ({ kind: 'abtest', id, label, href: '#/analyze' }),
};

/** Ask TRACE — structured intent matching over real records only. */
export function askTrace(db: Db, question: string): KnowledgeAnswer {
  const q = question.toLowerCase();
  const answer: string[] = [];
  const citations: KnowledgeCitation[] = [];
  const missing: string[] = [];
  let sample = 0;

  const revByToken = db.mapRevisions.find((r) => q.includes(r.rev.toLowerCase()));

  // intent: what did we learn from a test / revision
  if ((q.includes('learn') || q.includes('test')) && revByToken) {
    const abs = db.abTests.filter((t) => t.revisionAId === revByToken.id || t.revisionBId === revByToken.id);
    const plans = db.testPlans.filter((p) => p.variants.some((v) => v.mapRevisionId === revByToken.id));
    const decs = db.decisions.filter((d) => d.decision.toLowerCase().includes(revByToken.rev.toLowerCase()) || d.rationale.toLowerCase().includes(revByToken.rev.toLowerCase()));
    for (const ab of abs) {
      answer.push(`${ab.name}: outcome ${ab.outcome ?? 'pending'}. ${ab.conclusion ?? ''} Rider preferred ${ab.riderPreferred ?? '—'}; telemetry ${ab.telemetrySupportsPreference ? 'agreed' : 'disagreed'}.`);
      citations.push(cite.abtest(ab.id, ab.name));
      if (ab.sessionAId) citations.push(cite.session(db, ab.sessionAId));
      if (ab.sessionBId) citations.push(cite.session(db, ab.sessionBId));
      sample += 2;
    }
    for (const p of plans.filter((x) => x.conclusion)) {
      answer.push(`Test plan “${p.objective}”: ${p.conclusion}`);
      for (const v of p.variants) if (v.sessionId) { citations.push(cite.session(db, v.sessionId)); sample++; }
    }
    for (const d of decs) {
      answer.push(`Decision (${new Date(d.at).toLocaleDateString()}): ${d.decision} — ${d.rationale}`);
      citations.push(cite.decision(d.id, d.decision.slice(0, 60)));
      d.sessionIds.forEach((id) => db.sessions.some((s) => s.id === id) && citations.push(cite.session(db, id)));
      sample++;
    }
    if (!answer.length) missing.push(`No A/B test, test plan conclusion, or decision on file mentions ${revByToken.rev}.`);
  }

  // intent: best starts
  else if (q.includes('start')) {
    const withStarts = db.sessions.filter((s) => db.startAttempts.some((a) => a.sessionId === s.id));
    if (withStarts.length) {
      for (const s of withStarts) {
        const attempts = db.startAttempts.filter((a) => a.sessionId === s.id);
        const best = attempts.reduce((a, b) => (a.timeTo30MphS < b.timeTo30MphS ? a : b));
        const rev = db.mapRevisions.find((r) => r.id === s.setupSnapshot.mapRevisionId);
        answer.push(`${new Date(s.startedAt).toLocaleDateString()} (${s.setupSnapshot.setup.gearing}, map ${rev?.rev}): best 0–30 mph ${best.timeTo30MphS.toFixed(2)}s across ${attempts.length} attempts.`);
        citations.push(cite.session(db, s.id));
        sample += attempts.length;
      }
      const gearDec = db.decisions.find((d) => d.decision.toLowerCase().includes('gear'));
      if (gearDec) { answer.push(`Related decision: ${gearDec.decision} — ${gearDec.rationale}`); citations.push(cite.decision(gearDec.id, gearDec.decision.slice(0, 60))); }
    } else missing.push('No start attempts recorded yet.');
  }

  // intent: coolant / overheating threshold — a real scan over the traces
  else if (q.includes('coolant') || q.includes('overheat')) {
    const fMatch = /(\d{2,3})\s*°?\s*f/.exec(q);
    const thresholdC = fMatch ? (parseInt(fMatch[1], 10) - 32) * 5 / 9 : 82;
    let found = 0;
    for (const s of db.sessions.filter((x) => x.status === 'complete')) {
      const sim = simulateSession(db, s);
      const peak = Math.max(...sim.channels.coolant);
      if (peak > thresholdC) {
        const bike = db.bikes.find((b) => b.id === s.bikeId);
        answer.push(`${new Date(s.startedAt).toLocaleDateString()} — ${bike?.label}: coolant peaked at ${peak.toFixed(0)}°C (${Math.round(peak * 9 / 5 + 32)}°F) during “${s.objective}”.`);
        citations.push(cite.session(db, s.id));
        found++;
        sample++;
      }
    }
    if (!found) answer.push(`No session exceeded ${thresholdC.toFixed(0)}°C (${Math.round(thresholdC * 9 / 5 + 32)}°F) coolant in the scanned traces.`);
    const coolFault = db.faults.find((f) => f.note.toLowerCase().includes('cool') || f.code.toLowerCase().includes('temp'));
    if (coolFault) missing.push(`Open fault to consider: ${coolFault.code} — ${coolFault.note}`);
  }

  // intent: what changed after an engine build
  else if (q.includes('build')) {
    const build = db.engineBuilds.find((b) => q.includes(b.code.toLowerCase().slice(-3)) || q.includes(b.code.toLowerCase()));
    if (build) {
      const sess = db.sessions.filter((s) => s.setupSnapshot.engineBuildId === build.id);
      answer.push(`${build.code}: ${sess.length} session${sess.length === 1 ? '' : 's'} on file. ${build.notes ?? ''}`);
      sess.slice(0, 4).forEach((s) => citations.push(cite.session(db, s.id)));
      sample += sess.length;
    } else missing.push('Could not match an engine build code in the question.');
  }

  // intent: last event / what did we run at <track>
  else if (q.includes('run at') || q.includes('event') || db.events.some((e) => q.includes(e.name.toLowerCase().split(' ')[0]))) {
    const ev = db.events.find((e) => q.includes(e.name.toLowerCase().split(' ')[0])) ?? db.events[0];
    if (ev) {
      const ids = ev.days.flatMap((d) => d.slots.map((s) => s.sessionId)).filter(Boolean) as string[];
      const sess = ids.map((id) => db.sessions.find((s) => s.id === id)).filter(Boolean);
      for (const s of sess) {
        const rev = db.mapRevisions.find((r) => r.id === s!.setupSnapshot.mapRevisionId);
        answer.push(`${ev.name} — ${s!.objective}: map ${rev?.rev}, gearing ${s!.setupSnapshot.setup.gearing}, rear ${s!.setupSnapshot.setup.tirePressureRear} bar.`);
        citations.push(cite.session(db, s!.id));
        sample++;
      }
      if (!sess.length) missing.push(`Event ${ev.name} has no linked sessions yet.`);
    } else missing.push('No race events on file.');
  }

  else {
    missing.push('Ask TRACE currently answers structured questions about tests, revisions, starts, engine builds, and events. Try mentioning a revision (e.g. R07), “starts”, a build code, or an event name.');
  }

  return {
    answer: answer.length ? answer : ['No matching team records.'],
    citations,
    confidence: confidenceFrom({ sampleSize: sample, dataQualityOk: true, conditionSimilarity: 0.8, variablesChanged: 0 }),
    missing,
    state: 'DEVELOPMENT',
  };
}
