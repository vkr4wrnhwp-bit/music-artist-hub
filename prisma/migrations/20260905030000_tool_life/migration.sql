-- What this tool has actually done.
--
-- `lifeRemaining` was a 0-1 float, required on the tool form and shown on the
-- tools page as a colour-coded percentage -- and nothing in the system ever
-- changed it. It was whatever somebody typed when they added the tool,
-- presented as a live gauge, and a machinist reading "100%" in green
-- reasonably concluded the tool had life left. It is kept so no shop's data is
-- thrown away, and read by nothing.
--
-- These accumulate when a job is marked COMPLETE, from the cutting time the
-- toolpaths charge to this tool times the quantity made. They are a LOWER
-- BOUND and the UI says so: a job run without being recorded, or a tool
-- borrowed for another part, is time this never saw.
--
-- lifeCountedFrom is when the count started -- a new tool, or the regrind that
-- gave it a fresh edge. Null means nobody has said.
ALTER TABLE "Tool" ADD COLUMN "minutesUsed" REAL NOT NULL DEFAULT 0;
ALTER TABLE "Tool" ADD COLUMN "partsCut" INTEGER NOT NULL DEFAULT 0;
ALTER TABLE "Tool" ADD COLUMN "lifeCountedFrom" DATETIME;
