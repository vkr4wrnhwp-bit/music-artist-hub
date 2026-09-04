-- A post, proven on a named machine.
--
-- PostDefinition.certified is typed as the literal false and stays that way:
-- certification is not a property of the code. It is a property of a post having
-- been run on a specific machine, against a specific control software version,
-- by a named person who watched what happened.
--
-- Scoped tightly. A post proven on one machine says nothing about the one next
-- to it, and a control software update can change how a canned cycle behaves —
-- so the control version is part of the identity of what was proven.
CREATE TABLE "PostValidation" (
  "id" TEXT NOT NULL PRIMARY KEY,
  "organizationId" TEXT NOT NULL,
  "postId" TEXT NOT NULL,
  "machineId" TEXT NOT NULL,
  "controlVersion" TEXT NOT NULL,
  "validatedByName" TEXT NOT NULL,
  "validatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "evidence" TEXT NOT NULL,
  "revokedAt" DATETIME,
  "revokedReason" TEXT,
  CONSTRAINT "PostValidation_machineId_fkey" FOREIGN KEY ("machineId") REFERENCES "Machine" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX "PostValidation_organizationId_postId_machineId_idx" ON "PostValidation"("organizationId", "postId", "machineId");
