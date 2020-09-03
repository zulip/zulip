import time
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.timezone import now as timezone_now

from zerver.decorator import zulip_login_required
from zerver.lib.digest import DIGEST_CUTOFF, handle_digest_email


@zulip_login_required
def digest_page(request: HttpRequest) -> HttpResponse:
    user_profile_id = request.user.id
    cutoff = time.mktime((timezone_now() - timedelta(days=DIGEST_CUTOFF)).timetuple())
    context = handle_digest_email(user_profile_id, cutoff, render_to_web=True)
    if context:
        context.update(physical_address=settings.PHYSICAL_ADDRESS)
    return render(request, 'zerver/digest_base.html', context=context)
