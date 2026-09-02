-- Review findings kept rather than recomputed and forgotten, plus the human
-- responses recorded against them.
--
-- The finding content is a snapshot, not the source of truth: the engine is
-- re-run on every review. What persists is the history (first raised, last
-- seen, cleared) and the responses. A response carries the evidence digest it
-- was recorded against, so a response to changed evidence reads as stale
-- rather than silently still applying.
CREATE TABLE "ReviewFinding" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "findingKey" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "detail" TEXT NOT NULL,
    "method" TEXT NOT NULL,
    "evidenceJson" TEXT NOT NULL,
    "evidenceDigest" TEXT NOT NULL,
    "firstSeenAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lastSeenAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "clearedAt" TIMESTAMP(3),
    CONSTRAINT "ReviewFinding_pkey" PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX "ReviewFinding_partRevisionId_findingKey_key" ON "ReviewFinding"("partRevisionId", "findingKey");
CREATE INDEX "ReviewFinding_organizationId_idx" ON "ReviewFinding"("organizationId");
CREATE INDEX "ReviewFinding_partRevisionId_idx" ON "ReviewFinding"("partRevisionId");

CREATE TABLE "FindingResolution" (
    "id" TEXT NOT NULL,
    "findingId" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "note" TEXT NOT NULL,
    "actorType" TEXT NOT NULL DEFAULT 'HUMAN',
    "actorId" TEXT NOT NULL,
    "actorName" TEXT NOT NULL,
    "evidenceDigest" TEXT NOT NULL,
    "recordedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "FindingResolution_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "FindingResolution_findingId_idx" ON "FindingResolution"("findingId");

ALTER TABLE "FindingResolution" ADD CONSTRAINT "FindingResolution_findingId_fkey" FOREIGN KEY ("findingId") REFERENCES "ReviewFinding"("id") ON DELETE CASCADE ON UPDATE CASCADE;
