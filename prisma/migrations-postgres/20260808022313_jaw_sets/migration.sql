-- CreateTable
CREATE TABLE "JawSet" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "profile" TEXT NOT NULL,
    "nominalSize" DOUBLE PRECISION NOT NULL,
    "nominalLength" DOUBLE PRECISION,
    "stepDepth" DOUBLE PRECISION NOT NULL,
    "jawHeight" DOUBLE PRECISION NOT NULL,
    "material" TEXT NOT NULL,
    "viseDescription" TEXT NOT NULL,
    "timesUsed" INTEGER NOT NULL DEFAULT 0,
    "minutesToCut" DOUBLE PRECISION NOT NULL DEFAULT 35,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "JawSet_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "JawSet_organizationId_idx" ON "JawSet"("organizationId");

-- AddForeignKey
ALTER TABLE "JawSet" ADD CONSTRAINT "JawSet_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization"("id") ON DELETE CASCADE ON UPDATE CASCADE;
