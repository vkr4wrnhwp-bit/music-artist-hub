-- CreateTable
CREATE TABLE "JawSet" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "profile" TEXT NOT NULL,
    "nominalSize" REAL NOT NULL,
    "nominalLength" REAL,
    "stepDepth" REAL NOT NULL,
    "jawHeight" REAL NOT NULL,
    "material" TEXT NOT NULL,
    "viseDescription" TEXT NOT NULL,
    "timesUsed" INTEGER NOT NULL DEFAULT 0,
    "minutesToCut" REAL NOT NULL DEFAULT 35,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "JawSet_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE INDEX "JawSet_organizationId_idx" ON "JawSet"("organizationId");
