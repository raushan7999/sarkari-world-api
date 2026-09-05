"""Article domain constants. Mirrors the Node service's `src/constants.js`."""

# Public API category slugs, in display order. Hyphenated; the DB enum uses
# underscores.
CATEGORY_SLUGS: tuple[str, ...] = (
    "latest-job",
    "admit-card",
    "result",
    "answer-key",
    "admission",
    "syllabus",
    "scholarship",
    "tender",
    "sarkari-website",
    "sarkari-mobile-app",
    "blog",
)

CATEGORY_LABELS: dict[str, str] = {
    "latest-job": "Latest Job",
    "admit-card": "Admit Card",
    "result": "Result",
    "answer-key": "Answer Key",
    "admission": "Admission",
    "syllabus": "Syllabus",
    "scholarship": "Scholarship",
    "tender": "Tender",
    "sarkari-website": "Sarkari Website",
    "sarkari-mobile-app": "Sarkari Mobile App",
    "blog": "Blog",
}

# Pagination
PUBLIC_PAGE_SIZE = 15
PUBLIC_PAGE_SIZE_MAX = 50
ADMIN_PAGE_SIZE = 24
ADMIN_PAGE_SIZE_MAX = 100
MAX_LIST_PAGE = 1000
# Ceiling on `GET /v1/sitemap`. The sitemaps protocol allows 50,000 URLs per
# file, so a client that reaches this needs a sitemap index rather than a
# bigger response; the endpoint reports `truncated` so it can tell.
SITEMAP_MAX_ROWS = 50_000

# Input caps, enforced by both the Pydantic schemas and the payload normalisers.
SEARCH_QUERY_MIN = 2
SEARCH_QUERY_MAX = 100
SEARCH_RESULT_MAX = 250
TITLE_MAX = 220
DESCRIPTION_MAX = 2000
HTML_CONTENT_MAX = 500_000
SLUG_MAX = 200
META_TITLE_MAX = 60
META_DESCRIPTION_MAX = 160
COVER_IMAGE_URL_MAX = 2048
FAQ_MAX_ITEMS = 30
FAQ_QUESTION_MAX = 300
FAQ_ANSWER_MAX = 1500
LINKS_MAX = 24
LINK_CTA_MAX = 60
LINK_URL_MAX = 2048
URL_TITLE_LIST_MAX = 20
URL_TITLE_TITLE_MAX = 200
SEARCH_KEYWORD_MAX_ITEMS = 24
SEARCH_KEYWORD_ITEM_MAX = 80
WEB_URL_MAX = 2100
WEB_URL_TITLE_MAX = 300
WEB_URL_DOMAIN_MAX = 253
