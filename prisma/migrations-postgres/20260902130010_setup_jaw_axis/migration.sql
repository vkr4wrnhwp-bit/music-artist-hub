-- Which axis the vise jaws close on, in part coordinates.
--
-- Nullable with no default on purpose. This is the datum that decides where
-- the fixture is; defaulting it would place a modelled vise on the wrong two
-- faces and produce a collision check that clears the setup that would
-- actually crash. Null means the fixture is not modelled, and the checks that
-- need it say they did not run.
ALTER TABLE "Setup" ADD COLUMN "jawAxis" TEXT;
