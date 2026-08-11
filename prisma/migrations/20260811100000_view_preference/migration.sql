-- CreateTable
CREATE TABLE "ViewPreference" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "envJson" TEXT NOT NULL,
    "savedPresetsJson" TEXT NOT NULL DEFAULT '[]',
    "updatedAt" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE UNIQUE INDEX "ViewPreference_userId_key" ON "ViewPreference"("userId");
CREATE INDEX "ViewPreference_organizationId_idx" ON "ViewPreference"("organizationId");
