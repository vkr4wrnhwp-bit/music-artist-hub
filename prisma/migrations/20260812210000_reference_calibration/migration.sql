-- CreateTable
CREATE TABLE "ReferenceCut" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "machineId" TEXT,
    "toolId" TEXT,
    "materialName" TEXT NOT NULL,
    "operation" TEXT NOT NULL,
    "docInches" REAL NOT NULL,
    "wocInches" REAL NOT NULL,
    "feedIpm" REAL NOT NULL,
    "rpm" INTEGER NOT NULL,
    "coolant" TEXT NOT NULL DEFAULT 'FLOOD',
    "result" TEXT NOT NULL,
    "notes" TEXT,
    "createdById" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "ReferenceCut_organizationId_idx" ON "ReferenceCut"("organizationId");

-- CreateTable
CREATE TABLE "MachineCalibrationRecord" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "machineId" TEXT NOT NULL,
    "programLabel" TEXT NOT NULL,
    "estimatedMinutes" REAL NOT NULL,
    "actualMinutes" REAL NOT NULL,
    "toolChangeSeconds" REAL,
    "spindleRampSeconds" REAL,
    "notes" TEXT,
    "createdById" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX "MachineCalibrationRecord_organizationId_machineId_idx" ON "MachineCalibrationRecord"("organizationId", "machineId");
