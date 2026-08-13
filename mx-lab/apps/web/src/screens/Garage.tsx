import React from 'react';
import { computeReadiness } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Pill, readinessTone } from '../ui';

export function Garage() {
  const { db, allowed } = useApp();

  return (
    <div>
      <div className="page-title">
        <h1>Fleet</h1>
        <span className="sub">{db.org.name} · {db.bikes.filter((b) => !b.retired).length} bikes</span>
        {allowed('bike.create') && (
          <button className="btn small" style={{ marginLeft: 'auto' }} onClick={() => nav('bike/new')}>+ Register bike</button>
        )}
      </div>
      <Help id="garage">
        Readiness equals the <b>worst unresolved critical gate</b> — a bike isn't test-ready because
        someone feels ready, it's ready because every confirmed record says so. Click a card to see
        which gate is blocking.
      </Help>
      <div className="fleet">
        {db.bikes.filter((b) => !b.retired).map((bike) => {
          const model = db.bikeModels.find((m) => m.id === bike.bikeModelId);
          const rider = db.riders.find((r) => r.id === bike.assignedRiderId);
          const ecuDef = db.ecuDefinitions.find(
            (d) => d.id === db.ecuInstances.find((e) => e.id === bike.ecuInstanceId)?.ecuDefinitionId,
          );
          const build = db.engineBuilds.find((x) => x.id === bike.engineBuildId);
          const rev = db.mapRevisions.find((r) => r.id === bike.currentMapRevisionId);
          const map = db.maps.find((m) => m.id === rev?.mapId);
          const device = db.devices.find((d) => d.id === bike.hardwareDeviceId);
          const lastSession = [...db.sessions].filter((s) => s.bikeId === bike.id)
            .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
          const readiness = computeReadiness(db, bike);
          const tone = readinessTone(readiness.status);
          const cardCls = tone === 'good' ? 'ready' : tone === 'critical' || tone === 'serious' ? 'blocked' : 'warn';
          const sensorIssues = device
            ? Object.values(device.channelHealth).filter((q) => q === 'Missing' || q === 'Intermittent' || q === 'Out of range').length
            : 0;
          return (
            <div key={bike.id} className={`bike-card ${cardCls}`} onClick={() => nav(`bike/${bike.id}`)}
              role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && nav(`bike/${bike.id}`)}>
              <h3>
                <span className="mono">{bike.label}</span>
                <Pill tone={tone}>{readiness.status}</Pill>
              </h3>
              <dl className="kv">
                <dt>Model</dt><dd>{model ? `${model.modelYear} ${model.manufacturer} ${model.model}` : '—'}</dd>
                <dt>Rider</dt><dd>{rider?.name ?? 'Unassigned'}</dd>
                <dt>ECU</dt><dd>{ecuDef ? `${ecuDef.model}` : 'Unknown'}</dd>
                <dt>Map</dt><dd className="mono">{rev ? `${map?.name}-${rev.rev} · slot ${bike.currentMapSlot}` : 'None'}</dd>
                <dt>Trims</dt><dd className="mono">{Object.entries(bike.trims).map(([k, v]) => `${k}:${v}`).join(' ')}</dd>
                <dt>Engine</dt><dd className="mono">{build?.code ?? '—'} · {bike.hoursSinceRebuild.toFixed(1)} h since rebuild</dd>
                <dt>Hours</dt><dd className="mono">{bike.totalHours.toFixed(1)} total</dd>
                <dt>Maintenance</dt>
                <dd><Pill tone={bike.maintenanceStatus === 'Current' ? 'good' : bike.maintenanceStatus === 'Due Soon' ? 'warning' : 'critical'}>{bike.maintenanceStatus}</Pill></dd>
                <dt>MX Node</dt>
                <dd>
                  {device ? <><Pill tone="sim">SIMULATED</Pill>{' '}
                    <Pill tone={sensorIssues ? 'serious' : 'good'}>{sensorIssues ? `${sensorIssues} sensor fault${sensorIssues > 1 ? 's' : ''}` : 'Sensors OK'}</Pill></>
                    : <Pill tone="critical">None</Pill>}
                </dd>
                <dt>Last session</dt><dd>{lastSession ? new Date(lastSession.startedAt).toLocaleDateString() + ' — ' + lastSession.objective : '—'}</dd>
                <dt>Open issues</dt><dd>{bike.openIssues.length ? bike.openIssues.join('; ') : 'None'}</dd>
              </dl>
            </div>
          );
        })}
      </div>
    </div>
  );
}
