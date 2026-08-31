import time
from collections import defaultdict
from typing import Any, Literal

from django.conf import settings
from django.utils.timezone import now as timezone_now
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.actions.message_summary import ai_stats_finish, ai_stats_start
from zerver.lib.markdown import markdown_convert
from zerver.lib.message import get_raw_unread_data, messages_for_ids
from zerver.lib.topic import get_topic_from_message_info
from zerver.lib.url_encoding import encode_user_ids, stream_message_url
from zerver.models import UserProfile
from zerver.models.realms import MessageEditHistoryVisibilityPolicyEnum

# Maximum number of unread messages to summarize in a single recap request.
MAX_UNREAD_MESSAGES_FOR_RECAP = 100


def get_message_link(message: dict[str, Any]) -> str:
    """Generate a relative Zulip narrow URL for linking to a specific message."""
    if message["type"] == "stream":
        return stream_message_url(
            realm=None,
            message=message,
            include_base_url=False,
        )
    # Direct message link
    user_ids = [recipient["id"] for recipient in message["display_recipient"]]
    dm_slug = encode_user_ids(user_ids)
    message_id = str(message["id"])
    return f"#narrow/dm/{dm_slug}/near/{message_id}"


def format_messages_for_recap_prompt(
    message_list: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """
    Groups messages by conversation (stream + topic, or DM group) and
    formats them for the LLM prompt with pre-computed Zulip navigation links.
    """
    conversations: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for msg in message_list:
        if msg["type"] == "stream":
            channel_name = msg["display_recipient"]
            topic_name = get_topic_from_message_info(msg)
            conv_key = (f"#{channel_name}", topic_name)
        else:
            recipient_names = ", ".join(
                r["full_name"] for r in msg["display_recipient"]
            )
            conv_key = ("Direct Messages", recipient_names)
        conversations[conv_key].append(msg)

    formatted_sections = []
    metadata = []

    for (channel_or_dm, topic_or_recipients), msgs in conversations.items():
        section_lines = [f"### Conversation: {channel_or_dm} > {topic_or_recipients}"]
        for msg in msgs:
            msg_id = msg["id"]
            sender = msg["sender_full_name"]
            content = msg["content"]
            link_url = get_message_link(msg)
            section_lines.append(
                f"- [Message {msg_id}] {sender}: {content} (Link: {link_url})"
            )
            metadata.append({"id": msg_id, "sender": sender, "link": link_url})
        formatted_sections.append("\n".join(section_lines))

    return "\n\n".join(formatted_sections), metadata


def make_chat_message(
    content: str, role: Literal["user", "system"] = "user"
) -> ChatCompletionMessageParam:
    if role == "system":
        return {"content": content, "role": "system"}
    return {"content": content, "role": "user"}


def do_generate_recap(user_profile: UserProfile) -> str | None:
    model = settings.TOPIC_SUMMARIZATION_MODEL
    if model is None:  # nocoverage
        return None

    # Fetch unread data for the user
    raw_unread = get_raw_unread_data(user_profile)
    unmuted_stream_msgs = raw_unread["unmuted_stream_msgs"]
    pm_dict = raw_unread["pm_dict"]
    huddle_dict = raw_unread["huddle_dict"]

    all_unread_ids = sorted(
        list(unmuted_stream_msgs) + list(pm_dict.keys()) + list(huddle_dict.keys())
    )

    if len(all_unread_ids) == 0:
        return None

    # Cap to the most recent unread messages
    if len(all_unread_ids) > MAX_UNREAD_MESSAGES_FOR_RECAP:
        all_unread_ids = all_unread_ids[-MAX_UNREAD_MESSAGES_FOR_RECAP:]

    user_message_flags = {msg_id: [] for msg_id in all_unread_ids}
    message_list = messages_for_ids(
        message_ids=all_unread_ids,
        user_message_flags=user_message_flags,
        search_fields={},
        apply_markdown=False,
        client_gravatar=True,
        allow_empty_topic_name=False,
        message_edit_history_visibility_policy=MessageEditHistoryVisibilityPolicyEnum.none.value,
        user_profile=user_profile,
        realm=user_profile.realm,
    )

    if len(message_list) == 0:
        return None

    formatted_conversations, _ = format_messages_for_recap_prompt(message_list)

    system_prompt = (
        "You are an assistant providing an organized recap of unread messages in the Zulip team chat app. "
        "Your goal is to help the user catch up quickly on what happened while they were away.\n\n"
        "Guidelines:\n"
        "1. Organize your summary by Channel and Topic as provided.\n"
        "2. For each conversation, provide a concise bulleted summary of key discussions, decisions, and action items.\n"
        "3. Include clickable Markdown references to important messages using the provided Link URLs. "
        "For example: 'Alice announced the new release ([link](#narrow/...))' or 'Bob asked about the database schema ([message](#narrow/...))'.\n"
        "4. Refer to people by their names.\n"
        "5. Keep the recap structured, informative, and succinct.\n"
        "6. Do not include introductory pleasantries like 'Here is your recap:'. Start directly with the first section."
    )

    user_prompt = (
        f"Please summarize the following unread messages across conversations:\n\n"
        f"{formatted_conversations}"
    )

    messages = [
        make_chat_message(system_prompt, "system"),
        make_chat_message(user_prompt, "user"),
    ]

    ai_stats_start()

    client = OpenAI(
        api_key=settings.TOPIC_SUMMARIZATION_API_KEY,
        base_url=settings.TOPIC_SUMMARIZATION_API_BASE,
    )
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **settings.TOPIC_SUMMARIZATION_PARAMETERS,
    )

    assert response.usage is not None
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    credits_used = (output_tokens * settings.OUTPUT_COST_PER_GIGATOKEN) + (
        input_tokens * settings.INPUT_COST_PER_GIGATOKEN
    )
    ai_stats_finish()

    do_increment_logging_stat(
        user_profile, COUNT_STATS["ai_credit_usage::day"], None, timezone_now(), credits_used
    )

    recap_content = response.choices[0].message.content
    assert recap_content is not None

    rendered_recap = markdown_convert(recap_content, message_realm=user_profile.realm).rendered_content
    return rendered_recap
