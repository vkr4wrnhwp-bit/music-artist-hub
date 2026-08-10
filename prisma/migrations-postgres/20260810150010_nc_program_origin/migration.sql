-- AlterTable
ALTER TABLE "NCProgram" ADD COLUMN "origin" TEXT NOT NULL DEFAULT 'GENERATED';
ALTER TABLE "NCProgram" ADD COLUMN "sourceProgramId" TEXT;
ALTER TABLE "NCProgram" ADD COLUMN "optimizationAuditJson" TEXT;
