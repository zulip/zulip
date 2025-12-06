import css_inline
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

from zerver.decorator import zulip_login_required
from zerver.lib.digest import DIGEST_CUTOFF, get_digest_context
from zerver.models import UserProfile


@zulip_login_required
def digest_page(request: HttpRequest) -> HttpResponse:
    user = request.user
    assert isinstance(user, UserProfile)

    cutoff = DIGEST_CUTOFF

    context = get_digest_context(user, cutoff)

    raw_html = render_to_string("zerver/emails/digest.html", context, request=request)

    inlined_html = css_inline.inline(raw_html)

    return HttpResponse(inlined_html)
