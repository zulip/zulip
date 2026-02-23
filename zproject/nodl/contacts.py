import hashlib
import logging

from django.core.cache import cache

from zerver.models import Realm, UserProfile

from zproject.nodl.supabase_client import get_supabase_users_with_phones

logger = logging.getLogger(__name__)

CACHE_KEY = "nodl:phone_hash_map"
CACHE_TTL = 300  # 5 minutes


def build_phone_hash_map(realm: Realm) -> dict[str, dict]:
    """Build a mapping of phone_hash -> user info for all registered users.

    Fetches users from Supabase Admin API, hashes their E.164 phone numbers,
    and cross-references with Zulip UserProfiles to find users who exist in both.

    Returns:
        Dict mapping SHA-256(phone_e164) -> {"user_id": int, "display_name": str, "phone_hash": str}
    """
    supabase_users = get_supabase_users_with_phones()
    hash_map: dict[str, dict] = {}

    for su in supabase_users:
        phone = su["phone"]  # E.164 format from Supabase
        phone_hash = hashlib.sha256(phone.encode("utf-8")).hexdigest()

        # Derive Zulip email: try direct email from Supabase metadata, fall back to phone@nodl.local
        email = su.get("user_metadata", {}).get("email") or f"{phone}@nodl.local"

        try:
            user = UserProfile.objects.get(
                delivery_email=email,
                realm=realm,
                is_active=True,
            )
            hash_map[phone_hash] = {
                "user_id": user.id,
                "display_name": user.full_name,
                "phone_hash": phone_hash,
            }
        except UserProfile.DoesNotExist:
            # User exists in Supabase but not in Zulip (hasn't completed auth bridge)
            continue

    return hash_map


def get_phone_hash_map(realm: Realm) -> dict[str, dict]:
    """Get the phone hash map, using cache when available."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    hash_map = build_phone_hash_map(realm)
    cache.set(CACHE_KEY, hash_map, timeout=CACHE_TTL)
    return hash_map


def match_phone_hashes(
    submitted_hashes: list[str], requesting_user_id: int, realm: Realm
) -> list[dict]:
    """Match submitted phone hashes against registered users.

    Args:
        submitted_hashes: List of SHA-256 hex strings to match.
        requesting_user_id: ID of the requesting user (excluded from results).
        realm: The Zulip realm to search in.

    Returns:
        List of match dicts: [{"user_id": int, "display_name": str, "phone_hash": str}, ...]
    """
    hash_map = get_phone_hash_map(realm)
    matches = []

    for h in submitted_hashes:
        if h in hash_map:
            match = hash_map[h]
            # Exclude the requesting user from results
            if match["user_id"] != requesting_user_id:
                matches.append(match)

    return matches


def invalidate_phone_hash_cache() -> None:
    """Invalidate the phone hash cache.

    Call this when a new user completes the auth bridge
    so they appear in contact discovery sooner.
    """
    cache.delete(CACHE_KEY)
