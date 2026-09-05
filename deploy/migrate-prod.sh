#!/usr/bin/env bash
# Bring the `sarkariworld` database up to the schema this FastAPI service maps.
#
# It is currently on the Node-era schema: 5-value ArticleCategory enum,
# cover_instagram_url, no hashed api_key columns -- so every category endpoint
# 500s. This runs the canonical chain from the Node repo, plus two local steps
# that protect the Instagram tags.
#
# Order matters:
#   0000  local   preserve cover_instagram_url into instagram_post_url, and
#                 drop the hand-rolled empty cover_image_url column
#   0001  canon   add 'editor' to UserRole      (must run alone: ALTER TYPE)
#   0002  canon   hashed api_key_* columns
#   0003  canon   rename cover_instagram_url -> cover_image_url
#   0006  local   clear the renamed values that are Instagram URLs, not images
#   0004  canon   drop 'saved' from ArticleStatus
#   0005r local   11-value ArticleCategory + keyword re-bucket of 'exam';
#                 drops views/related_articles and the unused tables
#
# Every step is idempotent, so re-running is safe.
set -euo pipefail

DB="sarkariworld"
CANON="/Users/raushankumar/skw/sarkariworld-api/prisma/sql"
LOCAL="$(cd "$(dirname "$0")/.." && pwd)/migrations"
PSQL=(psql -U root -h localhost -d "$DB" -v ON_ERROR_STOP=1)

echo "==> backing up $DB"
mkdir -p backups
STAMP="$(date +%Y%m%d-%H%M%S)"
pg_dump -U root -h localhost -d "$DB" -Fc -f "backups/$DB-pre-chain-$STAMP.dump"
echo "    backups/$DB-pre-chain-$STAMP.dump"

run() {
  echo "==> $1"
  "${PSQL[@]}" -f "$2"
}

run "0000 preserve instagram tags (local)"        "$LOCAL/0000_preserve_instagram_tags.sql"
run "0001 add editor role"                        "$CANON/0001_add_editor_role.sql"
run "0002 hashed api key columns"                 "$CANON/0002_add_hashed_api_key_columns.sql"
run "0003 rename cover_instagram_url"             "$CANON/0003_rename_cover_image_url.sql"
run "0006 clear non-image cover urls (local)"     "$LOCAL/0006_clear_non_image_cover_urls.sql"
run "0004 remove saved article status"            "$CANON/0004_remove_saved_article_status.sql"
run "0005 align to trimmed schema + re-bucket"    "$LOCAL/0005_align_to_trimmed_schema.rebucket.sql"

echo
echo "==> category distribution"
"${PSQL[@]}" -tAF' | ' -c 'SELECT category::text, count(*) FROM "Article" GROUP BY 1 ORDER BY 2 DESC;'
echo
echo "==> instagram / youtube tags preserved"
"${PSQL[@]}" -tAF' | ' -c "SELECT
  count(*) FILTER (WHERE jsonb_array_length(COALESCE(instagram_post_url,'[]'::jsonb))>0) AS articles_with_instagram,
  count(*) FILTER (WHERE jsonb_array_length(COALESCE(youtube_video_url,'[]'::jsonb))>0)  AS articles_with_youtube,
  count(*) AS total
FROM \"Article\";"
echo
echo "==> done. Now: pm2 restart sarkariworld-api-py"
