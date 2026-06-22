from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.timestamp import datetime_to_global_time
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_int,
    check_iso_datetime,
    check_none_or,
    check_string,
    check_url,
)
from zerver.lib.webhooks.common import check_send_webhook_message, get_setup_webhook_message
from zerver.models import UserProfile

TOPIC_TEMPLATE = "Gong call: {call_title}"
MESSAGE_TEMPLATE = "**[{call_title}]({call_url})** started at {time} and lasted for {duration}."
SECTION_TEMPLATE = "**{heading}**:\n{body}"
TOPICS_TEMPLATE = "**Topics**: {topics}"
TOP_CONTENT_LIMIT = 3
PARTICIPANTS_LIMIT = 5
COMMENTS_LIMIT = 3


class Helper:
    def __init__(
        self,
        payload: WildValue,
        include_trackers: bool,
        include_topics: bool,
        include_participants: bool,
        include_participant_contacts: bool,
        include_public_comments: bool,
    ) -> None:
        self.payload = payload
        self.include_trackers = include_trackers
        self.include_topics = include_topics
        self.include_participants = include_participants
        self.include_participant_contacts = include_participant_contacts
        self.include_public_comments = include_public_comments


def format_duration_to_string(duration: int) -> str:
    # The duration value is in seconds.
    if duration < 60:
        return f"{duration} {'second' if duration == 1 else 'seconds'}"
    total_minutes = (duration + 30) // 60
    hours, minutes = divmod(total_minutes, 60)
    hour_word = "hour" if hours == 1 else "hours"
    minute_word = "minute" if minutes == 1 else "minutes"
    if hours > 0 and minutes > 0:
        return f"{hours} {hour_word} {minutes} {minute_word}"
    if hours > 0:
        return f"{hours} {hour_word}"
    return f"{minutes} {minute_word}"


def get_participants(parties_payload: WildValue, include_participant_contacts: bool) -> str:
    # Gong may omit a party's name, email, and phone for unidentified callers
    # (https://help.gong.io/docs/uploading-calls-from-a-non-integrated-telephony-system).
    labels: list[str] = []
    unidentified = 0
    for party in parties_payload:
        if len(labels) == PARTICIPANTS_LIMIT:
            break
        name = party.get("name")
        contact_parts = (
            [
                party[key].tame(check_string)
                for key in ("emailAddress", "phoneNumber")
                if party.get(key)
            ]
            if include_participant_contacts
            else []
        )

        label = name.tame(check_string) if name else (contact_parts[0] if contact_parts else None)
        if label is None:
            unidentified += 1
            continue
        title = party.get("title")
        title_part = f": {title.tame(check_string)}" if title else ""
        details = [c for c in contact_parts if c != label]
        contact_part = f" ({', '.join(details)})" if details else ""
        labels.append(f"* {label}{title_part}{contact_part}")

    if not labels:
        if unidentified:
            noun = "participant" if unidentified == 1 else "participants"
            return f"* {unidentified} {noun}"
        return ""

    if additional_participants := len(parties_payload) - len(labels):
        noun = "participant" if additional_participants == 1 else "participants"
        labels.append(f"* and {additional_participants} more {noun}")
    return "\n".join(labels)


def get_trackers(trackers_payload: WildValue) -> str:
    trackers = []
    for tracker in trackers_payload:
        if (count := tracker["count"].tame(check_int)) == 0:
            continue
        trackers.append((tracker["name"].tame(check_string), count, tracker.get("phrases")))
    trackers.sort(key=lambda tracker: tracker[1], reverse=True)

    tracker_lines = []
    for name, count, phrases in trackers[:TOP_CONTENT_LIMIT]:
        line = f"* {name} ({count})"
        if phrases:
            sorted_phrases = sorted(
                (
                    (phrase["phrase"].tame(check_string), phrase["count"].tame(check_int))
                    for phrase in phrases
                ),
                key=lambda phrase: phrase[1],
                reverse=True,
            )
            phrase_text = ", ".join(f"{text} ({n})" for text, n in sorted_phrases)
            line += f": {phrase_text}"
        tracker_lines.append(line)
    return "\n".join(tracker_lines)


def get_topics(topics_payload: WildValue) -> str:
    topics = [
        (topic["name"].tame(check_string), topic["duration"].tame(check_int))
        for topic in topics_payload
    ]
    topics.sort(key=lambda topic: topic[1], reverse=True)

    lines = []
    for name, duration in topics[:TOP_CONTENT_LIMIT]:
        if duration > 0:
            lines.append(f"{name} ({format_duration_to_string(duration)})")
        else:
            lines.append(f"{name}")

    topics_line = ", ".join(lines) if lines else ""
    if (extra_topics := len(topics) - TOP_CONTENT_LIMIT) > 0:
        topics_line += f" and {extra_topics} more {'topic' if extra_topics == 1 else 'topics'}"
    return topics_line + "." if topics_line else ""


def get_public_comments(comments_payload: WildValue) -> str:
    comments = sorted(
        comments_payload,
        key=lambda comment: comment["posted"].tame(check_iso_datetime),
        reverse=True,
    )
    lines = []
    for comment in comments[:COMMENTS_LIMIT]:
        text = comment["comment"].tame(check_string)
        lines.append(f"* {text}")
    additional_comments = len(comments) - len(lines)
    if additional_comments:
        lines.append(f"* and {additional_comments} more")
    return "\n".join(lines)


def handle_test_message(helper: Helper) -> tuple[str, str]:
    # Gong's "Test now" sends a real, already-processed call, so render the
    # actual message and prefix it with the standard setup confirmation.
    _, body = handle_call_processed_message(helper)
    return (
        "Gong Test",
        f"{get_setup_webhook_message('Gong')}\n\n{body}",
    )


def handle_call_processed_message(helper: Helper) -> tuple[str, str]:
    call_data = helper.payload["callData"]
    meta_data = call_data["metaData"]
    # call_title can be an optional field and can be omitted if not present.
    call_title = meta_data.get("title").tame(check_none_or(check_string))
    topic = (
        TOPIC_TEMPLATE.format(call_title=call_title)
        if call_title
        else f"Gong call (ID: {meta_data['id'].tame(check_string)})"
    )

    body = MESSAGE_TEMPLATE.format(
        call_title=call_title or "Gong call",
        call_url=meta_data["url"].tame(check_url),
        time=datetime_to_global_time(meta_data["started"].tame(check_iso_datetime)),
        duration=format_duration_to_string(meta_data["duration"].tame(check_int)),
    )
    if helper.include_participants and (
        participants := get_participants(call_data["parties"], helper.include_participant_contacts)
    ):
        body += "\n\n" + SECTION_TEMPLATE.format(heading="Participants", body=participants)

    if content := call_data.get("content"):
        if (
            helper.include_trackers
            and "trackers" in content
            and (top_trackers := get_trackers(content["trackers"]))
        ):
            body += "\n\n" + SECTION_TEMPLATE.format(
                heading="Top Trackers (by count)", body=top_trackers
            )
        if (
            helper.include_topics
            and "topics" in content
            and (topics := get_topics(content["topics"]))
        ):
            body += "\n\n" + TOPICS_TEMPLATE.format(topics=topics)

    if (
        helper.include_public_comments
        and (public_comments_list := call_data["collaboration"].get("publicComments"))
        and (public_comments := get_public_comments(public_comments_list))
    ):
        body += "\n\n" + SECTION_TEMPLATE.format(heading="Comments", body=public_comments)
    return topic, body


@webhook_view("Gong")
@typed_endpoint
def api_gong_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    include_trackers: Json[bool] = True,
    include_topics: Json[bool] = True,
    include_participants: Json[bool] = True,
    include_participant_contacts: Json[bool] = True,
    include_public_comments: Json[bool] = False,
) -> HttpResponse:
    helper = Helper(
        payload,
        include_trackers,
        include_topics,
        include_participants,
        include_participant_contacts,
        include_public_comments,
    )
    if payload.get("isTest").tame(check_bool):
        topic, body = handle_test_message(helper)
    else:
        topic, body = handle_call_processed_message(helper)
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
