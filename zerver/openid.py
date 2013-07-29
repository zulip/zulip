from __future__ import absolute_import

# Defer importing until later to avoid circular imports

def openid_failure_handler(request, message, status=403, template_name=None, exception=None):
    # We ignore template_name in this function

    from django_openid_auth.views import default_render_failure

    return default_render_failure(request, message, status=403, template_name="openid_error.html", exception=None)
