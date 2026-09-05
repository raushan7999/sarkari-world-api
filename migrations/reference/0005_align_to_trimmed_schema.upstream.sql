-- Align the live DB to the trimmed API schema (unified RBAC; no subscriber,
-- email, notification, announcement or view-tracking surface).
--
-- Preserves all data still used by the API (Article + User rows are kept; the
-- 'job'/'exam' Article rows are RE-HOMED, not deleted). Drops the tables,
-- columns and enums the API no longer references. Every statement is guarded so
-- the file is idempotent and safe to re-run. `_sw_migrations` is intentionally
-- left in place (owned by sibling apps, never touched by this API).

-- 1. ArticleCategory: replace the old {job,scholarship,tender,blog,exam} set with
--    the new 11-value taxonomy. Postgres cannot drop enum values in place, so the
--    type is recreated; legacy 'job' and 'exam' rows are re-homed to 'latest_job'
--    during the cast (change the CASE below to re-bucket differently). Guarded on
--    'job' still being present so the block runs at most once.
DO $$
BEGIN
	IF EXISTS (
		SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
		WHERE t.typname = 'ArticleCategory' AND e.enumlabel = 'job'
	) THEN
		ALTER TABLE "Article" ALTER COLUMN "category" DROP DEFAULT;
		ALTER TYPE "ArticleCategory" RENAME TO "ArticleCategory_old";
		CREATE TYPE "ArticleCategory" AS ENUM (
			'latest_job', 'admit_card', 'result', 'answer_key', 'admission',
			'syllabus', 'scholarship', 'tender', 'sarkari_website',
			'sarkari_mobile_app', 'blog'
		);
		ALTER TABLE "Article"
			ALTER COLUMN "category" TYPE "ArticleCategory"
			USING (
				CASE
					WHEN "category"::text IN ('job', 'exam') THEN 'latest_job'
					ELSE "category"::text
				END
			)::"ArticleCategory";
		ALTER TABLE "Article" ALTER COLUMN "category" SET DEFAULT 'blog';
		DROP TYPE "ArticleCategory_old";
	END IF;
END $$;

-- 2. Article: drop the removed columns (and the partial index on views).
DROP INDEX IF EXISTS "Article_published_views_idx";
ALTER TABLE "Article" DROP COLUMN IF EXISTS "views";
ALTER TABLE "Article" DROP COLUMN IF EXISTS "related_articles";

-- 3. User: drop the subscriber / verification / social columns the API no longer
--    uses. Dropping a column also drops any index or unique constraint on it.
ALTER TABLE "User" DROP COLUMN IF EXISTS "about";
ALTER TABLE "User" DROP COLUMN IF EXISTS "occupation";
ALTER TABLE "User" DROP COLUMN IF EXISTS "instagram";
ALTER TABLE "User" DROP COLUMN IF EXISTS "facebook";
ALTER TABLE "User" DROP COLUMN IF EXISTS "linkedin";
ALTER TABLE "User" DROP COLUMN IF EXISTS "twitter";
ALTER TABLE "User" DROP COLUMN IF EXISTS "is_verified";
ALTER TABLE "User" DROP COLUMN IF EXISTS "verification_token";
ALTER TABLE "User" DROP COLUMN IF EXISTS "verification_token_expires_at";
ALTER TABLE "User" DROP COLUMN IF EXISTS "verification_sends";
ALTER TABLE "User" DROP COLUMN IF EXISTS "welcome_email_sent_at";
ALTER TABLE "User" DROP COLUMN IF EXISTS "subscribed_at";
ALTER TABLE "User" DROP COLUMN IF EXISTS "is_active";
ALTER TABLE "User" DROP COLUMN IF EXISTS "unsubscribed_at";
ALTER TABLE "User" DROP COLUMN IF EXISTS "unsubscribe_token";

-- 4. Drop the tables the API no longer serves.
DROP TABLE IF EXISTS "DailyViewSnapshot" CASCADE;
DROP TABLE IF EXISTS "ViewSnapshot" CASCADE;
DROP TABLE IF EXISTS "Notification" CASCADE;
DROP TABLE IF EXISTS "Announcement" CASCADE;
DROP TABLE IF EXISTS "EmailLog" CASCADE;

-- 5. Drop the now-unreferenced enums (CrawlRunStatus is still used by CrawlRun).
DROP TYPE IF EXISTS "EmailMode";
DROP TYPE IF EXISTS "EmailLogStatus";
