import hashlib
import logging

from django.core.cache import cache

from zerver.models import Realm, UserProfile
from zproject.nodl.supabase_client import get_supabase_users_with_phones

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes


def build_phone_hash_map(realm: Realm) -> dict[str, dict]:
    """Build a mapping of phone_hash -> user info for all registered users.

    Fetches users from Supabase Admin API, hashes their E.164 phone numbers,
    and cross-references with Zulip UserProfiles to find users who exist in both.

    Returns:
        Dict mapping SHA-256(phone_e164) -> {"user_id": int, "display_name": str, "phone_hash": str}
    """
    supabase_users = get_supabase_users_with_phones()

    # Build email -> (phone_hash, phone) mapping for all Supabase users
    email_to_hash: dict[str, str] = {}
    for su in supabase_users:
        phone = su["phone"]  # E.164 format from Supabase
        phone_hash = hashlib.sha256(phone.encode("utf-8")).hexdigest()
        # Derive Zulip email: use admin-controlled email field, fall back to phone@nodl.local
        email = su.get("email") or f"{phone}@nodl.local"
        email_to_hash[email.lower()] = phone_hash

    if not email_to_hash:
        return {}

    # Single batch query instead of N+1
    zulip_users = UserProfile.objects.filter(
        delivery_email__in=list(email_to_hash.keys()),
        realm=realm,
        is_active=True,
    )

    hash_map: dict[str, dict] = {}
    for user in zulip_users:
        phone_hash = email_to_hash.get(user.delivery_email.lower())
        if phone_hash:
            hash_map[phone_hash] = {
                "user_id": user.id,
                "display_name": user.full_name,
                "phone_hash": phone_hash,
            }

    return hash_map


def _cache_key_for_realm(realm: Realm) -> str:
    """Return the realm-scoped cache key for the phone hash map."""
    return f"nodl:phone_hash_map:{realm.id}"


def get_phone_hash_map(realm: Realm) -> dict[str, dict]:
    """Get the phone hash map, using cache when available."""
    key = _cache_key_for_realm(realm)
    cached = cache.get(key)
    if cached is not None:
        return cached
    hash_map = build_phone_hash_map(realm)
    cache.set(key, hash_map, timeout=CACHE_TTL)
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


def invalidate_phone_hash_cache(realm: Realm) -> None:
    """Invalidate the phone hash cache for a specific realm.

    Call this when a new user completes the auth bridge
    so they appear in contact discovery sooner.
    """
    cache.delete(_cache_key_for_realm(realm))
