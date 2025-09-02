import _ from "lodash";
import assert from "minimalistic-assert";

import * as alert_words from "./alert_words.ts";
import type {LocalMessage} from "./echo.ts";
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

export type NewMessage =
    | {
          type: "server_message";
          raw_message: RawMessage;
      }
    | {
          type: "local_message";
          raw_message: LocalMessage;
      };

export function process_new_message(opts: NewMessage): Message {
    // Call this function when processing a new message.  After
    // a message is processed and inserted into the message store
    // cache, most modules use message_store.get to look at
    // messages.
    const cached_msg = message_store.get_cached_message(opts.raw_message.id);
    if (cached_msg !== undefined) {
        // Copy the match topic and content over if they exist on
        // the new message
        if (
            opts.type === "server_message" &&
            util.get_match_topic(opts.raw_message) !== undefined
        ) {
            util.set_match_data(cached_msg, opts.raw_message);
        }
        return cached_msg;
    }

    const message_with_booleans = message_store.convert_raw_message_to_message_with_booleans(opts);
    people.extract_people_from_message(message_with_booleans.message);

    const sent_by_me = people.is_my_user_id(message_with_booleans.message.sender_id);
    people.maybe_incr_recipient_count({...message_with_booleans.message, sent_by_me});

    let status_emoji_info;
    const sender = people.maybe_get_user_by_id(message_with_booleans.message.sender_id);
    if (sender) {
        message_with_booleans.message.sender_full_name = sender.full_name;
        message_with_booleans.message.sender_email = sender.email;
        status_emoji_info = user_status.get_status_emoji(message_with_booleans.message.sender_id);
    }

    // TODO: Rather than adding this field to the message object, it
    // might be cleaner to create an independent map from message_id
    // => clean_reactions data for the message, with care being taken
    // to make sure reify_message_id moves the data structure
    // properly.
    const clean_reactions = reactions.generate_clean_reactions(opts.raw_message);

    let message: Message;
    if (message_with_booleans.message.type === "stream") {
        let topic;
        if (message_with_booleans.type === "local_message") {
            topic = message_with_booleans.message.topic;
        } else {
            topic = message_with_booleans.message.topic ?? message_with_booleans.message.subject;
        }
        assert(topic !== undefined);

        // We add fully delivered messages to stream_topic_history,
        // being careful to not include locally echoed messages, which
        // don't have permanent IDs and don't belong in that structure.
        if (message_with_booleans.type === "server_message") {
            stream_topic_history.add_message({
                stream_id: message_with_booleans.message.stream_id,
                topic_name: topic,
                message_id: message_with_booleans.message.id,
            });
        }

        recent_senders.process_stream_message({
            stream_id: message_with_booleans.message.stream_id,
            topic,
            sender_id: message_with_booleans.message.sender_id,
            id: message_with_booleans.message.id,
        });

        if (message_with_booleans.type === "server_message") {
            const {reactions, subject, ...rest} = message_with_booleans.message;
            message = {
                ...rest,
                sent_by_me,
                status_emoji_info,
                is_private: false,
                is_stream: true,
                reply_to: message_with_booleans.message.sender_email,
                topic,
                stream: stream_data.get_stream_name_from_id(
                    message_with_booleans.message.stream_id,
                ),
                clean_reactions,
                display_reply_to: undefined,
            };
        } else {
            const {reactions, ...rest} = message_with_booleans.message;
            // TODO: Ideally display_recipient would be not optional in LocalMessage
            // ideally by refactoring the use of `build_display_recipient`, but that
            // seemed complicated to type.
            assert(rest.display_recipient !== undefined);
            message = {
                ...rest,
                sent_by_me,
                status_emoji_info,
                is_private: false,
                is_stream: true,
                reply_to: message_with_booleans.message.sender_email,
                topic,
                stream: stream_data.get_stream_name_from_id(
                    message_with_booleans.message.stream_id,
                ),
                clean_reactions,
                display_reply_to: undefined,
                display_recipient: rest.display_recipient,
                // TODO(evy): set "website" or "ZulipDesktop" as the client depending
                // whether we are the web app or desktop app
                client: "",
                submessages: [],
            };
        }
        message_user_ids.add_user_id(message.sender_id);
    } else {
        const pm_with_user_ids = people.pm_with_user_ids(message_with_booleans.message);
        assert(pm_with_user_ids !== undefined);
        const pm_with_url = people.pm_with_url(message_with_booleans.message);
        assert(pm_with_url !== undefined);
        const to_user_ids = people.pm_reply_user_string(message_with_booleans.message);
        assert(to_user_ids !== undefined);
        if (message_with_booleans.type === "server_message") {
            message = {
                ..._.omit(message_with_booleans.message, "reactions"),
                sent_by_me,
                status_emoji_info,
                is_private: true,
                is_stream: false,
                reply_to: util.normalize_recipients(
                    message_store.get_pm_emails(message_with_booleans.message),
                ),
                display_reply_to: message_store.get_pm_full_names(pm_with_user_ids),
                pm_with_url,
                to_user_ids,
                clean_reactions,
            };
        } else {
            const {reactions, topic_links, ...rest} = message_with_booleans.message;
            // TODO: Ideally display_recipient would be not optional in LocalMessage
            // ideally by refactoring the use of `build_display_recipient`, but that
            // seemed complicated to type.
            assert(rest.display_recipient !== undefined);
            message = {
                ...rest,
                sent_by_me,
                status_emoji_info,
                is_private: true,
                is_stream: false,
                reply_to: util.normalize_recipients(
                    message_store.get_pm_emails(message_with_booleans.message),
                ),
                display_reply_to: message_store.get_pm_full_names(pm_with_user_ids),
                pm_with_url,
                to_user_ids,
                clean_reactions,
                display_recipient: rest.display_recipient,
                submessages: [],
                // TODO(evy): set "website" or "ZulipDesktop" as the client depending
                // whether we are the web app or desktop app
                client: "",
            };
        }

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
