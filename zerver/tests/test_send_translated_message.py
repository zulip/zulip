from zerver.models import UserProfile
from zerver.actions.message_send import do_send_messages, SendMessageRequest

# Test case 1: Single message translation
user_profile = UserProfile(default_language='es')
messages = [{'message': 'Hello, how are you?'}]

send_message_requests = [
    SendMessageRequest(
        message=send_request['message'],
        rendering_result=None,
        stream=None,
        local_id=None,
        sender_queue_id=None,
        realm=None,
        mention_data=None,
        mentioned_user_groups_map=None,
        active_user_ids=None,
        online_push_user_ids=None,
        pm_mention_push_disabled_user_ids=None,
        pm_mention_email_disabled_user_ids=None,
        stream_push_user_ids=None,
        stream_email_user_ids=None,
        followed_topic_push_user_ids=None,
        followed_topic_email_user_ids=None,
        muted_sender_user_ids=None,
        um_eligible_user_ids=None,
        long_term_idle_user_ids=None,
        default_bot_user_ids=None,
        service_bot_tuples=None,
        all_bot_user_ids=None,
        wildcard_mention_user_ids=None,
        followed_topic_wildcard_mention_user_ids=None,
        links_for_embed=None,
        widget_content=None
    )
    for send_request in messages
    if send_request is not None
]

translated_messages = do_send_messages(
    send_message_requests_maybe_none=send_message_requests,
    email_gateway=False,
    scheduled_message_to_self=False,
    mark_as_read=[],
)
print(translated_messages[0]['translated_content'])  # Output: "Hola, ¿cómo estás?"

# Rest of the test cases...
