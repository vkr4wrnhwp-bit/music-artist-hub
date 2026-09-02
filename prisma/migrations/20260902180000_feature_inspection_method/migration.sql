-- How a feature will be verified, and who decided.
--
-- All three columns are nullable with no default and existing rows are left
-- alone. Backfilling a method would silently satisfy the "Critical tolerance
-- strategy" gate for every feature already in the database, which is the exact
-- thing the gate exists to prevent.
ALTER TABLE "Feature" ADD COLUMN "inspectionDeviceType" TEXT;
ALTER TABLE "Feature" ADD COLUMN "inspectionMethodBy" TEXT;
ALTER TABLE "Feature" ADD COLUMN "inspectionMethodAt" DATETIME;
