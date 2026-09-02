-- What arrived, before anything tried to read it. NULL means the file did not
-- say, which for controllerFamily is not the same as an unknown controller.
ALTER TABLE "NCProgram" ADD COLUMN "sourceEncoding" TEXT;
ALTER TABLE "NCProgram" ADD COLUMN "lineEnding" TEXT;
ALTER TABLE "NCProgram" ADD COLUMN "controllerFamily" TEXT;
