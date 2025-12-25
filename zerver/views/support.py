from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from zerver.lib.send_email import send_email
from zerver.lib.email_notifications import build_email


@require_http_methods(["GET", "POST"])
def support_page(request):
    is_cloud = settings.CORPORATE_ENABLED

    admin_email = None
    if not is_cloud:
        admin_email = settings.ZULIP_ADMINISTRATOR_EMAIL

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        zulip_url = request.POST.get("zulip_url", "").strip()
        message = request.POST.get("message", "").strip()

        email_subject = "Zulip support request"
        email_body = f"""
Name: {name}
Zulip URL: {zulip_url}

Message:
{message}
"""

        if is_cloud:
            recipients = [settings.ZULIP_SUPPORT_EMAIL]
        else:
            recipients = [admin_email]

        send_email(
            recipients,
            build_email(
                email_subject,
                email_body,
            ),
        )

        return redirect("/support?submitted=true")

    return render(
        request,
        "zerver/support.html",
        {
            "is_cloud": is_cloud,
            "admin_email": admin_email,
        },
    )
