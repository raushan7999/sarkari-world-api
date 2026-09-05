"""Authentication constants."""

API_KEY_PREFIX = "sw_"
# Indexed lookup prefix stored verbatim on User: "sw_" + 8 token characters.
API_KEY_LOOKUP_PREFIX_LENGTH = 11

SESSION_COOKIE = "sw_session"
USER_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
STAFF_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
SESSION_TOKEN_MAX_LENGTH = 4096

STAFF_ROLES = ("editor", "admin")
AUTH_PROVIDERS = ("subscription", "google")
