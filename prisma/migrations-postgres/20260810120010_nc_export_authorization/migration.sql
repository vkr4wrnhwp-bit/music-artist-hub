-- CreateTable
CREATE TABLE "NCExportAuthorization" (
    "id" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "ncProgramId" TEXT NOT NULL,
    "partRevisionId" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "byteLength" INTEGER NOT NULL,
    "digest" TEXT NOT NULL,
    "issuedToUserId" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "consumedAt" TIMESTAMP(3),
    "outcome" TEXT,
    "destinationName" TEXT,
    "writtenFilename" TEXT,
    "clientDigest" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "NCExportAuthorization_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "NCExportAuthorization_token_key" ON "NCExportAuthorization"("token");

-- CreateIndex
CREATE INDEX "NCExportAuthorization_ncProgramId_idx" ON "NCExportAuthorization"("ncProgramId");

-- CreateIndex
CREATE INDEX "NCExportAuthorization_organizationId_idx" ON "NCExportAuthorization"("organizationId");

-- AddForeignKey
ALTER TABLE "NCExportAuthorization" ADD CONSTRAINT "NCExportAuthorization_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "NCExportAuthorization" ADD CONSTRAINT "NCExportAuthorization_ncProgramId_fkey" FOREIGN KEY ("ncProgramId") REFERENCES "NCProgram"("id") ON DELETE CASCADE ON UPDATE CASCADE;
