#!/usr/bin/env bash
# Apply the SQL migrations in ../migrations to the production database.
#
# Every file is idempotent (guarded with IF EXISTS / IF NOT EXISTS / DO blocks),
# so there is no ledger and re-running is a no-op. Files apply in lexical order,
# which is also the required order:
#
#   0000  preserve cover_instagram_url into instagram_post_url  (before 0003)
#   0001  add 'editor' to UserRole        (alone: ALTER TYPE ... ADD VALUE)
#   0002  hashed api_key_* columns
#   0003  rename cover_instagram_url -> cover_image_url
#   0004  drop 'saved' from ArticleStatus
#   0005  11-value ArticleCategory, re-bucket 'exam', drop unused columns/tables
#   0006  clear cover_image_url values that are Instagram links, not images
#   0007  delete the newsletter-era 'subscription' accounts; default -> google
#
# 0001..0004 came from the Node service verbatim; 0005 is adapted from its
# counterpart (the original is kept at migrations/reference/). 0000, 0006 and
# 0007 are specific to this database. See migrations/README.md.
#
# Override the target with DATABASE: DATABASE=sarkariworld_dev ./deploy/migrate-prod.sh
set -euo pipefail

DB="${DATABASE:-sarkariworld}"
DB_USER="${DATABASE_USER:-root}"
DB_HOST="${DATABASE_HOST:-localhost}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIGRATIONS="$ROOT/migrations"
PSQL=(psql -U "$DB_USER" -h "$DB_HOST" -d "$DB" -v ON_ERROR_STOP=1)

echo "==> backing up $DB"
mkdir -p "$ROOT/backups"
DUMP="$ROOT/backups/$DB-pre-migrate-$(date +%Y%m%d-%H%M%S).dump"
pg_dump -U "$DB_USER" -h "$DB_HOST" -d "$DB" -Fc -f "$DUMP"
echo "    $DUMP"

shopt -s nullglob
for file in "$MIGRATIONS"/[0-9][0-9][0-9][0-9]_*.sql; do
  echo "==> $(basename "$file")"
  "${PSQL[@]}" -f "$file"
done

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
