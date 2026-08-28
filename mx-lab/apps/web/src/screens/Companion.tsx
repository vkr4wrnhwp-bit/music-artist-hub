import React, { useState } from 'react';
import {
  appendAudit, checkCompatibility, diffRevisions, diffTrims, DIRECT_WRITE_LABEL,
} from '@mxlab/domain';
import { nav, useApp } from '../state';
import { fmtSigned, Help, Panel, Pill } from '../ui';

/**
 * Vortex companion workflow (section 8.6): Phase 1 never writes an ECU.
 * This screen produces the exact change sheet the tuner takes to the official
 * Vortex programming workflow, then records the confirmed transfer.
 */
export function TransferSheet({ revId }: { revId: string }) {
  const { db, user, update, allowed } = useApp();
  const revision = db.mapRevisions.find((r) => r.id === revId);
  const [bikeId, setBikeId] = useState(() =>
    db.bikes.find((b) => {
      const rev = db.mapRevisions.find((r) => r.id === revId);
      return rev && db.ecuInstances.find((e) => e.id === b.ecuInstanceId)?.ecuDefinitionId === rev.compatibility.ecuDefinitionId;
    })?.id ?? db.bikes[0]?.id ?? '');
  const [slot, setSlot] = useState(4);
  const [software, setSoftware] = useState('Official Vortex programming workflow (SIMULATED)');
  const [verifier, setVerifier] = useState('');

  if (!revision || !user) return <p>Revision not found.</p>;
  const map = db.maps.find((m) => m.id === revision.mapId)!;
  const parent = db.mapRevisions.find((r) => r.id === revision.parentRevisionId);
  const bike = db.bikes.find((b) => b.id === bikeId);
  const ecuInst = db.ecuInstances.find((e) => e.id === bike?.ecuInstanceId);
  const compat = bike ? checkCompatibility(revision.compatibility, db, bike) : null;
  const currentRev = db.mapRevisions.find((r) => r.id === bike?.currentMapRevisionId);
  const base = currentRev ?? parent;
  const diff = base ? diffRevisions(base, revision) : [];
  const trimDiff = base ? diffTrims(base, revision) : [];
  const confirmed = db.transfers.find((t) => t.mapRevisionId === revision.id && t.bikeId === bikeId);
  // First test loop: EXPORTED → TRANSFER_CONFIRMED. Re-loading an already
  // approved/tested revision onto another *compatible* bike is also allowed;
  // draft/review/rejected/retired revisions can never be transferred.
  const LOADABLE: Array<typeof revision.state> = ['EXPORTED', 'TRANSFER_CONFIRMED', 'TESTED', 'ACCEPTED', 'TEAM_BASELINE'];
  const canConfirm = allowed('transfer.confirm') && LOADABLE.includes(revision.state) && compat && !compat.blocking && !confirmed;

  return (
    <div>
      <div className="page-title">
        <h1>Companion transfer — <span className="mono">{map.name}-{revision.rev}</span></h1>
        <Pill tone="sim">SIMULATED EXTERNAL WORKFLOW</Pill>
      </div>
      <div className="write-disabled no-print" style={{ marginBottom: 14 }}>{DIRECT_WRITE_LABEL}</div>
      <Help id="companion">
        MX LAB does not touch the ECU. The tuner performs this change in the official Vortex software;
        this sheet tells them <b>exactly which cells and settings change</b>, and the confirmation below
        records who did it, on which bike and ECU, and whether a second person verified it.
      </Help>

      <div className="cols">
        <div>
          <Panel title="Tuner change sheet">
            <dl className="kv">
              <dt>Map</dt><dd className="mono">{map.name}-{revision.rev}</dd>
              <dt>Baseline shown vs</dt><dd className="mono">{base ? `${map.name}-${base.rev}` : 'zero map'}</dd>
              <dt>Bike</dt><dd className="mono">{bike?.label ?? '—'}</dd>
              <dt>ECU serial</dt><dd className="mono">{ecuInst?.serialNumber ?? '—'}</dd>
              <dt>Target slot</dt><dd className="mono">{slot}</dd>
              <dt>Authored by</dt><dd>{db.users.find((u) => u.id === revision.authorUserId)?.name}</dd>
              <dt>Approved by</dt><dd>{revision.approvedByUserId ? db.users.find((u) => u.id === revision.approvedByUserId)?.name : '—'}</dd>
            </dl>
            <h4 style={{ margin: '12px 0 6px', fontSize: 13 }}>Cell changes ({diff.length})</h4>
            <div className="tbl-scroll" style={{ maxHeight: 260, overflowY: 'auto' }}>
              <table className="data">
                <thead><tr><th>Table</th><th>RPM</th><th>Throttle</th><th>From</th><th>To</th><th>Δ</th></tr></thead>
                <tbody>
                  {diff.map((d, i) => {
                    const td = map.tableDefs.find((x) => x.id === d.tableId)!;
                    const ax = map.axes.find((a) => a.id === td.xAxisId)!;
                    const ay = map.axes.find((a) => a.id === td.yAxisId)!;
                    return (
                      <tr key={i}>
                        <td>{td.label}</td>
                        <td className="num">{ay.breakpoints[d.y].toLocaleString()}</td>
                        <td className="num">{ax.breakpoints[d.x]}{ax.unit}</td>
                        <td className="num">{d.a}{td.unit}</td>
                        <td className="num"><b>{d.b}{td.unit}</b></td>
                        <td className="num">{fmtSigned(d.delta, 1)}</td>
                      </tr>
                    );
                  })}
                  {diff.length === 0 && <tr><td colSpan={6} className="hint">No cell differences against the shown baseline.</td></tr>}
                </tbody>
              </table>
            </div>
            {trimDiff.length > 0 && (
              <>
                <h4 style={{ margin: '12px 0 6px', fontSize: 13 }}>Global setting changes</h4>
                <table className="data">
                  <tbody>
                    {trimDiff.map((t) => <tr key={t.trim}><td>{t.trim} trim</td><td className="num">{t.a} → <b>{t.b}</b></td></tr>)}
                  </tbody>
                </table>
              </>
            )}
            <div className="btn-row no-print" style={{ marginTop: 12 }}>
              <button className="btn" onClick={() => window.print()}>Print change sheet</button>
            </div>
            <p className="print-only hint">
              SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE. Transfer to be performed only in the
              official Vortex programming workflow by an authorized tuner.
              Signature (performer): ______________________ · Signature (verifier): ______________________
            </p>
          </Panel>
        </div>

        <div>
          <Panel title="Transfer confirmation">
            <div className="field">
              <label>Bike receiving the map</label>
              <select value={bikeId} onChange={(e) => setBikeId(e.target.value)}>
                {db.bikes.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
              </select>
            </div>
            {compat && (
              <p style={{ margin: '0 0 10px' }}>
                <Pill tone={compat.blocking ? 'critical' : compat.verdict === 'Compatible' ? 'good' : 'warning'}>{compat.verdict}</Pill>
                {compat.blocking && <span className="hint" style={{ display: 'block', marginTop: 4 }}>{compat.details[0]} Transfer is blocked.</span>}
              </p>
            )}
            <div className="field">
              <label>Target map slot</label>
              <input type="number" min={1} max={10} value={slot} onChange={(e) => setSlot(parseInt(e.target.value, 10) || 1)} />
            </div>
            <div className="field">
              <label>External software used</label>
              <input value={software} onChange={(e) => setSoftware(e.target.value)} />
            </div>
            <div className="field">
              <label>Second-person verification (optional)</label>
              <select value={verifier} onChange={(e) => setVerifier(e.target.value)}>
                <option value="">— none —</option>
                {db.users.filter((u) => u.id !== user.id && (u.role === 'tuner' || u.role === 'mechanic' || u.role === 'crew_chief')).map((u) => (
                  <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
                ))}
              </select>
            </div>
            {confirmed ? (
              <p><Pill tone="good">Transfer confirmed</Pill> <span className="hint">{new Date(confirmed.transferredAt).toLocaleString()} by {db.users.find((u) => u.id === confirmed.performedByUserId)?.name} (SIMULATED)</span></p>
            ) : (
              <button className="btn primary" disabled={!canConfirm} title={!allowed('transfer.confirm') ? 'Your role cannot confirm transfers'
                : !LOADABLE.includes(revision.state) ? `Revision state ${revision.state} is not loadable`
                  : compat?.blocking ? 'Blocked by compatibility' : undefined}
                onClick={() => {
                  update((d) => {
                    const rev = d.mapRevisions.find((x) => x.id === revId)!;
                    const b = d.bikes.find((x) => x.id === bikeId)!;
                    d.transfers.push({
                      id: `xfer-${Date.now()}`, mapRevisionId: rev.id, bikeId: b.id,
                      ecuInstanceId: b.ecuInstanceId ?? 'unknown', slot,
                      externalSoftware: software, performedByUserId: user.id,
                      verifiedByUserId: verifier || undefined,
                      transferredAt: new Date().toISOString(),
                      independentlyConfirmed: !!verifier, simulated: true,
                    });
                    if (rev.state === 'EXPORTED') rev.state = 'TRANSFER_CONFIRMED';
                    b.currentMapRevisionId = rev.id;
                    b.currentMapSlot = slot;
                    const slots = d.mapSlots[b.id] ?? [];
                    const sl = slots.find((s) => s.slot === slot);
                    if (sl) { sl.mapRevisionId = rev.id; sl.purpose = 'Under test'; }
                    appendAudit(d, user.id, 'transfer.confirm', 'MapRevision', rev.id,
                      `SIMULATED external transfer of ${rev.rev} to ${b.label} slot ${slot}${verifier ? `, second-person verified by ${verifier}` : ''}.`);
                  });
                }}>
                Confirm external transfer (SIMULATED)
              </button>
            )}
            <p className="hint" style={{ marginTop: 8 }}>
              Confirming does not write anything to an ECU — it records that a person completed the
              change in the external Vortex workflow. The next test session on this bike is associated
              with this revision automatically.
            </p>
            {confirmed && (
              <div className="btn-row" style={{ marginTop: 8 }}>
                <button className="btn small primary" onClick={() => nav('session/new')}>Create test session →</button>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
