-- Retire the newsletter-era accounts.
--
-- `User.auth_provider` records how an account came to exist, and the old Node
-- service wrote "subscription" when someone signed up for the newsletter.
-- This API has no such path: `upsert_oauth_user` is the only writer and it
-- always stamps "google". The code has said so for a while — AUTH_PROVIDERS
-- is ("google",), /admin/meta advertises google alone, and the integration
-- suite asserts no other provider survives — but the rows themselves were
-- never cleaned up, so 109 of them still appeared in the admin user list.
--
-- They are inert. None carries a google_id, so none can ever be signed in to:
-- sign-in links by google_id and there is no password path. None has ever
-- logged in, none holds a bookmark, none authored an article, and no address
-- among them collides with a real account. Nothing references "User" by
-- foreign key.
--
-- The addresses were exported to backups/subscription-users-*.csv first, so
-- this drops the accounts, not the record of who subscribed.

BEGIN;

-- Defensive by design: every predicate below was verified to hold for all 109
-- rows before writing this. If one of them stops holding on some other copy
-- of the database, the statement quietly matches fewer rows rather than
-- destroying something live.
DELETE FROM "User"
WHERE "auth_provider" = 'subscription'
  AND "google_id" IS NULL
  AND "last_login_at" IS NULL
  AND "api_key_hash" IS NULL
  AND "role" = 'user'
  AND "id" NOT IN (SELECT DISTINCT "user_id" FROM "Bookmark")
  AND "id"::text NOT IN (
        SELECT DISTINCT "author_id" FROM "Article" WHERE "author_id" IS NOT NULL
      );

-- The column default was still "subscription", inherited from the Prisma
-- schema. Every row this service writes sets the value explicitly, so the
-- default was only ever a trap waiting for a hand-written INSERT.
ALTER TABLE "User" ALTER COLUMN "auth_provider" SET DEFAULT 'google';

COMMIT;
