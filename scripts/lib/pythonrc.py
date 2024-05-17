try:
    from django.conf import settings

    from analytics.models import *  # noqa: F403
    from zerver.models import *  # noqa: F403
    from zerver.models.realms import *  # noqa: F403
    from zerver.models.streams import *  # noqa: F403
    from zerver.models.users import *  # noqa: F403

    if settings.CORPORATE_ENABLED:
        from corporate.lib.stripe import *  # noqa: F403
except Exception:
    import traceback

    print("\nException importing Zulip core modules on startup!")
    traceback.print_exc()
else:
    print("\nSuccessfully imported Zulip settings, models, and actions functions.")
