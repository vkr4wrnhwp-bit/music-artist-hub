-- AlterTable
ALTER TABLE "Measurement" ADD COLUMN     "datumId" TEXT;

-- CreateTable
CREATE TABLE "Datum" (
    "id" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "letter" TEXT NOT NULL,
    "system" TEXT NOT NULL,
    "featureId" TEXT,
    "description" TEXT NOT NULL,
    "geometryType" TEXT NOT NULL DEFAULT 'PLANE',
    "proposedReason" TEXT,
    "acceptedByUser" BOOLEAN NOT NULL DEFAULT false,
    "acceptedAt" TIMESTAMP(3),
    "source" TEXT NOT NULL DEFAULT 'SYSTEM',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Datum_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Datum_partRevisionId_idx" ON "Datum"("partRevisionId");

-- CreateIndex
CREATE UNIQUE INDEX "Datum_partRevisionId_system_letter_key" ON "Datum"("partRevisionId", "system", "letter");

-- AddForeignKey
ALTER TABLE "Datum" ADD CONSTRAINT "Datum_partRevisionId_fkey" FOREIGN KEY ("partRevisionId") REFERENCES "PartRevision"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Datum" ADD CONSTRAINT "Datum_featureId_fkey" FOREIGN KEY ("featureId") REFERENCES "Feature"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Measurement" ADD CONSTRAINT "Measurement_datumId_fkey" FOREIGN KEY ("datumId") REFERENCES "Datum"("id") ON DELETE SET NULL ON UPDATE CASCADE;
