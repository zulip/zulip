import _ from "lodash";
import assert from "minimalistic-assert";

import * as alert_words from "./alert_words.ts";
import * as message_store from "./message_store.ts";
import type {Message, RawMessage} from "./message_store.ts";
import * as message_user_ids from "./message_user_ids.ts";
import * as people from "./people.ts";
import * as pm_conversations from "./pm_conversations.ts";
import * as reactions from "./reactions.ts";
import * as recent_senders from "./recent_senders.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as user_status from "./user_status.ts";
import * as util from "./util.ts";

export function process_new_message(raw_message: RawMessage, deliver_locally = false): Message {
    // Call this function when processing a new message.  After
    // a message is processed and inserted into the message store
    // cache, most modules use message_store.get to look at
    // messages.
    const cached_msg = message_store.get_cached_message(raw_message.id);
    if (cached_msg !== undefined) {
        // Copy the match topic and content over if they exist on
        // the new message
        if (util.get_match_topic(raw_message) !== undefined) {
            util.set_match_data(cached_msg, raw_message);
        }
        return cached_msg;
    }

    const message_with_booleans =
        message_store.convert_raw_message_to_message_with_booleans(raw_message);
    people.extract_people_from_message(message_with_booleans);

    const sent_by_me = people.is_my_user_id(message_with_booleans.sender_id);
    people.maybe_incr_recipient_count({...message_with_booleans, sent_by_me});

    let status_emoji_info;
    const sender = people.maybe_get_user_by_id(message_with_booleans.sender_id);
    if (sender) {
        message_with_booleans.sender_full_name = sender.full_name;
        message_with_booleans.sender_email = sender.email;
        status_emoji_info = user_status.get_status_emoji(message_with_booleans.sender_id);
    }

    if (!raw_message.reactions) {
        raw_message.reactions = [];
    }
    // TODO: Rather than adding this field to the message object, it
    // might be cleaner to create an independent map from message_id
    // => clean_reactions data for the message, with care being taken
    // to make sure reify_message_id moves the data structure
    // properly.
    const clean_reactions = reactions.generate_clean_reactions(raw_message);

    let message: Message;
    if (message_with_booleans.type === "stream") {
        const topic = message_with_booleans.topic ?? message_with_booleans.subject;
        assert(topic !== undefined);

        // We add fully delivered messages to stream_topic_history,
        // being careful to not include locally echoed messages, which
        // don't have permanent IDs and don't belong in that structure.
        if (!deliver_locally) {
            stream_topic_history.add_message({
                stream_id: message_with_booleans.stream_id,
                topic_name: topic,
                message_id: message_with_booleans.id,
            });
        }

        recent_senders.process_stream_message({
            stream_id: message_with_booleans.stream_id,
            topic,
            sender_id: message_with_booleans.sender_id,
            id: message_with_booleans.id,
        });

        message = {
            ..._.omit(message_with_booleans, ["reactions", "subject"]),
            sent_by_me,
            status_emoji_info,
            is_private: false,
            is_stream: true,
            reply_to: message_with_booleans.sender_email,
            topic,
            stream: stream_data.get_stream_name_from_id(message_with_booleans.stream_id),
            clean_reactions,
            display_reply_to: undefined,
        };
        message_user_ids.add_user_id(message.sender_id);
    } else {
        const pm_with_user_ids = people.pm_with_user_ids(message_with_booleans);
        assert(pm_with_user_ids !== undefined);
        const pm_with_url = people.pm_with_url(message_with_booleans);
        assert(pm_with_url !== undefined);
        const to_user_ids = people.pm_reply_user_string(message_with_booleans);
        assert(to_user_ids !== undefined);
        message = {
            ..._.omit(message_with_booleans, "reactions"),
            sent_by_me,
            status_emoji_info,
            is_private: true,
            is_stream: false,
            reply_to: util.normalize_recipients(message_store.get_pm_emails(message_with_booleans)),
            display_reply_to: message_store.get_pm_full_names(pm_with_user_ids),
            pm_with_url,
            to_user_ids,
            clean_reactions,
        };

        pm_conversations.process_message(message);

        recent_senders.process_private_message({
            to_user_ids,
            sender_id: message.sender_id,
            id: message.id,
        });
        if (people.is_my_user_id(message.sender_id)) {
            assert(typeof message.display_recipient !== "string");
            for (const recip of message.display_recipient) {
                message_user_ids.add_user_id(recip.id);
            }
        }
    }

    alert_words.process_message(message);
    message_store.update_message_cache(message);
    return message;
}
