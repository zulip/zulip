from django import forms
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from corporate.lib.support import get_support_url
from zerver.decorator import zulip_login_required
from zerver.lib.request import has_request_variables
from zerver.lib.send_email import FromAddress, send_email


class SupportRequestForm(forms.Form):
    # We use the same subject length requirement as GitHub's
    # contact support form.
    MAX_SUBJECT_LENGTH = 50
    request_subject = forms.CharField(max_length=MAX_SUBJECT_LENGTH)
    request_message = forms.CharField(widget=forms.Textarea)


@zulip_login_required
@has_request_variables
def support_request(request: HttpRequest) -> HttpResponse:
    user = request.user
    assert user.is_authenticated

    context = {
        "email": user.delivery_email,
        "realm_name": user.realm.name,
        "MAX_SUBJECT_LENGTH": SupportRequestForm.MAX_SUBJECT_LENGTH,
    }

    if request.POST:
        post_data = request.POST.copy()
        form = SupportRequestForm(post_data)

        if form.is_valid():
            email_context = {
                "requested_by": user.full_name,
                "realm_string_id": user.realm.string_id,
                "request_subject": form.cleaned_data["request_subject"],
                "request_message": form.cleaned_data["request_message"],
                "support_url": get_support_url(user.realm),
                "user_role": user.get_role_name(),
            }

            send_email(
                "zerver/emails/support_request",
                to_emails=[FromAddress.SUPPORT],
                from_name="Zulip Support",
                from_address=FromAddress.tokenized_no_reply_address(),
                reply_to_email=user.delivery_email,
                context=email_context,
            )

            response = render(request, "corporate/support_request_thanks.html", context=context)
            return response

    response = render(request, "corporate/support_request.html", context=context)
    return response
