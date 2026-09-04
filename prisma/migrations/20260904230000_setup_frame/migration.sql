-- Where program zero is, and which way the part is turned.
--
-- `orientation` says which face is up and cannot say which way the part was
-- turned to get it there: rolled about X mirrors every Y, pitched about Y
-- mirrors every X, and both read "BOTTOM". Two different parts, and no way to
-- tell them apart from the string — so the axis is recorded, and a BOTTOM setup
-- without one is refused rather than guessed at.
--
-- quarterTurns indexes the part about Z in 90 degree steps, which is what a
-- vise does. originX/originY move program zero off the stock centre.
--
-- All nullable, all meaning the convention the system already ran on: zero at
-- the centre of the stock, no index, the part the way up it was modelled.
-- Nothing planned before these columns existed changes.
ALTER TABLE "Setup" ADD COLUMN "flipAxis" TEXT;
ALTER TABLE "Setup" ADD COLUMN "quarterTurns" INTEGER;
ALTER TABLE "Setup" ADD COLUMN "originX" REAL;
ALTER TABLE "Setup" ADD COLUMN "originY" REAL;
