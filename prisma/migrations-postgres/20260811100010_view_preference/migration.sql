-- CreateTable
CREATE TABLE "ViewPreference" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "envJson" TEXT NOT NULL,
    "savedPresetsJson" TEXT NOT NULL DEFAULT '[]',
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ViewPreference_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "ViewPreference_userId_key" ON "ViewPreference"("userId");
CREATE INDEX "ViewPreference_organizationId_idx" ON "ViewPreference"("organizationId");
