import time
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.timezone import now as timezone_now
from zerver.lib.digest import handle_digest_email, DIGEST_CUTOFF
from zerver.decorator import zulip_login_required
from datetime import timedelta

@zulip_login_required
def digest_page(request: HttpRequest) -> HttpResponse:
    user_profile_id = request.user.id
    cutoff = time.mktime((timezone_now() - timedelta(days=DIGEST_CUTOFF)).timetuple())
    context = handle_digest_email(user_profile_id, cutoff, render_to_web=True)
    return render(request, 'zerver/emails/compiled/digest.html', context=context)
