import time
from datetime import timedelta

import lxml.html
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
    assert settings.STATIC_URL is not None
    context.update(
        email_images_base_url=settings.STATIC_URL + "images/emails",
        physical_address=settings.PHYSICAL_ADDRESS,
        page_is_digest=True,
    )

    email_body_html = render_to_string("zerver/emails/digest.html", context, request=request)

    inliner = get_inliner_instance()
    inlined_body = inliner.inline(email_body_html)

    # The email is a whole HTML document; placed into the page as-is,
    # browsers merge its <body> attributes, like its font settings,
    # into the page's own <body>. Keep only its styles and its body,
    # as a <div>.
    email_document = lxml.html.document_fromstring(inlined_body)
    email_head = email_document.find("head")
    email_body = email_document.find("body")
    assert email_head is not None and email_body is not None
    email_body.tag = "div"
    context["inlined_digest_content"] = "".join(
        lxml.html.tostring(element, encoding="unicode")
        for element in [*email_head.iter("style"), email_body]
    )
    final_html = render_to_string("zerver/digest_base.html", context, request=request)

    return HttpResponse(final_html)
