import logging

from django.db import IntegrityError

from zerver.actions.create_user import do_create_user
from zerver.models import Realm, UserProfile

logger = logging.getLogger(__name__)


def derive_email(supabase_payload: dict) -> str:
    """Derive a Zulip email from Supabase JWT claims.

    If the JWT has an email claim, use it directly.
    For phone-only users, derive email as {phone}@nodl.local.
    """
    email = supabase_payload.get("email", "")
    if email:
        return email
    phone = supabase_payload.get("phone", "")
    if phone:
        return f"{phone}@nodl.local"
    # Fallback to sub UUID
    return f"{supabase_payload['sub']}@nodl.local"


def derive_full_name(supabase_payload: dict) -> str:
    """Derive a display name from Supabase JWT claims."""
    user_metadata = supabase_payload.get("user_metadata", {})
    if isinstance(user_metadata, dict):
        name = user_metadata.get("full_name", "") or user_metadata.get("name", "")
        if name:
            return name
    phone = supabase_payload.get("phone", "")
    if phone:
        return phone
    return "nodl user"


def get_or_create_zulip_user(supabase_payload: dict, realm: Realm) -> UserProfile:
    """Look up or provision a Zulip user from Supabase JWT claims.

    Args:
        supabase_payload: Decoded Supabase JWT payload.
        realm: The Zulip realm to create the user in.

    Returns:
        The existing or newly created UserProfile.
    """
    email = derive_email(supabase_payload)

    # Try to find existing user
    try:
        return UserProfile.objects.get(
            delivery_email__iexact=email,
            realm=realm,
            is_active=True,
        )
    except UserProfile.DoesNotExist:
        pass

    # User does not exist - create one
    full_name = derive_full_name(supabase_payload)

    try:
        user_profile = do_create_user(
            email=email,
            password=None,
            realm=realm,
            full_name=full_name,
            acting_user=None,
        )
        logger.info(
            "Created Zulip user %s (id=%d) for Supabase user %s",
            email,
            user_profile.id,
            supabase_payload.get("sub", "unknown"),
        )
        return user_profile
    except IntegrityError as exc:
        # Race condition: another request may have created the user concurrently.
        # Try to fetch the existing user. If the lookup succeeds, this was a
        # duplicate-email race and we return the existing user. If the lookup
        # fails (DoesNotExist), the IntegrityError was something else entirely
        # (e.g. FK violation), so we re-raise the original exception.
        logger.info(
            "IntegrityError on user creation for %s, attempting fallback lookup",
            email,
        )
        try:
            return UserProfile.objects.get(
                delivery_email__iexact=email,
                realm=realm,
                is_active=True,
            )
        except UserProfile.DoesNotExist:
            raise exc from exc
