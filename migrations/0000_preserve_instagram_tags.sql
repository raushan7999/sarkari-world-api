-- Runs before 0003, which renames cover_instagram_url -> cover_image_url and
-- thereby reinterprets its contents as cover images.
--
-- All 9 populated `cover_instagram_url` values are real Instagram post URLs,
-- and 8 of them exist ONLY there -- they are not in the `instagram_post_url`
-- list. Letting 0003 rename the column would silently turn those 8 channel
-- tags into broken cover images. So they are copied into the list first.
--
-- The whole file is guarded on `cover_instagram_url` still existing, which is
-- the same thing as "0003 has not run yet". That guard is not decoration:
--
--   * The UPDATE below cannot even parse once the column has been renamed, so
--     an unguarded re-run aborts the entire chain at the first file.
--   * Step 2 is the dangerous one. `DROP COLUMN IF EXISTS "cover_image_url"`
--     is a no-op today, when that column does not exist yet -- but after 0003
--     has renamed into that name it is the live cover-image column, and a
--     second pass would drop it and every value in it. "IF EXISTS" protects
--     against the column being absent, which is not the failure mode here.
--
-- Inside the guard, the containment check makes the copy itself idempotent.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'Article'
          AND column_name = 'cover_instagram_url'
    ) THEN
        -- 1. Preserve every cover_instagram_url as a proper Instagram tag.
        UPDATE "Article"
        SET "instagram_post_url" =
              COALESCE("instagram_post_url", '[]'::jsonb)
              || jsonb_build_array(
                   jsonb_build_object('url', "cover_instagram_url", 'title', 'Instagram')
                 )
        WHERE "cover_instagram_url" IS NOT NULL
          AND "cover_instagram_url" <> ''
          AND NOT COALESCE("instagram_post_url", '[]'::jsonb)
                  @> jsonb_build_array(jsonb_build_object('url', "cover_instagram_url"));

        -- 2. Drop any pre-existing cover_image_url so 0003's RENAME has a free
        --    target. Verified 0 rows populated before dropping.
        ALTER TABLE "Article" DROP COLUMN IF EXISTS "cover_image_url";
    END IF;
END
$$;
