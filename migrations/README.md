# Migrations

Plain SQL, applied in lexical order by `deploy/migrate-prod.sh`. There is no
ledger: every file is guarded (`IF EXISTS` / `IF NOT EXISTS` / `DO` blocks) so
re-running the whole directory is a no-op. `reference/` is documentation and is
never executed.

These bring a database on the Node-era schema onto the schema this service maps.
Without them the `sarkariworld` database 500s on every category endpoint with
`column Article.cover_image_url does not exist`, and its `ArticleCategory` enum
still holds the old five values.

| File | Origin | What |
| --- | --- | --- |
| `0000_preserve_instagram_tags.sql` | this repo | Copy `cover_instagram_url` into `instagram_post_url` before 0003 renames it |
| `0001_add_editor_role.sql` | Node service, verbatim | Add `editor` to `UserRole` |
| `0002_add_hashed_api_key_columns.sql` | Node service, verbatim | Hashed API-key columns + prefix index |
| `0003_rename_cover_image_url.sql` | Node service, verbatim | `cover_instagram_url` → `cover_image_url` |
| `0004_remove_saved_article_status.sql` | Node service, verbatim | Drop `saved` from `ArticleStatus` |
| `0005_align_to_trimmed_schema.sql` | Node service, **adapted** | 11-value `ArticleCategory`, re-bucket `exam`, drop unused columns/tables |
| `0006_clear_non_image_cover_urls.sql` | this repo | Clear `cover_image_url` values that are Instagram links |

## Why 0000 and 0006 exist

0003 renames `cover_instagram_url` to `cover_image_url` on the premise that the
field now holds a hosted cover image. In this database it does not: all nine
populated values are `instagram.com/p/...` post URLs, and eight of them exist
nowhere else. Running 0003 alone would silently convert eight Instagram tags
into broken cover images.

So 0000 copies them into `instagram_post_url` first, and 0006 clears what the
rename leaves behind. Article media is a list of `{ url, title }` used to
cross-promote the Instagram and YouTube channels, which is why it is preserved
rather than repurposed.

## Why 0005 diverges

The original is kept verbatim at `reference/0005_align_to_trimmed_schema.upstream.sql`.
It re-homes both `job` and `exam` to `latest_job`, and its own comment invites
tuning: *"change the CASE below to re-bucket differently"*.

Every Result, Admit Card, Answer Key, Syllabus and Admission article sat in the
legacy `exam` bucket, so the original CASE would have shipped five permanently
empty category pages. This version splits `exam` on title keywords, most
specific first so *"Answer Key Result"* lands in `answer_key` rather than
`result`. Measured against the 687 live rows:

```
latest_job 38 | result 34 | syllabus 15 | admit_card 14 | answer_key 10 | admission 7
```

Re-classifying later is a plain `UPDATE`; nothing is deleted.

## reference/

`schema.prisma` is the Node service's Prisma schema, kept because it was the
DDL source of truth for this database and that repo is being retired. It also
defines the crawler tables this API never reads (`SarkariWebsite`,
`GoogleSearchQuery`, `CrawlRun`, `SearchKeywordGroup`) but sibling apps do —
without it there would be no written definition of them anywhere. It documents;
nothing here runs it.
