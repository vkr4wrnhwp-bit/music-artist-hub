-- Control software version, as it reads on the machine.
--
-- Part of the identity of what a post validation proved: a control update can
-- change how a canned cycle retracts or how look-ahead handles short blocks.
-- Nullable, no default — a proof cannot be matched against a version nobody
-- wrote down, and inventing one would let a stale proof stand.
ALTER TABLE "Machine" ADD COLUMN "controlVersion" TEXT;
