-- Two pieces of leftover state from the Node service.
--
-- 1. `User.api_key` held API-key secrets in plaintext. This service replaced
--    that with `api_key_prefix` + a bcrypt `api_key_hash` (migration 0002),
--    and the column has been mapped-but-never-read since — `resolve_api_key`
--    matches on prefix and hash only, so a value here authenticates nothing.
--    One row still carries a 46-character `sw_` secret whose hashed
--    counterpart was never created, which makes it dead as a credential and
--    pure liability as stored data. Clearing the value keeps the column (the
--    model still maps it) without keeping the secret.
--
--    Anyone who was relying on that key already cannot use it. Issue a fresh
--    one from the console: Users -> the key cell.
--
-- 2. Bookmarks pointing at rows that no longer exist. There are no foreign
--    keys on this schema, so deleting a user or an article leaves its
--    bookmarks behind. The API already tolerates this — a bookmark whose
--    article has gone serialises with `article: null` — but the admin
--    analytics count those rows, so totals and "top users" are inflated by
--    engagement that cannot be attributed to anything.

BEGIN;

UPDATE "User" SET "api_key" = NULL WHERE "api_key" IS NOT NULL;

DELETE FROM "Bookmark" b
WHERE NOT EXISTS (SELECT 1 FROM "User" u WHERE u."id" = b."user_id")
   OR NOT EXISTS (SELECT 1 FROM "Article" a WHERE a."id" = b."article_id");

COMMIT;
