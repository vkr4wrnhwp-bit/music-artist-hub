-- CreateTable
CREATE TABLE "GuideEvent" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "flowId" TEXT NOT NULL,
    "stepId" TEXT,
    "action" TEXT NOT NULL,
    "detail" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "GuideEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "GuideEvent_organizationId_flowId_idx" ON "GuideEvent"("organizationId", "flowId");
