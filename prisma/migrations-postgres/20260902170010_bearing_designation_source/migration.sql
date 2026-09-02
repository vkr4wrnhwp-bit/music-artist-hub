-- How a bearing designation was established, and the photograph it was
-- confirmed against.
--
-- A designation is dimensions, not a label: findBearing turns 6203 into a
-- 17 mm bore and 6208 into a 40 mm one, and the mating analysis reasons about
-- the fit from that. A misread stamp does not produce a wrong caption, it
-- produces the wrong bore -- so where the value came from travels with it.
--
-- Nullable, and existing rows stay null: designations recorded before this
-- column existed were typed or seeded, and marking them either way would be
-- inventing a provenance.
ALTER TABLE "Feature" ADD COLUMN "matingDesignationSource" TEXT;
ALTER TABLE "Feature" ADD COLUMN "matingDesignationPhotoId" TEXT;
