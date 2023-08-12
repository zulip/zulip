import time

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_anything, check_int, check_list, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALL_EVENT_TYPES = ["error_notification", "error_activity"]


@webhook_view("Raygun", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_raygun_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    # The payload contains 'event' key. This 'event' key has a value of either
    # 'error_notification' or 'error_activity'. 'error_notification' happens
    # when an error is caught in an application, where as 'error_activity'
    # happens when an action is being taken for the error itself
    # (ignored/resolved/assigned/etc.).
    event = payload["event"].tame(check_string)

    # Because we wanted to create a message for all of the payloads, it is best
    # to handle them separately. This is because some payload keys don't exist
    # in the other event.

    if event == "error_notification":
        message = compose_notification_message(payload)
    elif event == "error_activity":
        message = compose_activity_message(payload)
    else:
        raise UnsupportedWebhookEventTypeError(event)

    topic = "test"

    check_send_webhook_message(request, user_profile, topic, message, event)

    return json_success(request)


def make_user_stats_chunk(error_dict: WildValue) -> str:
    """Creates a stat chunk about total occurrences and users affected for the
    error.

    Example: usersAffected: 2, totalOccurrences: 10
    Output: 2 users affected with 10 total occurrences

    :param error_dict: The error dictionary containing the error keys and
    values
    :returns: A message chunk that will be added to the main message
    """
    users_affected = error_dict["usersAffected"].tame(check_int)
    total_occurrences = error_dict["totalOccurrences"].tame(check_int)

    # One line is subjectively better than two lines for this.
    return f"* {users_affected} users affected with {total_occurrences} total occurrences\n"


def make_time_chunk(error_dict: WildValue) -> str:
    """Creates a time message chunk.

    Example: firstOccurredOn: "X", lastOccurredOn: "Y"
    Output:
    First occurred: X
    Last occurred: Y

    :param error_dict: The error dictionary containing the error keys and
    values
    :returns: A message chunk that will be added to the main message
    """
    # Make the timestamp more readable to a human.
    time_first = parse_time(error_dict["firstOccurredOn"].tame(check_string))
    time_last = parse_time(error_dict["lastOccurredOn"].tame(check_string))

    # Provide time information about this error,
    return f"* **First occurred**: {time_first}\n* **Last occurred**: {time_last}\n"


def make_message_chunk(message: str) -> str:
    """Creates a message chunk if exists.

    Example: message: "This is an example message" returns "Message: This is an
    example message". Whereas message: "" returns "".

    :param message: The value of message inside of the error dictionary
    :returns: A message chunk if there exists an additional message, otherwise
    returns an empty string.
    """
    # "Message" shouldn't be included if there is none supplied.
    return f"* **Message**: {message}\n" if message != "" else ""


def make_app_info_chunk(app_dict: WildValue) -> str:
    """Creates a message chunk that contains the application info and the link
    to the Raygun dashboard about the application.

    :param app_dict: The application dictionary obtained from the payload
    :returns: A message chunk that will be added to the main message
    """
    app_name = app_dict["name"].tame(check_string)
    app_url = app_dict["url"].tame(check_string)
    return f"* **Application details**: [{app_name}]({app_url})\n"


def notification_message_follow_up(payload: WildValue) -> str:
    """Creates a message for a repeating error follow up

    :param payload: Raygun payload
    :return: Returns the message, somewhat beautifully formatted
    """
    message = ""

    # Link to Raygun about the follow up
    followup_link_md = "[follow-up error]({})".format(payload["error"]["url"].tame(check_string))

    followup_type = payload["eventType"].tame(check_string)

    if followup_type == "HourlyFollowUp":
        prefix = "Hourly"
    else:
        # Cut the "MinuteFollowUp" from the possible event types, then add "
        # minute" after that. So prefix for "OneMinuteFollowUp" is "One
        # minute", where "FiveMinuteFollowUp" is "Five minute".
        prefix = followup_type[: len(followup_type) - 14] + " minute"

    message += f"{prefix} {followup_link_md}:\n"

    # Get the message of the error.
    payload_msg = payload["error"]["message"].tame(check_string)

    message += make_message_chunk(payload_msg)
    message += make_time_chunk(payload["error"])
    message += make_user_stats_chunk(payload["error"])
    message += make_app_info_chunk(payload["application"])

    return message


def notification_message_error_occurred(payload: WildValue) -> str:
    """Creates a message for a new error or reoccurred error

    :param payload: Raygun payload
    :return: Returns the message, somewhat beautifully formatted
    """
    message = ""

    # Provide a clickable link that goes to Raygun about this error.
    error_link_md = "[Error]({})".format(payload["error"]["url"].tame(check_string))

    # Stylize the message based on the event type of the error.
    if payload["eventType"].tame(check_string) == "NewErrorOccurred":
        message += "{}:\n".format(f"New {error_link_md} occurred")
    elif payload["eventType"].tame(check_string) == "ErrorReoccurred":
        message += "{}:\n".format(f"{error_link_md} reoccurred")

    # Get the message of the error. This value can be empty (as in "").
    payload_msg = payload["error"]["message"].tame(check_string)

    message += make_message_chunk(payload_msg)
    message += make_time_chunk(payload["error"])
    message += make_user_stats_chunk(payload["error"])

    # Only NewErrorOccurred and ErrorReoccurred contain an error instance.
    error_instance = payload["error"]["instance"]

    # Extract each of the keys and values in error_instance for easier handle

    # Contains list of tags for the error. Can be empty (null)
    tags = error_instance["tags"]

    # Contains the identity of affected user at the moment this error
    # happened. This surprisingly can be null. Somehow.
    affected_user = error_instance["affectedUser"]

    # Contains custom data for this particular error (if supplied). Can be
    # null.
    custom_data = error_instance["customData"]

    if tags is not None:
        message += "* **Tags**: {}\n".format(", ".join(tags.tame(check_list(check_string))))

    if affected_user is not None:
        user_uuid = affected_user["UUID"].tame(check_string)
        message += f"* **Affected user**: {user_uuid[:6]}...{user_uuid[-5:]}\n"

    if custom_data is not None:
        # We don't know what the keys and values beforehand, so we are forced
        # to iterate.
        for key in sorted(custom_data.keys()):
            message += f"* **{key}**: {custom_data[key].tame(check_anything)}\n"

    message += make_app_info_chunk(payload["application"])

    return message


def compose_notification_message(payload: WildValue) -> str:
    """Composes a message that contains information on the error

    :param payload: Raygun payload
    :return: Returns a response message
    """

    # Get the event type of the error. This can be "NewErrorOccurred",
    # "ErrorReoccurred", "OneMinuteFollowUp", "FiveMinuteFollowUp", ...,
    # "HourlyFollowUp" for notification error.
    event_type = payload["eventType"].tame(check_string)

    # "NewErrorOccurred" and "ErrorReoccurred" contain error instance
    # information, meaning that it has payload['error']['instance']. The other
    # event type (the follow ups) doesn't have this instance.

    # We now split this main function again into two functions. One is for
    # "NewErrorOccurred" and "ErrorReoccurred", and one is for the rest. Both
    # functions will return a text message that is formatted for the chat.
    if event_type in ("NewErrorOccurred", "ErrorReoccurred"):
        return notification_message_error_occurred(payload)
    elif "FollowUp" in event_type:
        return notification_message_follow_up(payload)
    else:
        raise UnsupportedWebhookEventTypeError(event_type)


def activity_message(payload: WildValue) -> str:
    """Creates a message from an activity that is being taken for an error

    :param payload: Raygun payload
    :return: Returns the message, somewhat beautifully formatted
    """
    message = ""

    error_link_md = "[Error]({})".format(payload["error"]["url"].tame(check_string))

    event_type = payload["eventType"].tame(check_string)

    user = payload["error"]["user"].tame(check_string)
    if event_type == "StatusChanged":
        error_status = payload["error"]["status"].tame(check_string)
        message += f"{error_link_md} status changed to **{error_status}** by {user}:\n"
    elif event_type == "CommentAdded":
        comment = payload["error"]["comment"].tame(check_string)
        message += f"{user} commented on {error_link_md}:\n\n``` quote\n{comment}\n```\n"
    elif event_type == "AssignedToUser":
        assigned_to = payload["error"]["assignedTo"].tame(check_string)
        message += f"{user} assigned {error_link_md} to {assigned_to}:\n"

    message += "* **Timestamp**: {}\n".format(
        parse_time(payload["error"]["activityDate"].tame(check_string))
    )

    message += make_app_info_chunk(payload["application"])

    return message


def compose_activity_message(payload: WildValue) -> str:
    """Composes a message that contains an activity that is being taken to
    an error, such as commenting, assigning an error to a user, ignoring the
    error, etc.

    :param payload: Raygun payload
    :return: Returns a response message
    """

    event_type = payload["eventType"].tame(check_string)

    # Activity is separated into three main categories: status changes (
    # ignores, resolved), error is assigned to user, and comment added to
    # an error,

    # But, they all are almost identical and the only differences between them
    # are the keys at line 9 (check fixtures). So there's no need to split
    # the function like the notification one.
    if event_type in ("StatusChanged", "AssignedToUser", "CommentAdded"):
        return activity_message(payload)
    else:
        raise UnsupportedWebhookEventTypeError(event_type)


def parse_time(timestamp: str) -> str:
    """Parses and returns the timestamp provided

    :param timestamp: The timestamp provided by the payload
    :returns: A string containing the time
    """

    # Raygun provides two timestamp format, one with the Z at the end,
    # and one without the Z.

    format = "%Y-%m-%dT%H:%M:%S"
    format += "Z" if timestamp[-1:] == "Z" else ""
    parsed_time = time.strftime("%c", time.strptime(timestamp, format))
    return parsed_time
