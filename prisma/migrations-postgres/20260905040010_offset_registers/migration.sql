-- The offset registers this shop actually uses.
--
-- H is the length offset the program calls, D the diameter offset. Both were
-- assumed equal to the tool number everywhere -- printed in the program header
-- and on the setup sheet as though CANVAS knew what was in the control's
-- offset table. It usually is the tool number, and a wrong H is the single most
-- consequential wrong number in a program: the tool goes to the wrong Z.
--
-- Null means nobody recorded it, and then the post says ASSUMED.
ALTER TABLE "Tool" ADD COLUMN "lengthOffset" INTEGER;
ALTER TABLE "Tool" ADD COLUMN "diameterOffset" INTEGER;
