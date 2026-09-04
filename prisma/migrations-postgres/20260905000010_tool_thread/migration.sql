-- What thread this tool cuts, for a tap or a thread mill.
--
-- A 1/4-20 tap and a 1/4-28 tap are both 0.250 diameter, so matching a tap to a
-- hole by diameter puts a 28-pitch tap into a hole drilled for 20 and snaps it
-- off in the part -- the most expensive thing that happens to a small hole. The
-- tool carries its own designation and the match is on the thread.
--
-- Nullable: most of the crib does not cut threads, and a tap without a
-- designation is refused rather than matched on its size.
ALTER TABLE "Tool" ADD COLUMN "threadDesignation" TEXT;
