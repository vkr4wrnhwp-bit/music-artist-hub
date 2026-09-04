-- Roughing or finishing, as a property of the operation.
--
-- stockToLeave was the only thing distinguishing them, which made a finish
-- pass a roughing pass with a different number in it: same mid-range chipload,
-- same stepdown, same depth ladder. Roughing feeds on the final wall.
--
-- Nullable with no default. Absent means ROUGH, which is what every existing
-- operation is; backfilling FINISH anywhere would change what an approved plan
-- cuts without anybody asking for it.
ALTER TABLE "Operation" ADD COLUMN "pass" TEXT;
