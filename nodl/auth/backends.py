"""Supabase authentication backend for Django.

This module provides a Django authentication backend that authenticates
users via their Supabase user ID, working in conjunction with
SupabaseJWTMiddleware.
"""

import uuid
from typing import Any

from django.http import HttpRequest

from nodl.extensions.models import NodlUserExtension
from zerver.models import UserProfile


class SupabaseAuthBackend:
    """Django auth backend that authenticates users via Supabase user ID.

    This backend works in conjunction with SupabaseJWTMiddleware:
    1. Middleware validates JWT and sets request.supabase_user_id
    2. This backend looks up the UserProfile via NodlUserExtension

    The backend does NOT handle password authentication - all auth is
    delegated to Supabase via JWT tokens.
    """

    def authenticate(
        self,
        request: HttpRequest | None = None,
        supabase_user_id: str | None = None,
        **kwargs: Any,
    ) -> UserProfile | None:
        """Authenticate a user by Supabase user ID.

        Looks up the NodlUserExtension table to find the corresponding
        Zulip UserProfile for the given Supabase user ID.

        Args:
            request: The HTTP request (optional).
            supabase_user_id: The Supabase user UUID string.
            **kwargs: Additional arguments (ignored).

        Returns:
            UserProfile if found and active, None otherwise.
        """
        if supabase_user_id is None:
            return None

        try:
            supabase_uuid = uuid.UUID(supabase_user_id)
            extension = NodlUserExtension.objects.select_related("zulip_user").get(
                supabase_user_id=supabase_uuid
            )
            if extension.zulip_user and extension.zulip_user.is_active:
                return extension.zulip_user
        except (NodlUserExtension.DoesNotExist, ValueError):
            pass

        return None

    def get_user(self, user_id: int) -> UserProfile | None:
        """Get user by primary key ID.

        Required by Django's authentication framework for session management.

        Args:
            user_id: The primary key of the UserProfile.

        Returns:
            UserProfile if found and active, None otherwise.
        """
        try:
            return UserProfile.objects.get(pk=user_id, is_active=True)
        except UserProfile.DoesNotExist:
            return None
