-- The tool's point.
--
-- pointAngle is the INCLUDED angle at the point in degrees, as the catalogue
-- states it: 90 for a 90° chamfer mill, 118 for a jobber drill. tipDiameter is
-- the flat ground on the end.
--
-- A chamfer's angle is a property of the tool that cuts it. A 90° chamfer mill
-- has a 45° flank and cuts 45° chamfers; it cannot cut a 30° chamfer at any
-- depth or offset. Both columns are nullable with no default, because the
-- alternative is inventing the geometry of a cone the shop owns — and the
-- chamfer engine refuses the operation and says which field is missing rather
-- than cutting a chamfer of a size nobody asked for.
ALTER TABLE "Tool" ADD COLUMN "pointAngle" DOUBLE PRECISION;
ALTER TABLE "Tool" ADD COLUMN "tipDiameter" DOUBLE PRECISION;
