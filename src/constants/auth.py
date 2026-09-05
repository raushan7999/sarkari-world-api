"""Authentication constants."""

API_KEY_PREFIX = "sw_"
# Indexed lookup prefix stored verbatim on User: "sw_" + 8 token characters.
API_KEY_LOOKUP_PREFIX_LENGTH = 11

SESSION_COOKIE = "sw_session"
USER_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
STAFF_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
SESSION_TOKEN_MAX_LENGTH = 4096

# API keys expire 30 days after issue and are rotated by hand. There is no
# expiry column in the schema, so validity is derived from api_key_created_at.
API_KEY_TTL_DAYS = 30
# Bytes of entropy in the generated secret.
API_KEY_ENTROPY_BYTES = 24

STAFF_ROLES = ("editor", "admin")
# Google is the only sign-in method. Adding one here is not enough — it also
# needs a verifier in `services/oauth.py`.
AUTH_PROVIDERS = ("google",)
