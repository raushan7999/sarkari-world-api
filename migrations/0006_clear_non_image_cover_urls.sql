-- Run AFTER canonical 0003. That migration renames cover_instagram_url ->
-- cover_image_url on the premise that the field now holds a hosted cover
-- image. In this database it does not -- every populated value is an
-- instagram.com post URL, already preserved into `instagram_post_url` by
-- 0000. Left in place they would render as broken <img> covers, so the
-- non-image values are cleared. Idempotent.
UPDATE "Article"
SET "cover_image_url" = NULL
WHERE "cover_image_url" ~* 'instagram\.com';
