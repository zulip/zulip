from django.conf import settings
from django.shortcuts import render

def support_page(request):
    is_cloud = settings.CORPORATE_ENABLED

    admin_email = None
    if not is_cloud:
        # Canonical admin contact email for self-hosted servers
        admin_email = settings.ZULIP_ADMINISTRATOR_EMAIL

    return render(
        request,
        "zerver/support.html",
        {
            "is_cloud": is_cloud,
            "admin_email": admin_email,
        },
    )
