import $ from "jquery";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import {$t_html} from "./i18n";
import * as loading from "./loading";
import * as message_flags from "./message_flags";
import * as message_lists from "./message_lists";
import * as message_live_update from "./message_live_update";
import * as message_store from "./message_store";
import * as message_viewport from "./message_viewport";
import * as notifications from "./notifications";
import * as people from "./people";
import * as recent_topics_ui from "./recent_topics_ui";
import * as recent_topics_util from "./recent_topics_util";
import * as ui_report from "./ui_report";
import * as unread from "./unread";
import * as unread_ui from "./unread_ui";

let loading_indicator_displayed = false;

// We might want to use a slightly smaller batch for the first
// request, because empirically, the first request can be
// significantly slower, likely due to the database warming up its
// cache with your UserMessage rows. We don't do that, just because
// the progress indicator experience of 1000, 3000, etc. feels weird.
const INITIAL_BATCH_SIZE = 1000;
const FOLLOWUP_BATCH_SIZE = 1000;

export function mark_all_as_read(args = {}) {
    args = {
        // We use an anchor of "oldest", not "first_unread", because
        // "first_unread" will be the oldest non-muted unread message,
        // which would result in muted unreads older than the first
        // unread not being processed.
        anchor: "oldest",
        messages_read_till_now: 0,
        num_after: INITIAL_BATCH_SIZE,
        ...args,
    };
    const request = {
        anchor: args.anchor,
        // anchor="oldest" is an anchor ID lower than any valid
        // message ID; and follow-up requests will have already
        // processed the anchor ID, so we just want this to be
        // unconditionally false.
        include_anchor: false,
        num_before: 0,
        num_after: args.num_after,
        op: "add",
        flag: "read",
        // Since there's a database index on is:unread, it's a fast
        // search query and thus worth including here as an optimization.
        narrow: JSON.stringify([{operator: "is", operand: "unread", negated: false}]),
    };
    channel.post({
        url: "/json/messages/flags/narrow",
        data: request,
        success(data) {
            const messages_read_till_now = args.messages_read_till_now + data.updated_count;

            if (!data.found_newest) {
                // If we weren't able to make everything as read in a
                // single API request, then show a loading indicator.
                ui_report.loading(
                    $t_html(
                        {
                            defaultMessage:
                                "{N, plural, one {Working… {N} message marked as read so far.} other {Working… {N} messages marked as read so far.}}",
                        },
                        {N: messages_read_till_now},
                    ),
                    $("#request-progress-status-banner"),
                );
                if (!loading_indicator_displayed) {
                    loading.make_indicator(
                        $("#request-progress-status-banner .loading-indicator"),
                        {abs_positioned: true},
                    );
                    loading_indicator_displayed = true;
                }

                mark_all_as_read({
                    anchor: data.last_processed_id,
                    messages_read_till_now,
                    num_after: FOLLOWUP_BATCH_SIZE,
                });
            } else {
                if (loading_indicator_displayed) {
                    // Only show the success message if a progress banner was displayed.
                    ui_report.loading(
                        $t_html(
                            {
                                defaultMessage:
                                    "{N, plural, one {Done! {N} message marked as read.} other {Done! {N} messages marked as read.}}",
                            },
                            {N: messages_read_till_now},
                        ),
                        $("#request-progress-status-banner"),
                        true,
                    );
                    loading_indicator_displayed = false;
                }

                if (unread.old_unreads_missing) {
                    // In the rare case that the user had more than
                    // 50K total unreads on the server, the client
                    // won't have known about all of them; this was
                    // communicated to the client via
                    // unread.old_unreads_missing.
                    //
                    // However, since we know we just marked
                    // **everything** as read, we know that we now
                    // have a correct data set of unreads.
                    unread.clear_old_unreads_missing();
                    blueslip.log("Cleared old_unreads_missing after bankruptcy.");
                }
            }
        },
        error(xhr) {
            // If we hit the rate limit, just continue without showing any error.
            if (xhr.responseJSON.code === "RATE_LIMIT_HIT") {
                const milliseconds_to_wait = 1000 * xhr.responseJSON["retry-after"];
                setTimeout(() => mark_all_as_read(args), milliseconds_to_wait);
            } else {
                // TODO: Ideally this would be a ui_report.error();
                // the user needs to know that our operation failed.
                blueslip.error("Failed to mark messages as read: " + xhr.responseText);
            }
        },
    });
}

function process_newly_read_message(message, options) {
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.show_message_as_read(message, options);
    }
    notifications.close_notification(message);
    recent_topics_ui.update_topic_unread_count(message);
}

export function mark_as_unread_from_here(
    message_id,
    include_anchor = true,
    messages_marked_unread_till_now = 0,
    num_after = INITIAL_BATCH_SIZE - 1,
    narrow,
) {
    if (narrow === undefined) {
        narrow = JSON.stringify(message_lists.current.data.filter.operators());
    }
    message_lists.current.prevent_reading();
    const opts = {
        anchor: message_id,
        include_anchor,
        num_before: 0,
        num_after,
        narrow,
        op: "remove",
        flag: "read",
    };
    channel.post({
        url: "/json/messages/flags/narrow",
        data: opts,
        success(data) {
            messages_marked_unread_till_now += data.updated_count;

            if (!data.found_newest) {
                // If we weren't able to complete the request fully in
                // the current batch, show a progress indicator.
                ui_report.loading(
                    $t_html(
                        {
                            defaultMessage:
                                "{N, plural, one {Working… {N} message marked as unread so far.} other {Working… {N} messages marked as unread so far.}}",
                        },
                        {N: messages_marked_unread_till_now},
                    ),
                    $("#request-progress-status-banner"),
                );
                if (!loading_indicator_displayed) {
                    loading.make_indicator(
                        $("#request-progress-status-banner .loading-indicator"),
                        {abs_positioned: true},
                    );
                    loading_indicator_displayed = true;
                }
                mark_as_unread_from_here(
                    data.last_processed_id,
                    false,
                    messages_marked_unread_till_now,
                    FOLLOWUP_BATCH_SIZE,
                    narrow,
                );
            } else if (loading_indicator_displayed) {
                // If we were showing a loading indicator, then
                // display that we finished. For the common case where
                // the operation succeeds in a single batch, we don't
                // bother distracting the user with the indication;
                // the success will be obvious from the UI updating.
                loading_indicator_displayed = false;
                ui_report.loading(
                    $t_html(
                        {
                            defaultMessage:
                                "{N, plural, one {Done! {N} message marked as unread.} other {Done! {N} messages marked as unread.}}",
                        },
                        {N: messages_marked_unread_till_now},
                    ),
                    $("#request-progress-status-banner"),
                    true,
                );
            }
        },
        error(xhr) {
            // If we hit the rate limit, just continue without showing any error.
            if (xhr.responseJSON.code === "RATE_LIMIT_HIT") {
                const milliseconds_to_wait = 1000 * xhr.responseJSON["retry-after"];
                setTimeout(
                    () =>
                        mark_as_unread_from_here(
                            message_id,
                            false,
                            messages_marked_unread_till_now,
                            narrow,
                        ),
                    milliseconds_to_wait,
                );
            } else {
                // TODO: Ideally, this case would communicate the
                // failure to the user, with some manual retry
                // offered, since the most likely cause is a 502.
                blueslip.error("Unexpected error marking messages as unread: " + xhr.responseText);
            }
        },
    });
}

export function resume_reading() {
    message_lists.current.resume_reading();
}

export function process_read_messages_event(message_ids) {
    /*
        This code has a lot in common with notify_server_messages_read,
        but there are subtle differences due to the fact that the
        server can tell us about unread messages that we didn't
        actually read locally (and which we may not have even
        loaded locally).
    */
    const options = {from: "server"};

    message_ids = unread.get_unread_message_ids(message_ids);
    if (message_ids.length === 0) {
        return;
    }

    for (const message_id of message_ids) {
        if (message_lists.current.narrowed) {
            // I'm not sure this entirely makes sense for all server
            // notifications.
            unread.set_messages_read_in_narrow(true);
        }

        unread.mark_as_read(message_id);

        const message = message_store.get(message_id);

        // TODO: This ends up doing one in-place rerender operation on
        // recent conversations per message, not a single global
        // rerender or one per conversation.
        if (message) {
            process_newly_read_message(message, options);
        }
    }

    unread_ui.update_unread_counts();
}

export function process_unread_messages_event({message_ids, message_details}) {
    // This is the reverse of  process_unread_messages_event.
    message_ids = unread.get_read_message_ids(message_ids);
    if (message_ids.length === 0) {
        return;
    }

    if (message_lists.current.narrowed) {
        unread.set_messages_read_in_narrow(false);
    }

    for (const message_id of message_ids) {
        const message = message_store.get(message_id);

        if (message) {
            message.unread = true;
        }

        const message_info = message_details[message_id];

        let user_ids_string;

        if (message_info.type === "private") {
            user_ids_string = people.pm_lookup_key_from_user_ids(message_info.user_ids);
        }

        unread.process_unread_message({
            id: message_id,
            mentioned: message_info.mentioned,
            stream_id: message_info.stream_id,
            topic: message_info.topic,
            type: message_info.type,
            unread: true,
            user_ids_string,
        });
    }

    /*
        A batch of messages marked as unread can be 1000+ messages, so
        we do want to do a bulk operation for these UI updates.

        We use a big-hammer approach now to updating the message view.
        This is relatively harmless, since the only time we are called is
        when the user herself marks her message as unread.  But we
        do eventually want to be more surgical here, especially once we
        have a final scheme for how best to structure the HTML within
        the message to indicate read-vs.-unread.  Currently we use a
        green border, but that may change.

        The main downside of doing a full rerender is that it can be
        user-visible in the form of users' avatars flickering.
    */
    message_live_update.rerender_messages_view();
    recent_topics_ui.complete_rerender();

    if (
        !message_lists.current.can_mark_messages_read() &&
        message_lists.current.has_unread_messages()
    ) {
        unread_ui.notify_messages_remain_unread();
    }

    unread_ui.update_unread_counts();
}

// Takes a list of messages and marks them as read.
// Skips any messages that are already marked as read.
export function notify_server_messages_read(messages, options = {}) {
    messages = unread.get_unread_messages(messages);
    if (messages.length === 0) {
        return;
    }

    message_flags.send_read(messages);

    for (const message of messages) {
        if (message_lists.current.narrowed) {
            unread.set_messages_read_in_narrow(true);
        }

        unread.mark_as_read(message.id);
        process_newly_read_message(message, options);
    }

    unread_ui.update_unread_counts();
}

export function notify_server_message_read(message, options) {
    notify_server_messages_read([message], options);
}

export function process_scrolled_to_bottom() {
    if (recent_topics_util.is_visible()) {
        // First, verify the current message list is visible.
        return;
    }

    if (message_lists.current.can_mark_messages_read()) {
        mark_current_list_as_read();
        return;
    }

    // For message lists that don't support marking messages as read
    // automatically, we display a banner offering to let you mark
    // them as read manually, only if there are unreads present.
    if (message_lists.current.has_unread_messages()) {
        unread_ui.notify_messages_remain_unread();
    }
}

// If we ever materially change the algorithm for this function, we
// may need to update notifications.received_messages as well.
export function process_visible() {
    if (message_viewport.is_visible_and_focused() && message_viewport.bottom_message_visible()) {
        process_scrolled_to_bottom();
    }
}

export function mark_current_list_as_read(options) {
    notify_server_messages_read(message_lists.current.all_messages(), options);
}

export function mark_stream_as_read(stream_id, cont) {
    channel.post({
        url: "/json/mark_stream_as_read",
        data: {stream_id},
        success: cont,
    });
}

export function mark_topic_as_read(stream_id, topic, cont) {
    channel.post({
        url: "/json/mark_topic_as_read",
        data: {stream_id, topic_name: topic},
        success: cont,
    });
}

export function mark_pm_as_read(user_ids_string) {
    // user_ids_string is a stringified list of user ids which are
    // participants in the conversation other than the current
    // user. Eg: "123,124" or "123"
    const unread_msg_ids = unread.get_msg_ids_for_user_ids_string(user_ids_string);
    message_flags.mark_as_read(unread_msg_ids);
}
