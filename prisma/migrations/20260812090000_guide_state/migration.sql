-- AlterTable
ALTER TABLE "Part" ADD COLUMN "training" BOOLEAN NOT NULL DEFAULT false;

-- CreateTable
CREATE TABLE "GuideState" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "mode" TEXT NOT NULL DEFAULT 'ASSIST',
    "profile" TEXT,
    "sessionsJson" TEXT NOT NULL DEFAULT '{}',
    "updatedAt" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE UNIQUE INDEX "GuideState_userId_key" ON "GuideState"("userId");
CREATE INDEX "GuideState_organizationId_idx" ON "GuideState"("organizationId");
