import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import render_confirm_mark_all_as_read from "../templates/confirm_dialog/confirm_mark_all_as_read.hbs";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as desktop_notifications from "./desktop_notifications";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import * as loading from "./loading";
import * as message_flags from "./message_flags";
import * as message_lists from "./message_lists";
import * as message_store from "./message_store";
import * as message_viewport from "./message_viewport";
import * as modals from "./modals";
import * as overlays from "./overlays";
import * as people from "./people";
import * as recent_view_ui from "./recent_view_ui";
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

// When you start Zulip, window_focused should be true, but it might not be the
// case after a server-initiated reload.
let window_focused = document.hasFocus && document.hasFocus();

// Since there's a database index on is:unread, it's a fast
// search query and thus worth including here as an optimization.),
const all_unread_messages_narrow = [{operator: "is", operand: "unread", negated: false}];

export function is_window_focused() {
    return window_focused;
}

export function confirm_mark_all_as_read() {
    const html_body = render_confirm_mark_all_as_read();

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Mark all messages as read?"}),
        html_body,
        on_click: mark_all_as_read,
        loading_spinner: true,
    });
}

function bulk_update_read_flags_for_narrow(narrow, op, args = {}) {
    let response_html;
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
        op,
        flag: "read",
        narrow: JSON.stringify(narrow),
    };
    channel.post({
        url: "/json/messages/flags/narrow",
        data: request,
        success(data) {
            const messages_read_till_now = args.messages_read_till_now + data.updated_count;

            if (!data.found_newest) {
                // If we weren't able to make everything as read in a
                // single API request, then show a loading indicator.
                if (op === "add") {
                    response_html = $t_html(
                        {
                            defaultMessage:
                                "{N, plural, one {Working… {N} message marked as read so far.} other {Working… {N} messages marked as read so far.}}",
                        },
                        {N: messages_read_till_now},
                    );
                } else {
                    response_html = $t_html(
                        {
                            defaultMessage:
                                "{N, plural, one {Working… {N} message marked as unread so far.} other {Working… {N} messages marked as unread so far.}}",
                        },
                        {N: messages_read_till_now},
                    );
                }
                ui_report.loading(response_html, $("#request-progress-status-banner"));
                if (!loading_indicator_displayed) {
                    loading.make_indicator(
                        $("#request-progress-status-banner .loading-indicator"),
                        {abs_positioned: true},
                    );
                    loading_indicator_displayed = true;
                }

                bulk_update_read_flags_for_narrow(narrow, op, {
                    ...args,
                    anchor: data.last_processed_id,
                    messages_read_till_now,
                    num_after: FOLLOWUP_BATCH_SIZE,
                });
            } else {
                if (loading_indicator_displayed) {
                    // Only show the success message if a progress banner was displayed.
                    if (op === "add") {
                        response_html = $t_html(
                            {
                                defaultMessage:
                                    "{N, plural, one {Done! {N} message marked as read.} other {Done! {N} messages marked as read.}}",
                            },
                            {N: messages_read_till_now},
                        );
                    } else {
                        response_html = $t_html(
                            {
                                defaultMessage:
                                    "{N, plural, one {Done! {N} message marked as unread.} other {Done! {N} messages marked as unread.}}",
                            },
                            {N: messages_read_till_now},
                        );
                    }
                    ui_report.loading(response_html, $("#request-progress-status-banner"), true);
                    loading_indicator_displayed = false;
                }

                if (_.isEqual(narrow, all_unread_messages_narrow) && unread.old_unreads_missing) {
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
            dialog_widget.close();
        },
        error(xhr) {
            if (xhr.readyState === 0) {
                // client cancelled the request
            } else if (xhr.responseJSON?.code === "RATE_LIMIT_HIT") {
                // If we hit the rate limit, just continue without showing any error.
                const milliseconds_to_wait = 1000 * xhr.responseJSON["retry-after"];
                setTimeout(
                    () => bulk_update_read_flags_for_narrow(narrow, op, args),
                    milliseconds_to_wait,
                );
            } else {
                // TODO: Ideally this would be a ui_report.error();
                // the user needs to know that our operation failed.
                const operation = op === "add" ? "read" : "unread";
                blueslip.error(`Failed to mark messages as ${operation}`, {
                    status: xhr.status,
                    body: xhr.responseText,
                });
            }
            dialog_widget.hide_dialog_spinner();
        },
    });
}

function process_newly_read_message(message, options) {
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.view.show_message_as_read(message, options);
    }
    desktop_notifications.close_notification(message);
    recent_view_ui.update_topic_unread_count(message);
}

export function mark_as_unread_from_here(
    message_id,
    include_anchor = true,
    messages_marked_unread_till_now = 0,
    num_after = INITIAL_BATCH_SIZE - 1,
    narrow,
) {
    assert(message_lists.current !== undefined);
    if (narrow === undefined) {
        narrow = JSON.stringify(message_lists.current.data.filter.terms());
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
            if (xhr.readyState === 0) {
                // client cancelled the request
            } else if (xhr.responseJSON?.code === "RATE_LIMIT_HIT") {
                // If we hit the rate limit, just continue without showing any error.
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
                blueslip.error("Unexpected error marking messages as unread", {
                    status: xhr.status,
                    body: xhr.responseText,
                });
            }
        },
    });
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
    // This is the reverse of process_read_messages_event.
    message_ids = unread.get_read_message_ids(message_ids);
    if (message_ids.length === 0) {
        return;
    }

    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        const message_info = message_details[message_id];
        let mentioned_me_directly;

        if (message) {
            message.unread = true;
            mentioned_me_directly = message.mentioned_me_directly;
        } else {
            // BUG: If we don't have a copy of the message locally, we
            // have no way to correctly compute whether the mentions
            // are personal mentions or wildcard mentions, because
            // message_info doesn't contain that information... so we
            // guess that it's a personal mention.
            //
            // This is a correctness bug, but is likely very rare: We
            // will have a copy of all unread messages locally once
            // the app has finished the message_fetch backfill
            // sequence (and also will certainly have this message if
            // this is the client where the "Mark as unread" action
            // was taken). Further, the distinction is only important
            // for mentions in muted streams, where we count direct
            // mentions as important enough to promote, and wildcard
            // mentions as not.
            //
            // A possible fix would be to just fetch the fully message
            // from the API here, but the right fix likely requires API changes.
            mentioned_me_directly = message_info.mentioned;
        }

        let user_ids_string;

        if (message_info.type === "private") {
            user_ids_string = people.pm_lookup_key_from_user_ids(message_info.user_ids);
        }

        unread.process_unread_message({
            id: message_id,
            mentioned: message_info.mentioned,
            mentioned_me_directly,
            stream_id: message_info.stream_id,
            topic: message_info.topic,
            type: message_info.type,
            unread: true,
            user_ids_string,
        });
    }

    // Update UI for the messages marked as unread.
    for (const list of message_lists.all_rendered_message_lists()) {
        list.view.show_messages_as_unread(message_ids);
    }

    recent_view_ui.complete_rerender();

    if (
        message_lists.current !== undefined &&
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
        unread.mark_as_read(message.id);
        process_newly_read_message(message, options);
    }

    unread_ui.update_unread_counts();
}

export function notify_server_message_read(message, options) {
    notify_server_messages_read([message], options);
}

function process_scrolled_to_bottom() {
    if (message_lists.current === undefined) {
        // First, verify that user is narrowed to a list of messages.
        return;
    }

    if (message_lists.current.can_mark_messages_read()) {
        // Mark all the messages in this message feed as read.
        //
        // Important: We have not checked definitively whether there
        // are further messages that we're waiting on the server to
        // return that would appear below the visible part of the
        // feed, so it would not be correct to instead ask the server
        // to mark all messages matching this entire narrow as read.
        notify_server_messages_read(message_lists.current.all_messages());
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
// may need to update message_notifications.received_messages as well.
export function process_visible() {
    if (
        message_lists.current !== undefined &&
        viewport_is_visible_and_focused() &&
        message_viewport.bottom_rendered_message_visible() &&
        message_lists.current.view.is_fetched_end_rendered()
    ) {
        process_scrolled_to_bottom();
    }
}

export function mark_stream_as_read(stream_id) {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "is", operand: "unread", negated: false},
            {operator: "channel", operand: stream_id},
        ],
        "add",
        {
            stream_id,
        },
    );
}

export function mark_topic_as_read(stream_id, topic) {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "is", operand: "unread", negated: false},
            {operator: "channel", operand: stream_id},
            {operator: "topic", operand: topic},
        ],
        "add",
        {
            stream_id,
            topic,
        },
    );
}

export function mark_topic_as_unread(stream_id, topic) {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "channel", operand: stream_id},
            {operator: "topic", operand: topic},
        ],
        "remove",
        {
            stream_id,
            topic,
        },
    );
}

export function mark_all_as_read() {
    bulk_update_read_flags_for_narrow(all_unread_messages_narrow, "add");
}

export function mark_pm_as_read(user_ids_string) {
    // user_ids_string is a stringified list of user ids which are
    // participants in the conversation other than the current
    // user. Eg: "123,124" or "123"
    const unread_msg_ids = unread.get_msg_ids_for_user_ids_string(user_ids_string);
    message_flags.mark_as_read(unread_msg_ids);
}

export function viewport_is_visible_and_focused() {
    if (
        overlays.any_active() ||
        modals.any_active() ||
        !is_window_focused() ||
        !$("#message_feed_container").is(":visible")
    ) {
        return false;
    }
    return true;
}

export function initialize() {
    $(window)
        .on("focus", () => {
            window_focused = true;

            // Update many places on the DOM to reflect unread
            // counts.
            process_visible();
        })
        .on("blur", () => {
            window_focused = false;
        });
}
