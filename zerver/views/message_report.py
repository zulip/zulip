from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message, validate_can_send_moderation_request
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

REPORT_MESSAGE_REASONS = {
    "spam": gettext_lazy("Spam"),
    "harassment": gettext_lazy("Harassment"),
    "inappropriate": gettext_lazy("Inappropriate content"),
    "norms": gettext_lazy("Violates community norms"),
    "other": gettext_lazy("Other reason"),
}


@typed_endpoint
def report_message_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: int,
    reason: str,
    explanation: str | None = None,
) -> HttpResponse:
    request_notes = RequestNotes.get_notes(request)
    assert request_notes.log_data is not None

    # Ensure that a moderation request channel is not disabled.
    if user_profile.realm.get_moderation_request_channel() is not None:
        raise JsonableError(
            _("Moderation request channel must be specified to enable message reporting.")
        )

    if reason == "other" and explanation is None:
        raise JsonableError(_("For reason=other, an explanation must be provided."))

    validate_can_send_moderation_request(user_profile)

    message = access_message(user_profile, message_id, lock_message=False)

    # TODO: The main logic to send the reported message to `moderation_request_channel`.

    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    log_data["extra"] = f"[{user_profile.full_name}, {message_id}, {reason}, {explanation}]"

    return json_success(request)
