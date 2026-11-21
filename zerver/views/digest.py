import time
from datetime import timedelta
from urllib.parse import urlencode

import lxml.html
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.utils.timezone import now as timezone_now

from zerver.decorator import zulip_login_required
from zerver.lib.digest import DIGEST_CUTOFF, get_digest_context
from zerver.lib.send_email import get_inliner_instance

# Prototype: introduction variants to preview, while we figure out
# which organization settings the intro needs.
DIGEST_INTRO_PREVIEWS = {
    "default": "Default",
    "custom": "Custom",
    "none": "None",
}
DIGEST_CUSTOM_INTRO_EXAMPLE = (
    "Welcome back to {realm_name}! Our community call is every Thursday at "
    "16:00 UTC, and new members are always welcome to say hi in #social."
)


@zulip_login_required
def digest_page(request: HttpRequest) -> HttpResponse:
    user_profile = request.user
    assert user_profile.is_authenticated
    cutoff = time.mktime((timezone_now() - timedelta(days=DIGEST_CUTOFF)).timetuple())

    context = get_digest_context(user_profile, cutoff)
    context.update(physical_address=settings.PHYSICAL_ADDRESS, page_is_digest=True)

    selected = {"intro": request.GET.get("intro", "default")}
    if selected["intro"] not in DIGEST_INTRO_PREVIEWS:
        selected["intro"] = "default"

    def switch(name: str, label: str, options: dict[str, str]) -> dict[str, object]:
        return {
            "name": name,
            "label": label,
            "selected_label": options[selected[name]],
            "links": [
                (option_label, f"?{urlencode({**selected, name: key})}", key == selected[name])
                for key, option_label in options.items()
            ],
        }

    context.update(
        digest_intro=selected["intro"],
        digest_custom_intro=DIGEST_CUSTOM_INTRO_EXAMPLE.format(realm_name=user_profile.realm.name),
        digest_switches=[switch("intro", "Intro", DIGEST_INTRO_PREVIEWS)],
    )

    email_body_html = render_to_string("zerver/emails/digest.html", context, request=request)

    inliner = get_inliner_instance()
    inlined_body = inliner.inline(email_body_html)

    # The email is a whole HTML document; placed into the page as-is,
    # browsers merge its <body> attributes into the page's own <body>.
    # Keep only its styles and its body, as a <div>.
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
