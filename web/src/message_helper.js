import * as alert_words from "./alert_words";
import * as message_store from "./message_store";
import * as message_user_ids from "./message_user_ids";
import * as people from "./people";
import * as pm_conversations from "./pm_conversations";
import * as recent_senders from "./recent_senders";
import * as stream_topic_history from "./stream_topic_history";
import * as user_status from "./user_status";
import * as util from "./util";

export function process_new_message(message) {
    // Call this function when processing a new message.  After
    // a message is processed and inserted into the message store
    // cache, most modules use message_store.get to look at
    // messages.
    const cached_msg = message_store.get_cached_message(message.id);
    if (cached_msg !== undefined) {
        // Copy the match topic and content over if they exist on
        // the new message
        if (util.get_match_topic(message) !== undefined) {
            util.set_match_data(cached_msg, message);
        }
        return cached_msg;
    }

    message_store.set_message_booleans(message);
    message.sent_by_me = people.is_current_user(message.sender_email);

    people.extract_people_from_message(message);
    people.maybe_incr_recipient_count(message);

    const sender = people.maybe_get_user_by_id(message.sender_id);
    if (sender) {
        message.sender_full_name = sender.full_name;
        message.sender_email = sender.email;
        message.status_emoji_info = user_status.get_status_emoji(message.sender_id);
    }

    // Convert topic even for direct messages, as legacy code
    // wants the empty field.
    util.convert_message_topic(message);

    switch (message.type) {
        case "stream":
            message.is_stream = true;
            message.reply_to = message.sender_email;

            stream_topic_history.add_message({
                stream_id: message.stream_id,
                topic_name: message.topic,
                message_id: message.id,
            });

            recent_senders.process_stream_message(message);
            message_user_ids.add_user_id(message.sender_id);
            break;

        case "private":
            message.is_private = true;
            message.reply_to = util.normalize_recipients(message_store.get_pm_emails(message));
            message.display_reply_to = message_store.get_pm_full_names(message);
            message.pm_with_url = people.pm_with_url(message);
            message.to_user_ids = people.pm_reply_user_string(message);

            pm_conversations.process_message(message);

            recent_senders.process_private_message(message);
            if (people.is_my_user_id(message.sender_id)) {
                for (const recip of message.display_recipient) {
                    message_user_ids.add_user_id(recip.id);
                }
            }
            break;
    }

    alert_words.process_message(message);
    if (!message.reactions) {
        message.reactions = [];
    }
    message_store.update_message_cache(message);
    return message;
}
