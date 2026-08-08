-- AlterTable
ALTER TABLE "Setup" ADD COLUMN     "clampForce" DOUBLE PRECISION,
ADD COLUMN     "hasPositiveStop" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "jawSurface" TEXT,
ADD COLUMN     "loadDirection" TEXT;

-- AlterTable
ALTER TABLE "Tool" ADD COLUMN     "actualStickout" DOUBLE PRECISION,
ADD COLUMN     "condition" TEXT NOT NULL DEFAULT 'UNKNOWN',
ADD COLUMN     "helixAngle" DOUBLE PRECISION,
ADD COLUMN     "lastUsedAt" TIMESTAMP(3),
ADD COLUMN     "measuredRunout" DOUBLE PRECISION,
ADD COLUMN     "previousMaterial" TEXT,
ADD COLUMN     "regrindCount" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "shopNotes" TEXT;

-- CreateTable
CREATE TABLE "OperationState" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "setupId" TEXT,
    "sequence" INTEGER NOT NULL,
    "kind" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "envelopeX" DOUBLE PRECISION,
    "envelopeY" DOUBLE PRECISION,
    "envelopeZ" DOUBLE PRECISION,
    "remainingVolume" DOUBLE PRECISION,
    "removedVolume" DOUBLE PRECISION,
    "minWallThickness" DOUBLE PRECISION,
    "clampingSurfacesIntact" BOOLEAN NOT NULL DEFAULT true,
    "derivedGeometryJson" TEXT,
    "source" TEXT NOT NULL DEFAULT 'CALCULATED',
    "confidence" TEXT NOT NULL DEFAULT 'LOW',
    "notes" TEXT,

    CONSTRAINT "OperationState_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ShopKnowledge" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "machineId" TEXT,
    "toolId" TEXT,
    "materialId" TEXT,
    "toolClass" TEXT,
    "toolDiameter" DOUBLE PRECISION,
    "category" TEXT NOT NULL,
    "observation" TEXT NOT NULL,
    "parameter" TEXT,
    "thresholdValue" DOUBLE PRECISION,
    "thresholdUnit" TEXT,
    "direction" TEXT,
    "origin" TEXT NOT NULL DEFAULT 'OPERATOR',
    "jobCount" INTEGER NOT NULL DEFAULT 1,
    "lastObservedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "recordedById" TEXT,
    "confidence" TEXT NOT NULL DEFAULT 'LOW',
    "active" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ShopKnowledge_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Disagreement" (
    "id" TEXT NOT NULL,
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
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Disagreement_pkey" PRIMARY KEY ("id")
);

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

-- AddForeignKey
ALTER TABLE "OperationState" ADD CONSTRAINT "OperationState_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ShopKnowledge" ADD CONSTRAINT "ShopKnowledge_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ShopKnowledge" ADD CONSTRAINT "ShopKnowledge_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ShopKnowledge" ADD CONSTRAINT "ShopKnowledge_toolId_fkey" FOREIGN KEY ("toolId") REFERENCES "Tool"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ShopKnowledge" ADD CONSTRAINT "ShopKnowledge_materialId_fkey" FOREIGN KEY ("materialId") REFERENCES "Material"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ShopKnowledge" ADD CONSTRAINT "ShopKnowledge_recordedById_fkey" FOREIGN KEY ("recordedById") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Disagreement" ADD CONSTRAINT "Disagreement_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Disagreement" ADD CONSTRAINT "Disagreement_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Disagreement" ADD CONSTRAINT "Disagreement_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Disagreement" ADD CONSTRAINT "Disagreement_comparableJobId_fkey" FOREIGN KEY ("comparableJobId") REFERENCES "Job"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Disagreement" ADD CONSTRAINT "Disagreement_shopKnowledgeId_fkey" FOREIGN KEY ("shopKnowledgeId") REFERENCES "ShopKnowledge"("id") ON DELETE SET NULL ON UPDATE CASCADE;
