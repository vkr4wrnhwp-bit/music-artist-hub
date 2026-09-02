-- Bind a turned part's approval to the state that was approved.
--
-- Nullable with no default. Existing rows are not backfilled with a digest of
-- their current state: that would convert an approval nobody can identify into
-- one that reads as current, which is the exact failure this column prevents.
-- A null digest reads as STALE.
ALTER TABLE "RotationalPart" ADD COLUMN "approvedDigest" TEXT;
