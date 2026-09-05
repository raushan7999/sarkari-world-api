-- Run BEFORE canonical 0003 (which renames cover_instagram_url ->
-- cover_image_url and thereby reinterprets its contents as cover images).
--
-- All 9 populated `cover_instagram_url` values are real Instagram post URLs,
-- and 8 of them exist ONLY there -- they are not in the `instagram_post_url`
-- list. Letting 0003 rename the column would silently turn those 8 channel
-- tags into broken cover images. So they are copied into the list first.
--
-- Idempotent: the containment check skips URLs already in the list.

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

-- 2. Undo the hand-rolled column so 0003's RENAME has a free target name.
--    Verified 0 rows populated before dropping.
ALTER TABLE "Article" DROP COLUMN IF EXISTS "cover_image_url";
