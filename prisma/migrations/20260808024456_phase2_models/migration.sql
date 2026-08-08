-- CreateTable
CREATE TABLE "OperationState" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "setupId" TEXT,
    "sequence" INTEGER NOT NULL,
    "kind" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "envelopeX" REAL,
    "envelopeY" REAL,
    "envelopeZ" REAL,
    "remainingVolume" REAL,
    "removedVolume" REAL,
    "minWallThickness" REAL,
    "clampingSurfacesIntact" BOOLEAN NOT NULL DEFAULT true,
    "derivedGeometryJson" TEXT,
    "source" TEXT NOT NULL DEFAULT 'CALCULATED',
    "confidence" TEXT NOT NULL DEFAULT 'LOW',
    "notes" TEXT,
    CONSTRAINT "OperationState_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ShopKnowledge" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "machineId" TEXT,
    "toolId" TEXT,
    "materialId" TEXT,
    "toolClass" TEXT,
    "toolDiameter" REAL,
    "category" TEXT NOT NULL,
    "observation" TEXT NOT NULL,
    "parameter" TEXT,
    "thresholdValue" REAL,
    "thresholdUnit" TEXT,
    "direction" TEXT,
    "origin" TEXT NOT NULL DEFAULT 'OPERATOR',
    "jobCount" INTEGER NOT NULL DEFAULT 1,
    "lastObservedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recordedById" TEXT,
    "confidence" TEXT NOT NULL DEFAULT 'LOW',
    "active" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "ShopKnowledge_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "ShopKnowledge_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "ShopKnowledge_toolId_fkey" FOREIGN KEY ("toolId") REFERENCES "Tool" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "ShopKnowledge_materialId_fkey" FOREIGN KEY ("materialId") REFERENCES "Material" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "ShopKnowledge_recordedById_fkey" FOREIGN KEY ("recordedById") REFERENCES "User" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Disagreement" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "userId" TEXT,
    "subjectType" TEXT NOT NULL,
    "subjectId" TEXT,
    "partRevisionId" TEXT,
    "setupId" TEXT,
    "canvasPosition" TEXT NOT NULL,
    "reasoning" TEXT NOT NULL,
    "hasRunComparable" BOOLEAN NOT NULL DEFAULT false,
    "comparableJobId" TEXT,
    "proposedValue" TEXT,
    "status" TEXT NOT NULL DEFAULT 'OPEN',
    "resolution" TEXT,
    "gateCleared" BOOLEAN NOT NULL DEFAULT false,
    "shopKnowledgeId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Disagreement_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Disagreement_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Disagreement_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Disagreement_comparableJobId_fkey" FOREIGN KEY ("comparableJobId") REFERENCES "Job" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Disagreement_shopKnowledgeId_fkey" FOREIGN KEY ("shopKnowledgeId") REFERENCES "ShopKnowledge" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Setup" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "sequence" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "orientation" TEXT NOT NULL DEFAULT 'TOP',
    "machineId" TEXT,
    "workholdingId" TEXT,
    "workOffset" TEXT NOT NULL DEFAULT 'G54',
    "datumNote" TEXT,
    "gripDepth" REAL,
    "gripLength" REAL,
    "stockProjection" REAL,
    "parallelHeight" REAL,
    "jawSurface" TEXT,
    "clampForce" REAL,
    "hasPositiveStop" BOOLEAN NOT NULL DEFAULT false,
    "loadDirection" TEXT,
    "riskLevel" TEXT,
    "riskFactorsJson" TEXT,
    "estimatedCycleMinutes" REAL,
    "notes" TEXT,
    CONSTRAINT "Setup_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Setup_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Setup_workholdingId_fkey" FOREIGN KEY ("workholdingId") REFERENCES "WorkholdingDevice" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Setup" ("datumNote", "estimatedCycleMinutes", "gripDepth", "gripLength", "id", "machineId", "name", "notes", "orientation", "parallelHeight", "partRevisionId", "riskFactorsJson", "riskLevel", "sequence", "stockProjection", "workOffset", "workholdingId") SELECT "datumNote", "estimatedCycleMinutes", "gripDepth", "gripLength", "id", "machineId", "name", "notes", "orientation", "parallelHeight", "partRevisionId", "riskFactorsJson", "riskLevel", "sequence", "stockProjection", "workOffset", "workholdingId" FROM "Setup";
DROP TABLE "Setup";
ALTER TABLE "new_Setup" RENAME TO "Setup";
CREATE INDEX "Setup_partRevisionId_idx" ON "Setup"("partRevisionId");
CREATE UNIQUE INDEX "Setup_partRevisionId_sequence_key" ON "Setup"("partRevisionId", "sequence");
CREATE TABLE "new_Tool" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "toolNumber" INTEGER NOT NULL,
    "toolClass" TEXT NOT NULL,
    "manufacturer" TEXT,
    "product" TEXT,
    "description" TEXT NOT NULL,
    "diameter" REAL NOT NULL,
    "cornerRadius" REAL NOT NULL DEFAULT 0,
    "flutes" INTEGER NOT NULL,
    "material" TEXT NOT NULL,
    "coating" TEXT,
    "fluteLength" REAL NOT NULL,
    "overallLength" REAL NOT NULL,
    "stickout" REAL NOT NULL,
    "holderId" TEXT,
    "maxRPM" INTEGER NOT NULL,
    "recommendedMaterials" TEXT NOT NULL,
    "chiploadMin" REAL NOT NULL,
    "chiploadMax" REAL NOT NULL,
    "sfmMin" REAL NOT NULL,
    "sfmMax" REAL NOT NULL,
    "coolant" TEXT NOT NULL,
    "lifeRemaining" REAL NOT NULL DEFAULT 1,
    "costPerTool" REAL NOT NULL DEFAULT 0,
    "expectedLifeMinutes" REAL NOT NULL DEFAULT 120,
    "notes" TEXT,
    "condition" TEXT NOT NULL DEFAULT 'UNKNOWN',
    "actualStickout" REAL,
    "measuredRunout" REAL,
    "helixAngle" REAL,
    "regrindCount" INTEGER NOT NULL DEFAULT 0,
    "previousMaterial" TEXT,
    "lastUsedAt" DATETIME,
    "shopNotes" TEXT,
    CONSTRAINT "Tool_holderId_fkey" FOREIGN KEY ("holderId") REFERENCES "ToolHolder" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Tool_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_Tool" ("chiploadMax", "chiploadMin", "coating", "coolant", "cornerRadius", "costPerTool", "description", "diameter", "expectedLifeMinutes", "fluteLength", "flutes", "holderId", "id", "lifeRemaining", "manufacturer", "material", "maxRPM", "notes", "organizationId", "overallLength", "product", "recommendedMaterials", "sfmMax", "sfmMin", "stickout", "toolClass", "toolNumber") SELECT "chiploadMax", "chiploadMin", "coating", "coolant", "cornerRadius", "costPerTool", "description", "diameter", "expectedLifeMinutes", "fluteLength", "flutes", "holderId", "id", "lifeRemaining", "manufacturer", "material", "maxRPM", "notes", "organizationId", "overallLength", "product", "recommendedMaterials", "sfmMax", "sfmMin", "stickout", "toolClass", "toolNumber" FROM "Tool";
DROP TABLE "Tool";
ALTER TABLE "new_Tool" RENAME TO "Tool";
CREATE INDEX "Tool_organizationId_idx" ON "Tool"("organizationId");
CREATE UNIQUE INDEX "Tool_organizationId_toolNumber_key" ON "Tool"("organizationId", "toolNumber");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE INDEX "OperationState_partRevisionId_idx" ON "OperationState"("partRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "OperationState_partRevisionId_sequence_key" ON "OperationState"("partRevisionId", "sequence");

-- CreateIndex
CREATE INDEX "ShopKnowledge_organizationId_idx" ON "ShopKnowledge"("organizationId");

-- CreateIndex
CREATE INDEX "ShopKnowledge_organizationId_category_idx" ON "ShopKnowledge"("organizationId", "category");

-- CreateIndex
CREATE INDEX "Disagreement_organizationId_idx" ON "Disagreement"("organizationId");

-- CreateIndex
CREATE INDEX "Disagreement_partRevisionId_idx" ON "Disagreement"("partRevisionId");
