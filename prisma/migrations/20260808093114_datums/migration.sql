-- CreateTable
CREATE TABLE "Datum" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "partRevisionId" TEXT NOT NULL,
    "letter" TEXT NOT NULL,
    "system" TEXT NOT NULL,
    "featureId" TEXT,
    "description" TEXT NOT NULL,
    "geometryType" TEXT NOT NULL DEFAULT 'PLANE',
    "proposedReason" TEXT,
    "acceptedByUser" BOOLEAN NOT NULL DEFAULT false,
    "acceptedAt" DATETIME,
    "source" TEXT NOT NULL DEFAULT 'SYSTEM',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Datum_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Datum_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Measurement" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sessionId" TEXT NOT NULL,
    "featureId" TEXT,
    "assetId" TEXT,
    "deviceId" TEXT,
    "label" TEXT NOT NULL,
    "measuredValue" REAL NOT NULL,
    "units" TEXT NOT NULL DEFAULT 'IN',
    "uncertainty" REAL NOT NULL,
    "repeatCount" INTEGER NOT NULL DEFAULT 1,
    "context" TEXT NOT NULL DEFAULT 'GENERAL',
    "suggestedNominal" REAL,
    "suggestedNominalLabel" TEXT,
    "suggestedFamily" TEXT,
    "suggestionConfidence" REAL,
    "suggestionBasis" TEXT,
    "resolution" TEXT NOT NULL DEFAULT 'PENDING',
    "resolvedValue" REAL,
    "resolvedBy" TEXT,
    "resolvedAt" DATETIME,
    "dependsOn" TEXT NOT NULL DEFAULT '[]',
    "datumId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Measurement_sessionId_fkey" FOREIGN KEY ("sessionId") REFERENCES "MeasurementSession" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Measurement_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Measurement_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "UploadedAsset" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Measurement_deviceId_fkey" FOREIGN KEY ("deviceId") REFERENCES "MetrologyDevice" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Measurement_datumId_fkey" FOREIGN KEY ("datumId") REFERENCES "Datum" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Measurement" ("assetId", "context", "createdAt", "dependsOn", "deviceId", "featureId", "id", "label", "measuredValue", "repeatCount", "resolution", "resolvedAt", "resolvedBy", "resolvedValue", "sessionId", "suggestedFamily", "suggestedNominal", "suggestedNominalLabel", "suggestionBasis", "suggestionConfidence", "uncertainty", "units") SELECT "assetId", "context", "createdAt", "dependsOn", "deviceId", "featureId", "id", "label", "measuredValue", "repeatCount", "resolution", "resolvedAt", "resolvedBy", "resolvedValue", "sessionId", "suggestedFamily", "suggestedNominal", "suggestedNominalLabel", "suggestionBasis", "suggestionConfidence", "uncertainty", "units" FROM "Measurement";
DROP TABLE "Measurement";
ALTER TABLE "new_Measurement" RENAME TO "Measurement";
CREATE INDEX "Measurement_sessionId_idx" ON "Measurement"("sessionId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE INDEX "Datum_partRevisionId_idx" ON "Datum"("partRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "Datum_partRevisionId_system_letter_key" ON "Datum"("partRevisionId", "system", "letter");
