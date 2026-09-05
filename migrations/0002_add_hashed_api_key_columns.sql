-- Additive adaptation of the live sarkariworld_dev database (step 2 of 2).
-- Adds the hashed API-key credential columns alongside the legacy plaintext
-- `api_key` column. All additive and idempotent; existing rows/apps unaffected.
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "api_key_prefix" TEXT;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "api_key_hash" TEXT;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "api_key_name" TEXT;
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "api_key_created_at" TIMESTAMP(3);
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "api_key_last_used_at" TIMESTAMP(3);
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "api_key_revoked_at" TIMESTAMP(3);
CREATE UNIQUE INDEX IF NOT EXISTS "User_api_key_prefix_key" ON "User"("api_key_prefix");
