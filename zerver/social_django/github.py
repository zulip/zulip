from typing import Any, Dict, Optional

from social_core.backends.oauth import BaseOAuth2
from django.http import HttpResponse

from zerver.models import get_realm, UserProfile
from zproject.backends import common_get_active_user, auth_enabled_helper

def get_user(backend: BaseOAuth2,
             details: Dict[str, Any],
             response: HttpResponse,
             *args: Any,
             **kwargs: Any) -> Optional[UserProfile]:
    strategy = backend.strategy
    strategy.data = {}
    strategy.data['return_data'] = return_data = {}
    strategy.data['details'] = details
    email = details.get('email', False)
    if 'email' not in details or not email:
        return_data["invalid_email"] = True
        return None

    subdomain = strategy.session_get('subdomain')
    realm = get_realm(subdomain)
    if realm is None:
        return_data["invalid_realm"] = True
        return None

    strategy.data['realm'] = realm
    if not auth_enabled_helper([backend.auth_backend_name], realm):
        return_data["auth_backend_disabled"] = True
        return None

    return_data["valid_attestation"] = True
    return common_get_active_user(email, realm, return_data)
