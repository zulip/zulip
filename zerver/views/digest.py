import time
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.timezone import now as timezone_now

from zerver.decorator import zulip_login_required
from zerver.lib.digest import DIGEST_CUTOFF, get_digest_context


@zulip_login_required
def digest_page(request: HttpRequest) -> HttpResponse:
    user_profile = request.user
    start_date = request.GET.get('start-date', None)
    end_date = request.GET.get('end-date', None)
    message_weight = request.GET.get('message-weight', 1)
    sender_weight = request.GET.get('sender-weight', 1)
    react_weight = request.GET.get('react-weight', 1)

    if start_date:
        # do something
        start_date += 1
    else:
        # do something else
        start_date = 1
    cutoff = time.mktime((timezone_now() - timedelta(days=DIGEST_CUTOFF)).timetuple())
    end_date = timezone_now()

    context = get_digest_context(user_profile, cutoff, end_date)
    context.update(physical_address=settings.PHYSICAL_ADDRESS)
    return render(request, 'zerver/digest_base.html', context=context)
