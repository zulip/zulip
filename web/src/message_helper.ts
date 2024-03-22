import * as alert_words from "./alert_words";
import * as message_store from "./message_store";
import type {Message, RawMessage} from "./message_store";
import * as message_user_ids from "./message_user_ids";
import * as people from "./people";
import * as pm_conversations from "./pm_conversations";
import * as reactions from "./reactions";
import * as recent_senders from "./recent_senders";
import * as stream_topic_history from "./stream_topic_history";
// import * as user_status from "./user_status";
import * as util from "./util";

export function process_new_message(message: RawMessage): Message {
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

    const message_with_boolean = message_store.set_message_booleans(message);

    people.extract_people_from_message(message_with_boolean);
    const reply_to = util.normalize_recipients(message_store.get_pm_emails(message));
    const sent_by_me = people.is_current_user(message.sender_email);
    people.maybe_incr_recipient_count({...message_with_boolean, sent_by_me});

    let processed_message: Message;

    switch (message.type) {
        case "stream":
            processed_message = {
                ...message_with_boolean,
                sent_by_me,
                clean_reactions: new Map(),
                reply_to: message.sender_email,
                starred_status: "", // Set a dummy starred_status value
                message_reactions: [], // Initialize message_reactions as an empty array
                url: "", // Set a dummy URL value
                type: "stream",
                is_private: false,
                is_stream: true,
                topic: message.subject,
                stream_id: message.stream_id,
                subject: message.subject,
                topic_links: [],
            };

            stream_topic_history.add_message({
                stream_id: processed_message.stream_id,
                topic_name: processed_message.topic,
                message_id: processed_message.id,
            });

            recent_senders.process_stream_message(processed_message);
            message_user_ids.add_user_id(processed_message.sender_id);
            break;

        case "private":
            processed_message = {
                ...message_with_boolean,
                clean_reactions: new Map(),
                sent_by_me,
                reply_to,
                display_reply_to: message_store.get_pm_full_names(message),
                starred_status: "", // Set a dummy starred_status value
                message_reactions: [], // Initialize message_reactions as an empty array
                url: "", // Set a dummy URL value
                type: "private",
                is_private: true,
                is_stream: false,
                pm_with_url: people.pm_with_url(message)!,
                to_user_ids: people.reply_to_to_user_ids_string(reply_to)!,
            };

            pm_conversations.process_message(processed_message);

            recent_senders.process_private_message(processed_message);
            if (people.is_my_user_id(message.sender_id)) {
                for (const recip of message.display_recipient) {
                    message_user_ids.add_user_id(recip.id);
                }
            }
            break;
    }

    // Cleaning message_reactions during initial message processing
    // to avoid message_reactions being undefined during rendering
    if (!message.reactions) {
        message.reactions = [];
    }

    processed_message.reactions = message.reactions;
    processed_message.message_reactions = reactions.get_message_reactions(processed_message);

    const sender = people.maybe_get_user_by_id(processed_message.sender_id);
    if (sender) {
        processed_message.sender_full_name = sender.full_name;
        processed_message.sender_email = sender.email;
    }

    alert_words.process_message(processed_message);

    message_store.update_message_cache(processed_message);
    return processed_message;
}
