-- Remove the unused `saved` value from the ArticleStatus enum.
-- Postgres cannot DROP a value from an enum in place, so the type is recreated.
-- Existing rows in 'saved' are re-homed to 'draft' first. The three partial
-- indexes whose predicate references the enum are dropped and rebuilt around the
-- type swap (their predicates reference 'published', which survives).
-- Idempotent: the whole block is skipped once 'saved' is gone from the type.
DO $$
BEGIN
	IF EXISTS (
		SELECT 1
		FROM pg_enum e
		JOIN pg_type t ON t.oid = e.enumtypid
		WHERE t.typname = 'ArticleStatus' AND e.enumlabel = 'saved'
	) THEN
		-- 1. Re-home any existing data off the value being removed.
		UPDATE "Article" SET "article_status" = 'draft' WHERE "article_status" = 'saved';

		-- 2. Drop the partial indexes that reference the enum type.
		DROP INDEX IF EXISTS "Article_published_created_at_idx";
		DROP INDEX IF EXISTS "Article_published_views_idx";
		DROP INDEX IF EXISTS "Article_status_category_created_at_idx";

		-- 3. Swap the enum type (the only way to remove a value).
		ALTER TABLE "Article" ALTER COLUMN "article_status" DROP DEFAULT;
		ALTER TYPE "ArticleStatus" RENAME TO "ArticleStatus_old";
		CREATE TYPE "ArticleStatus" AS ENUM ('draft', 'published', 'archived');
		ALTER TABLE "Article"
			ALTER COLUMN "article_status" TYPE "ArticleStatus"
			USING "article_status"::text::"ArticleStatus";
		ALTER TABLE "Article" ALTER COLUMN "article_status" SET DEFAULT 'draft';
		DROP TYPE "ArticleStatus_old";

		-- 4. Rebuild the partial indexes against the new type.
		CREATE INDEX "Article_published_created_at_idx"
			ON "Article" ("created_at" DESC)
			WHERE (article_status = 'published'::"ArticleStatus");
		CREATE INDEX "Article_published_views_idx"
			ON "Article" ("views" DESC, "created_at" DESC)
			WHERE ((article_status = 'published'::"ArticleStatus") AND (views > 0));
		CREATE INDEX "Article_status_category_created_at_idx"
			ON "Article" ("category", "created_at" DESC)
			WHERE (article_status = 'published'::"ArticleStatus");
	END IF;
END $$;
