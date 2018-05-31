from typing import Any, Dict

from social_django.strategy import DjangoStrategy
from django.http import HttpResponse

from zerver.models import UserProfile
from zerver.views.auth import login_or_register_remote_user, \
    redirect_and_log_into_subdomain, redirect_to_subdomain_login_url

class ZulipStrategy(DjangoStrategy):
    data = None  # type: Dict[str, Any]

    def complete(self, user_profile: UserProfile) -> HttpResponse:
        assert self.data is not None
        return_data = self.data['return_data']

        if return_data.get('invalid_realm'):
            return redirect_to_subdomain_login_url()

        realm = self.data['realm']
        details = self.data['details']

        full_name = details['fullname']
        invalid_subdomain = return_data.get('invalid_subdomain')
        mobile_flow_otp = self.session_get('mobile_flow_otp')
        is_signup = self.session_get('is_signup') == '1'
        redirect_to = self.session_get('next')
        email = details['email']

        if mobile_flow_otp is not None:
            return login_or_register_remote_user(self.request, email,
                                                 user_profile, full_name,
                                                 invalid_subdomain=invalid_subdomain,
                                                 mobile_flow_otp=mobile_flow_otp,
                                                 is_signup=is_signup,
                                                 redirect_to=redirect_to)
        return redirect_and_log_into_subdomain(realm, full_name,
                                               email,
                                               is_signup=is_signup,
                                               redirect_to=redirect_to)
