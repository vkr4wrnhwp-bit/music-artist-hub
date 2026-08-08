-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Feature" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "functionalRole" TEXT NOT NULL DEFAULT 'NONE',
    "critical" BOOLEAN NOT NULL DEFAULT false,
    "parametersJson" TEXT NOT NULL,
    "tolerancePlus" REAL,
    "toleranceMinus" REAL,
    "surfaceFinish" REAL,
    "inspectionMethod" TEXT,
    "matingComponent" TEXT,
    "matingDesignation" TEXT,
    "interfaceSide" TEXT,
    "rotatingUnderLoad" BOOLEAN NOT NULL DEFAULT false,
    "fitClass" TEXT,
    "notes" TEXT,
    "orderIndex" INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT "Feature_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_Feature" ("critical", "functionalRole", "id", "inspectionMethod", "kind", "label", "notes", "orderIndex", "parametersJson", "partRevisionId", "surfaceFinish", "toleranceMinus", "tolerancePlus") SELECT "critical", "functionalRole", "id", "inspectionMethod", "kind", "label", "notes", "orderIndex", "parametersJson", "partRevisionId", "surfaceFinish", "toleranceMinus", "tolerancePlus" FROM "Feature";
DROP TABLE "Feature";
ALTER TABLE "new_Feature" RENAME TO "Feature";
CREATE INDEX "Feature_partRevisionId_idx" ON "Feature"("partRevisionId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
