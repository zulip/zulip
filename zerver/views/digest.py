import time
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.utils.timezone import now as timezone_now

from zerver.decorator import zulip_login_required
from zerver.lib.digest import DIGEST_CUTOFF, get_digest_context
from zerver.lib.send_email import get_inliner_instance


@zulip_login_required
def digest_page(request: HttpRequest) -> HttpResponse:
    user_profile = request.user
    assert user_profile.is_authenticated
    cutoff = time.mktime((timezone_now() - timedelta(days=DIGEST_CUTOFF)).timetuple())

    context = get_digest_context(user_profile, cutoff)
    context.update(physical_address=settings.PHYSICAL_ADDRESS)

    email_body_html = render_to_string("zerver/emails/digest.html", context, request=request)

    inliner = get_inliner_instance()
    inlined_body = inliner.inline(email_body_html)

    context["inlined_digest_content"] = inlined_body
    final_html = render_to_string("zerver/digest_base.html", context, request=request)

    return HttpResponse(final_html)
