-- What the shop can actually print with.
--
-- The additive advisor judges a part against these rows and refuses where they
-- are absent. Tolerance, surface finish and the two tensile figures are all
-- nullable: a printer nobody has measured cannot be compared to a tolerance
-- band, and reporting that gap is the point.
CREATE TABLE "Printer" (
  "id" TEXT NOT NULL PRIMARY KEY,
  "organizationId" TEXT NOT NULL,
  "manufacturer" TEXT NOT NULL,
  "model" TEXT NOT NULL,
  "technology" TEXT NOT NULL,
  "buildX" REAL NOT NULL,
  "buildY" REAL NOT NULL,
  "buildZ" REAL NOT NULL,
  "achievableTolerance" REAL,
  "achievableRa" REAL,
  "minLayerHeight" REAL,
  "nozzleDiameter" REAL,
  "notes" TEXT,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "Printer_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "Printer_organizationId_manufacturer_model_key" ON "Printer"("organizationId", "manufacturer", "model");
CREATE INDEX "Printer_organizationId_idx" ON "Printer"("organizationId");

CREATE TABLE "PrintMaterial" (
  "id" TEXT NOT NULL PRIMARY KEY,
  "organizationId" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "technology" TEXT NOT NULL,
  "tensileXY" REAL,
  "tensileZ" REAL,
  "maxServiceTempF" REAL,
  "creepDataOnFile" BOOLEAN NOT NULL DEFAULT false,
  "densityLbIn3" REAL,
  "costPerPound" REAL,
  "notes" TEXT,
  "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "PrintMaterial_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "Organization" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "PrintMaterial_organizationId_name_key" ON "PrintMaterial"("organizationId", "name");
CREATE INDEX "PrintMaterial_organizationId_idx" ON "PrintMaterial"("organizationId");
