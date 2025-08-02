import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose_notifications from "./compose_notifications.ts";
import type {MessageList} from "./message_list.ts";
import * as message_lists from "./message_lists.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as narrow_state from "./narrow_state.ts";
import * as unread_ops from "./unread_ops.ts";
import * as util from "./util.ts";

const msg_match_narrow_api_response_schema = z.object({
    messages: z.record(
        z.string(),
        z.object({
            match_content: z.string(),
            match_subject: z.string(),
        }),
    ),
});

export function maybe_add_narrowed_messages(
    messages: Message[],
    msg_list: MessageList,
    messages_are_new = false,
    attempt = 1,
): void {
    const ids: number[] = [];

    for (const elem of messages) {
        ids.push(elem.id);
    }

    void channel.get({
        url: "/json/messages/matches_narrow",
        data: {
            msg_ids: JSON.stringify(ids),
            narrow: JSON.stringify(narrow_state.public_search_terms()),
        },
        timeout: 5000,
        success(raw_data) {
            const data = msg_match_narrow_api_response_schema.parse(raw_data);

            if (!narrow_state.is_message_feed_visible() || msg_list !== message_lists.current) {
                // We unnarrowed or moved to Recent Conversations in the meantime.
                return;
            }

            let new_messages: Message[] = [];
            const elsewhere_messages: Message[] = [];

            for (const elem of messages) {
                if (Object.hasOwn(data.messages, elem.id)) {
                    util.set_match_data(elem, data.messages[elem.id]!);
                    new_messages.push(elem);
                } else {
                    elsewhere_messages.push(elem);
                }
            }

            // We replace our slightly stale message object with the
            // latest copy from the message_store. This helps in very
            // rare race conditions, where e.g. the current user's name was
            // edited in between when they sent the message and when
            // we hear back from the server and can echo the new
            // message.
            new_messages = new_messages.map((new_msg) => {
                const cached_msg = message_store.get_cached_message(new_msg.id);
                if (cached_msg !== undefined) {
                    // Copy the match topic and content over from the new_msg to
                    // cached_msg. Also unlike message_helper.process_new_message, we
                    // are not checking if new_msg has match_topic, the upstream code
                    // ensure that.
                    util.set_match_data(cached_msg, new_msg);
                    return cached_msg;
                }

                return new_msg;
            });

            // Remove the elsewhere_messages from the message list since
            // they don't match the filter as per data from server.
            msg_list.remove_and_rerender(elsewhere_messages.map((msg) => msg.id));
            msg_list.add_messages(new_messages, {messages_are_new});
            unread_ops.process_visible();
            compose_notifications.notify_messages_outside_current_search(elsewhere_messages);
        },
        error(xhr) {
            if (!narrow_state.is_message_feed_visible() || msg_list !== message_lists.current) {
                return;
            }
            if (xhr.status === 400) {
                // This narrow was invalid -- don't retry it, and don't display the message.
                return;
            }
            if (attempt >= 5) {
                // Too many retries -- bail out.  However, this means the `messages` are potentially
                // missing from the search results view.  Since this is a very unlikely circumstance
                // (Tornado is up, Django is down for 5 retries, user is in a search view that it
                // cannot apply itself) and the failure mode is not bad (it will simply fail to
                // include live updates of new matching messages), just log an error.
                blueslip.error(
                    "Failed to determine if new message matches current narrow, after 5 tries",
                );
                return;
            }
            // Backoff on retries, with full jitter: up to 2s, 4s, 8s, 16s, 32s
            const delay = Math.random() * 2 ** attempt * 2000;
            setTimeout(() => {
                if (msg_list === message_lists.current) {
                    // Don't actually try again if we un-narrowed
                    // while waiting
                    maybe_add_narrowed_messages(messages, msg_list, messages_are_new, attempt + 1);
                }
            }, delay);
        },
    });
}
