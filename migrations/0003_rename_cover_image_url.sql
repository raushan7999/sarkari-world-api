-- Rename Article.cover_instagram_url -> cover_image_url (preserves existing data).
-- The field now holds a server-hosted cover image URL, not an Instagram embed.
-- Idempotent: only renames if the old column still exists.
DO $$
BEGIN
	IF EXISTS (
		SELECT 1 FROM information_schema.columns
		WHERE table_name = 'Article' AND column_name = 'cover_instagram_url'
	) THEN
		ALTER TABLE "Article" RENAME COLUMN "cover_instagram_url" TO "cover_image_url";
	END IF;
END $$;
