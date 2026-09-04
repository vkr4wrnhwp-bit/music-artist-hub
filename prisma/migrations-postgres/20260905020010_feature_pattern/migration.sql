-- One statement on a drawing, N features on a part.
--
-- A bolt circle is expanded into the real features it describes, because
-- everything downstream of the feature list is per feature: coverage asks
-- whether each one is cut, inspection assigns each one a method, measurement
-- records a reading against each one. A virtual pattern would have to be
-- unfolded at every one of those points, and the first place it was not
-- unfolded would be a hole nobody checked.
--
-- The drawing's statement travels with the instances so the group stays visible
-- and editable as a group. Six coordinates are a consequence; "6 on a 3.000
-- bolt circle" is what the drawing actually says.
ALTER TABLE "Feature" ADD COLUMN "patternId" TEXT;
ALTER TABLE "Feature" ADD COLUMN "patternIndex" INTEGER;
ALTER TABLE "Feature" ADD COLUMN "patternJson" TEXT;
