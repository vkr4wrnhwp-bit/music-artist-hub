-- Tool carousel: where a tool physically sits.
--
-- Both columns are nullable because "in the crib" is the honest state for
-- most tools and is not the same as pocket zero. Postgres also treats NULLs
-- as distinct in a unique index, so any number of unassigned tools coexist
-- while two tools can never claim one pocket of one machine.
ALTER TABLE "Tool" ADD COLUMN "machineId" TEXT;
ALTER TABLE "Tool" ADD COLUMN "pocket" INTEGER;

ALTER TABLE "Tool" ADD CONSTRAINT "Tool_machineId_fkey"
  FOREIGN KEY ("machineId") REFERENCES "Machine"("id") ON DELETE SET NULL ON UPDATE CASCADE;

CREATE UNIQUE INDEX "Tool_machineId_pocket_key" ON "Tool"("machineId", "pocket");
CREATE INDEX "Tool_machineId_idx" ON "Tool"("machineId");
