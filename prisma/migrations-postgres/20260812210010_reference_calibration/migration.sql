-- CreateTable
CREATE TABLE "ReferenceCut" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "machineId" TEXT,
    "toolId" TEXT,
    "materialName" TEXT NOT NULL,
    "operation" TEXT NOT NULL,
    "docInches" DOUBLE PRECISION NOT NULL,
    "wocInches" DOUBLE PRECISION NOT NULL,
    "feedIpm" DOUBLE PRECISION NOT NULL,
    "rpm" INTEGER NOT NULL,
    "coolant" TEXT NOT NULL DEFAULT 'FLOOD',
    "result" TEXT NOT NULL,
    "notes" TEXT,
    "createdById" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ReferenceCut_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "ReferenceCut_organizationId_idx" ON "ReferenceCut"("organizationId");

-- CreateTable
CREATE TABLE "MachineCalibrationRecord" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "machineId" TEXT NOT NULL,
    "programLabel" TEXT NOT NULL,
    "estimatedMinutes" DOUBLE PRECISION NOT NULL,
    "actualMinutes" DOUBLE PRECISION NOT NULL,
    "toolChangeSeconds" DOUBLE PRECISION,
    "spindleRampSeconds" DOUBLE PRECISION,
    "notes" TEXT,
    "createdById" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "MachineCalibrationRecord_pkey" PRIMARY KEY ("id")
);
CREATE INDEX "MachineCalibrationRecord_organizationId_machineId_idx" ON "MachineCalibrationRecord"("organizationId", "machineId");
