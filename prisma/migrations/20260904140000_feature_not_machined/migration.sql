-- Not made by this program.
--
-- A sentence from a person saying this feature is not cut by the plan: a
-- fillet the CAM engine has no operation for, a chamfer broken at the bench, a
-- bore the extrusion already carries, a vendor operation.
--
-- Nullable with no default and existing rows are left alone. Backfilling any
-- value here would account for every feature already in the database and clear
-- the coverage gate on parts nobody has looked at, which is the exact thing the
-- gate exists to catch.
ALTER TABLE "Feature" ADD COLUMN "notMachinedReason" TEXT;
ALTER TABLE "Feature" ADD COLUMN "notMachinedBy" TEXT;
ALTER TABLE "Feature" ADD COLUMN "notMachinedAt" DATETIME;
