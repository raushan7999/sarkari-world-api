-- Additive adaptation of the live sarkariworld_dev database (step 1 of 2).
-- Adds the `editor` UserRole value. Run separately: Postgres cannot ADD an enum
-- value inside a multi-statement transaction batch.
ALTER TYPE "UserRole" ADD VALUE IF NOT EXISTS 'editor';
