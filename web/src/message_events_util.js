import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_notifications from "./compose_notifications";
import * as message_helper from "./message_helper";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";
import * as unread_ops from "./unread_ops";
import * as util from "./util";

// TODO: Move this function to 'message_util.ts' once #30702 is merged.
export function maybe_add_narrowed_messages(messages, msg_list, callback, attempt = 1) {
    const ids = [];

    for (const elem of messages) {
        ids.push(elem.id);
    }

    channel.get({
        url: "/json/messages/matches_narrow",
        data: {
            msg_ids: JSON.stringify(ids),
            narrow: JSON.stringify(narrow_state.public_search_terms()),
        },
        timeout: 5000,
        success(data) {
            if (!narrow_state.is_message_feed_visible() || msg_list !== message_lists.current) {
                // We unnarrowed or moved to Recent Conversations in the meantime.
                return;
            }

            let new_messages = [];
            const elsewhere_messages = [];

            for (const elem of messages) {
                if (Object.hasOwn(data.messages, elem.id)) {
                    util.set_match_data(elem, data.messages[elem.id]);
                    new_messages.push(elem);
                } else {
                    elsewhere_messages.push(elem);
                }
            }

            // This second call to process_new_message in the
            // insert_new_messages code path is designed to replace
            // our slightly stale message object with the latest copy
            // from the message_store. This helps in very rare race
            // conditions, where e.g. the current user's name was
            // edited in between when they sent the message and when
            // we hear back from the server and can echo the new
            // message.
            new_messages = new_messages.map((message) =>
                message_helper.process_new_message(message),
            );

            callback(new_messages, msg_list);
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
                    maybe_add_narrowed_messages(messages, msg_list, callback, attempt + 1);
                }
            }, delay);
        },
    });
}
