from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from zerver.lib.send_email import send_email, send_email_to_admins


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

        body = f"""
Name: {name}
Zulip URL: {zulip_url}

Message:
{message}
""".strip()

        if is_cloud:
            send_email(
                template_prefix="zerver/emails/support_request",
                to_emails=["support@zulip.com"],
                context={
                    "realm_string_id": (
                        request.realm.string_id
                        if hasattr(request, "realm") and request.realm
                        else "unknown"
                    ),
                    "body": body,
                },
            )
        else:
            send_email_to_admins(
                template_prefix="zerver/emails/support_request",
                realm=request.realm,
                context={
                    "body": body,
                },
            )

        return redirect("/")

    return render(
        request,
        "zerver/support.html",
        {
            "is_cloud": is_cloud,
            "admin_email": admin_email,
        },
    )
