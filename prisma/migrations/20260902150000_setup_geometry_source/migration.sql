-- Where a setup's geometry came from.
--
-- PLANNED is the approach generator's intent; MEASURED is what a machinist
-- actually set at the machine. The holding-margin arithmetic is identical
-- either way and the claim it supports is not: a margin computed from a
-- planned grip describes a setup nobody has built yet.
--
-- Nullable with no default, and deliberately NOT backfilled to PLANNED for
-- existing rows: those setups were written before anything recorded this, and
-- inventing a provenance for them would be exactly the fabrication the column
-- exists to prevent.
ALTER TABLE "Setup" ADD COLUMN "geometrySource" TEXT;
ALTER TABLE "Setup" ADD COLUMN "geometryRecordedBy" TEXT;
ALTER TABLE "Setup" ADD COLUMN "geometryRecordedAt" DATETIME;
