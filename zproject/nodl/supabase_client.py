import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_supabase_users_with_phones() -> list[dict[str, Any]]:
    """Fetch all Supabase users that have a phone number set.

    Uses the Supabase Admin API with the service_role key.
    Paginates through all results.

    Returns:
        List of user dicts with keys: id, phone, user_metadata.
        Returns empty list on any API error.
    """
    supabase_url = getattr(settings, "NODL_SUPABASE_URL", "")
    service_role_key = getattr(settings, "NODL_SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_role_key:
        logger.error("NODL_SUPABASE_URL or NODL_SUPABASE_SERVICE_ROLE_KEY not configured")
        return []

    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
    }

    all_users: list[dict[str, Any]] = []
    page = 1

    try:
        while True:
            resp = requests.get(
                f"{supabase_url.rstrip('/')}/auth/v1/admin/users",
                headers=headers,
                params={"page": str(page), "per_page": "500"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning(
                    "Supabase Admin API returned %d when listing users (page %d)",
                    resp.status_code,
                    page,
                )
                break

            data = resp.json()
            users = data.get("users", [])
            if not users:
                break

            for user in users:
                phone = user.get("phone", "")
                if phone:
                    all_users.append(
                        {
                            "id": user.get("id", ""),
                            "phone": phone,
                            "user_metadata": user.get("user_metadata", {}),
                        }
                    )

            page += 1

    except requests.RequestException:
        logger.exception("Failed to fetch Supabase users with phones")

    return all_users
