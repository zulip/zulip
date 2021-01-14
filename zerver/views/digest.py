import time
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.timezone import now as timezone_now

from zerver.decorator import zulip_login_required
from zerver.forms import DigestParameterForm
from zerver.lib.digest import DIGEST_CUTOFF, DigestWeights, get_digest_context


@zulip_login_required
def digest_page(request: HttpRequest) -> HttpResponse:
    user_profile = request.user

    cutoff = time.mktime((timezone_now() - timedelta(days=DIGEST_CUTOFF)).timetuple())
    digest_weights = DigestWeights(message_weight=1, sender_weight=1)
    if request.method == "POST":
        form = DigestParameterForm(request.POST)

        if form.is_valid():
            message_weight = form.cleaned_data["message_weight"]
            sender_weight = form.cleaned_data["sender_weight"]
            digest_weights = DigestWeights(
                message_weight=message_weight, sender_weight=sender_weight
            )

    else:
        form = DigestParameterForm()

    context = get_digest_context(user_profile, cutoff, digest_weights)
    context.update(physical_address=settings.PHYSICAL_ADDRESS, form=form)

    return render(request, "zerver/digest_base.html", context=context)
