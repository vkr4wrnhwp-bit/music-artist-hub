# Machine telemetry — ARCHITECTURE ONLY, NOT CONNECTED

src/lib/telemetry.ts defines the consumer interfaces
(MachineTelemetrySource, SpindleLoadSample, FeedSample,
ActualCycleSample, ToolLifeSample) and the source registry (MTConnect,
OPC UA, controller logs, CSV import) — every source's status is the
literal type "NOT_CONNECTED", the only value that exists today, and
the /machines panel renders it verbatim per source.

No adapter is built. Nothing in CANVAS claims live machine data, and
the panel says exactly that. Long-term objective: calibrate estimated
load and cycle time against what the shop's machines actually did.
