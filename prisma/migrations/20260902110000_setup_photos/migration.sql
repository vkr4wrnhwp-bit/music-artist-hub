-- A photograph of how a setup was actually built, pinned to that setup.
-- SET NULL rather than CASCADE: re-planning a setup must not destroy the
-- record of how the job was held. The photo keeps its partId.
ALTER TABLE "UploadedAsset" ADD COLUMN "setupId" TEXT REFERENCES "Setup"("id") ON DELETE SET NULL ON UPDATE CASCADE;
CREATE INDEX "UploadedAsset_setupId_idx" ON "UploadedAsset"("setupId");
