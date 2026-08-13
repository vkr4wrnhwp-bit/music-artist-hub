-- CreateTable
CREATE TABLE "BetaRunRecord" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "partRevisionId" TEXT,
    "ncProgramId" TEXT,
    "machineLabel" TEXT,
    "materialName" TEXT,
    "toolNotes" TEXT,
    "holderNotes" TEXT,
    "workholdingNotes" TEXT,
    "predictedCycleMinutes" REAL,
    "actualCycleMinutes" REAL,
    "predictedLoadNote" TEXT,
    "actualLoadNote" TEXT,
    "canvasRecommendation" TEXT,
    "verdict" TEXT NOT NULL,
    "wrongCategoriesJson" TEXT NOT NULL DEFAULT '[]',
    "whatWasWrong" TEXT,
    "measuredResultsNote" TEXT,
    "toolWearNote" TEXT,
    "chatter" BOOLEAN,
    "scrapOrFailure" BOOLEAN NOT NULL DEFAULT false,
    "correctiveAction" TEXT,
    "createdById" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "BetaRunRecord_organizationId_idx" ON "BetaRunRecord"("organizationId");
CREATE INDEX "BetaRunRecord_partRevisionId_idx" ON "BetaRunRecord"("partRevisionId");
