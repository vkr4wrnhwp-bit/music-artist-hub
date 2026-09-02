-- The jobs write path.
--
-- Release: the human act that lets a job be raised against a revision. The
-- readiness picture is snapshotted because the question an outcome has to
-- answer later is "what did we know when we said run it", and readiness moves
-- as the shop's tools and instruments change. Releasing clears no gate.
ALTER TABLE "PartRevision" ADD COLUMN "releasedAt" DATETIME;
ALTER TABLE "PartRevision" ADD COLUMN "releasedBy" TEXT;
ALTER TABLE "PartRevision" ADD COLUMN "releaseSnapshotJson" TEXT;

-- Outcome scope, captured at recording time. A setup can be re-planned, and
-- an observation read back through it afterwards would silently start
-- describing a different machine. A null is a missing fact, not a wildcard.
ALTER TABLE "JobOutcome" ADD COLUMN "machineId" TEXT;
ALTER TABLE "JobOutcome" ADD COLUMN "workholdingId" TEXT;
ALTER TABLE "JobOutcome" ADD COLUMN "materialName" TEXT;
