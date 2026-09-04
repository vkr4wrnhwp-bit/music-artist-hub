-- Has this program ever cut a good part?
--
-- The most important property an NC program has, and nothing recorded it: a
-- program proven on the machine last Tuesday and the same program never run
-- were indistinguishable, and no machinist treats them the same.
--
-- provenDigest is the SHA-256 of the code as it was when somebody watched it
-- cut. Re-post and the digest stops matching, so the proof reads as stale
-- rather than vouching for text nobody has run.
--
-- All nullable, no defaults, existing rows untouched. Backfilling any value
-- would mark every program in the database as proven.
ALTER TABLE "NCProgram" ADD COLUMN "provenAt" DATETIME;
ALTER TABLE "NCProgram" ADD COLUMN "provenByName" TEXT;
ALTER TABLE "NCProgram" ADD COLUMN "provenMachineId" TEXT;
ALTER TABLE "NCProgram" ADD COLUMN "provenNote" TEXT;
ALTER TABLE "NCProgram" ADD COLUMN "provenDigest" TEXT;
