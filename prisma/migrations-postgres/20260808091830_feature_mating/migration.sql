-- AlterTable
ALTER TABLE "Feature" ADD COLUMN     "fitClass" TEXT,
ADD COLUMN     "interfaceSide" TEXT,
ADD COLUMN     "matingComponent" TEXT,
ADD COLUMN     "matingDesignation" TEXT,
ADD COLUMN     "rotatingUnderLoad" BOOLEAN NOT NULL DEFAULT false;
