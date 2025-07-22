import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_confirm_mark_messages_as_read from "../templates/confirm_dialog/confirm_mark_all_as_read.hbs";
import render_confirm_mark_as_unread_from_here from "../templates/confirm_dialog/confirm_mark_as_unread_from_here.hbs";
import render_inline_decorated_channel_name from "../templates/inline_decorated_channel_name.hbs";
import render_skipped_marking_unread from "../templates/skipped_marking_unread.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as feedback_widget from "./feedback_widget.ts";
import {Filter} from "./filter.ts";
import {$t, $t_html} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as message_flags from "./message_flags.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as message_store from "./message_store.ts";
import * as message_viewport from "./message_viewport.ts";
import * as modals from "./modals.ts";
import * as overlays from "./overlays.ts";
import * as people from "./people.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import type {MessageDetails} from "./server_event_types.ts";
import type {NarrowTerm} from "./state_data.ts";
import * as sub_store from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";
import * as unread from "./unread.ts";
import * as unread_ui from "./unread_ui.ts";
import * as util from "./util.ts";
import * as watchdog from "./watchdog.ts";

let loading_indicator_displayed = false;
let unsubscribed_ignored_channels: number[] = [];

// We might want to use a slightly smaller batch for the first
// request, because empirically, the first request can be
// significantly slower, likely due to the database warming up its
// cache with your UserMessage rows. We don't do that, just because
// the progress indicator experience of 1000, 3000, etc. feels weird.
const INITIAL_BATCH_SIZE = 1000;
const FOLLOWUP_BATCH_SIZE = 1000;

// Minimum count of affected messages required to trigger the confirmation
// dialog when marking messages as unread in an interleaved narrow.
// When the last message in the narrow is fetched, the exact count is known,
// otherwise we use the lower bound count.
const MIN_MARK_AS_UNREAD_COUNT_KNOWN = 50;
const MIN_MARK_AS_UNREAD_COUNT_LOWER_BOUND = 10;
const UNREAD_COUNT_STEP_SIZE = 25;

// When you start Zulip, window_focused should be true, but it might not be the
// case after a server-initiated reload.
let window_focused = document.hasFocus();

// Since there's a database index on is:unread, it's a fast
// search query and thus worth including here as an optimization.),
const all_unread_messages_narrow = [{operator: "is", operand: "unread", negated: false}];

export function is_window_focused(): boolean {
    return window_focused;
}

export function confirm_mark_messages_as_read(): void {
    const html_body = render_confirm_mark_messages_as_read();

    const modal_id = confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Choose messages to mark as read"}),
        html_body,
        on_click() {
            handle_mark_messages_as_read(modal_id);
        },
        loading_spinner: true,
    });

    // When the user clicks on "Mark messages as read," the dialog box opens with a
    // dropdown that, by default, displays the count of unread messages in
    // topics that the user does not follow.
    const default_messages_count = unread.get_counts().unfollowed_topic_unread_messages_count;
    $("#message_count").text(get_message_count_text(default_messages_count));

    // When the user selects another option from the dropdown, this section is executed.
    $("#mark_as_read_option").on("change", function () {
        const selected_option = $(this).val();
        let messages_count;
        if (selected_option === "muted_topics") {
            messages_count = unread.get_counts().muted_topic_unread_messages_count;
        } else if (selected_option === "topics_not_followed") {
            messages_count = unread.get_counts().unfollowed_topic_unread_messages_count;
        } else {
            messages_count = unread.get_unread_message_count();
        }
        $("#message_count").text(get_message_count_text(messages_count));
    });
}

const update_flags_for_narrow_response_schema = z.object({
    processed_count: z.number(),
    updated_count: z.number(),
    first_processed_id: z.nullable(z.number()),
    last_processed_id: z.nullable(z.number()),
    found_oldest: z.boolean(),
    found_newest: z.boolean(),
    ignored_because_not_subscribed_channels: z.array(z.number()),
});

const update_flags_for_response_schema = z.object({
    ignored_because_not_subscribed_channels: z.array(z.number()),
});

function handle_skipped_unsubscribed_streams(
    ignored_because_not_subscribed_channels: number[],
): void {
    if (ignored_because_not_subscribed_channels.length > 0) {
        // Zulip has an invariant that all unread messages must be in streams
        // the user is subscribed to. Notify the user if messages from
        // unsubscribed streams are ignored by the server.
        const stream_names_with_privacy_symbol_html = ignored_because_not_subscribed_channels.map(
            (stream_id) => {
                const stream = sub_store.get(stream_id);
                const decorated_channel_name = render_inline_decorated_channel_name({stream});
                return `<span class="white-space-nowrap">${decorated_channel_name}</span>`;
            },
        );

        const populate: (element: JQuery) => void = ($container) => {
            const formatted_stream_list_text = util.format_array_as_list(
                stream_names_with_privacy_symbol_html,
                "long",
                "conjunction",
            );
            const rendered_html = render_skipped_marking_unread({
                streams: formatted_stream_list_text,
            });
            $container.html(rendered_html);
        };

        const title_text = $t({defaultMessage: "Skipped unsubscribed channels"});

        feedback_widget.show({
            populate,
            title_text,
        });
    }
}

export function get_message_count_text(count: number): string {
    if (unread.old_unreads_missing) {
        return $t(
            {
                defaultMessage: "{count}+ messages will be marked as read.",
            },
            {count},
        );
    }
    return $t(
        {
            defaultMessage:
                "{count, plural, one {# message} other {# messages}} will be marked as read.",
        },
        {count},
    );
}

function bulk_update_read_flags_for_narrow(
    narrow: NarrowTerm[],
    op: "add" | "remove",
    {
        // We use an anchor of "oldest", not "first_unread", because
        // "first_unread" will be the oldest non-muted unread message,
        // which would result in muted unreads older than the first
        // unread not being processed.
        anchor = "oldest",
        messages_read_till_now = 0,
        num_after = INITIAL_BATCH_SIZE,
    }: {
        anchor?: "newest" | "oldest" | "first_unread" | number;
        messages_read_till_now?: number;
        num_after?: number;
    } = {},
    caller_modal_id?: string,
): void {
    let response_html;
    const terms_with_integer_channel_id = narrow.map((term) => {
        if (term.operator === "channel") {
            return {
                ...term,
                operand: Number.parseInt(term.operand, 10),
            };
        }
        return term;
    });
    const request = {
        anchor,
        // anchor="oldest" is an anchor ID lower than any valid
        // message ID; and follow-up requests will have already
        // processed the anchor ID, so we just want this to be
        // unconditionally false.
        include_anchor: false,
        num_before: 0,
        num_after,
        op,
        flag: "read",
        narrow: JSON.stringify(terms_with_integer_channel_id),
    };
    void channel.post({
        url: "/json/messages/flags/narrow",
        data: request,
        success(raw_data) {
            const data = update_flags_for_narrow_response_schema.parse(raw_data);
            messages_read_till_now += data.updated_count;

            if (!data.found_newest) {
                assert(data.last_processed_id !== null);
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

                bulk_update_read_flags_for_narrow(
                    narrow,
                    op,
                    {
                        anchor: data.last_processed_id,
                        messages_read_till_now,
                        num_after: FOLLOWUP_BATCH_SIZE,
                    },
                    caller_modal_id,
                );
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

                if (caller_modal_id) {
                    modals.close_if_open(caller_modal_id);
                }

                // We just marked all the messages in this narrow as read.
                // Hide the unread banner and resume reading if possible.
                //
                // We exclude the `is:unread` term that was included
                // by the caller for checking whether weot re-enable
                // resume-reading.
                //
                // TODO: Ideally, we'd change the calling convention
                // to avoid this hacky code, which may behave
                // incorrectly for some `is:unread` search views.
                const filter_terms = narrow.filter(
                    (term) =>
                        !(
                            term.operator === "is" &&
                            term.operand === "unread" &&
                            term.negated === false
                        ),
                );
                // Current narrow may have "with" or "near" operator around a message
                // target which we would want to ignore for bulk reading a message list.
                if (
                    message_lists.current?.data.filter.equals(new Filter(filter_terms), [
                        "with",
                        "near",
                    ])
                ) {
                    message_lists.current?.resume_reading();
                    unread_ui.hide_unread_banner();
                }
            }
        },
        error(xhr) {
            let parsed;
            if (xhr.readyState === 0) {
                // client cancelled the request
            } else if (
                (parsed = z
                    .object({code: z.literal("RATE_LIMIT_HIT"), ["retry-after"]: z.number()})
                    .safeParse(xhr.responseJSON)).success
            ) {
                // If we hit the rate limit, just continue without showing any error.
                const milliseconds_to_wait = 1000 * parsed.data["retry-after"];
                setTimeout(() => {
                    bulk_update_read_flags_for_narrow(
                        narrow,
                        op,
                        {
                            anchor,
                            messages_read_till_now,
                            num_after,
                        },
                        caller_modal_id,
                    );
                }, milliseconds_to_wait);
            } else {
                // TODO: Ideally this would be a ui_report.error();
                // the user needs to know that our operation failed.
                const operation = op === "add" ? "read" : "unread";
                blueslip.error(`Failed to mark messages as ${operation}`, {
                    status: xhr.status,
                    body: xhr.responseText,
                });
                if (caller_modal_id && modals.is_active(caller_modal_id)) {
                    dialog_widget.hide_dialog_spinner();
                }
            }
        },
    });
}

function handle_mark_messages_as_read(modal_id: string): void {
    const selected_option = $("#mark_as_read_option").val();

    switch (selected_option) {
        case "muted_topics": {
            mark_muted_topic_messages_as_read(modal_id);
            break;
        }
        case "topics_not_followed": {
            mark_unfollowed_topic_messages_as_read(modal_id);
            break;
        }
        case "all_messages": {
            mark_all_as_read(modal_id);
            break;
        }
        default: {
            assert(false, `Invalid mark_as_read_option: ${String(selected_option)}`);
        }
    }
}

function process_newly_read_message(
    message: Message,
    options: {from?: "pointer" | "server"},
): void {
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.view.show_message_as_read(message, options);
    }
    desktop_notifications.close_notification(message);
    recent_view_ui.update_topic_unread_count(message);
}

export function mark_as_unread_from_here(message_id: number): void {
    assert(message_lists.current !== undefined);
    const current_filter = message_lists.current.data.filter;
    const narrow = current_filter.get_stringified_narrow_for_server_query();
    message_lists.current.prevent_reading();

    const has_found_newest = message_lists.current.data.fetch_status.has_found_newest();
    const may_contain_multiple_conversations = current_filter.may_contain_multiple_conversations();

    // If we are certain we have all messages below the current point,
    // or believe we're offline, then we prefer the locally available
    // message IDs over asking the server to mark the view as unread.
    //
    // Using a list of message IDs is faster for small sets and also
    // is the only option that makes sense if we're offline: Just
    // process the messages the user can see, and not some that might
    // be below them in the view but are unavailable.
    const likely_offline = watchdog.suspects_user_is_offline();
    const prefer_local_ids = has_found_newest || watchdog.suspects_user_is_offline();

    const locally_available_matching_message_ids = message_lists.current
        .all_messages()
        .filter((msg) => msg.id >= message_id && !msg.unread)
        .map((msg) => msg.id);
    const locally_available_message_count = locally_available_matching_message_ids.length;
    let display_count: string;

    function do_mark_unread(message_ids_to_update: number[] | undefined): void {
        // If we have already fully fetched the current view, we can
        // send the server the set of IDs to update, rather than
        // updating on the basis of the narrow.
        if (
            message_ids_to_update !== undefined &&
            (message_ids_to_update.length < 200 || likely_offline)
        ) {
            do_mark_unread_by_ids(message_ids_to_update);
        } else {
            const include_anchor = true;
            const messages_marked_unread_till_now = 0;
            const num_after = INITIAL_BATCH_SIZE - 1;
            do_mark_unread_by_narrow(
                message_id,
                include_anchor,
                messages_marked_unread_till_now,
                num_after,
                narrow,
            );
        }
    }

    if (!may_contain_multiple_conversations) {
        // Never display a prompt in a conversation view.
        if (prefer_local_ids) {
            do_mark_unread(locally_available_matching_message_ids);
        } else {
            do_mark_unread(undefined);
        }
        return;
    } else if (prefer_local_ids) {
        // Since we have the anchor message ID and the newest
        // messages, we know exactly which messages to mark as unread.
        if (locally_available_matching_message_ids.length < MIN_MARK_AS_UNREAD_COUNT_KNOWN) {
            // If the number is sufficiently small, we proceed without
            // a confirmation dialog.
            do_mark_unread(locally_available_matching_message_ids);
            return;
        }

        display_count = locally_available_message_count.toString();
    } else if (locally_available_message_count < UNREAD_COUNT_STEP_SIZE) {
        // TODO: This logic should have a case for where we're
        // offline, and skip the prompt in interleaved views in that
        // case.
        display_count = locally_available_message_count.toString();
    } else {
        // Otherwise, we round down to the nearest
        // UNREAD_COUNT_STEP_SIZE and display as, e.g., `25+`.
        const rounded_count =
            Math.floor(locally_available_message_count / UNREAD_COUNT_STEP_SIZE) *
            UNREAD_COUNT_STEP_SIZE;
        display_count = `${rounded_count}+`;
    }

    const context = {
        // If we don't know how many messages will be affected, but
        // can't prove the number is more than 10, we avoid showing a
        // count, since it just seems weird to say "3+ messages will
        // be marked as read".
        //
        // It's not obvious this case is worth having special strings
        // for, given how unlikely it is. A sample scenario is that
        // we're be that we're near the fetched bottom of a /near/1
        // search view where can_apply_locally is false, which will
        // have triggered a request for the next batch of messages
        // from the server, but that request has not returned. But it
        // may happen more offline if the client is intermittantly
        // offline.
        show_message_count: locally_available_message_count >= MIN_MARK_AS_UNREAD_COUNT_LOWER_BOUND,
        count: display_count,
    };

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Mark messages as unread?"}),
        html_body: render_confirm_mark_as_unread_from_here(context),
        on_click() {
            if (prefer_local_ids) {
                do_mark_unread(locally_available_matching_message_ids);
            } else {
                do_mark_unread(undefined);
            }
        },
    });
}

function do_mark_unread_by_narrow(
    message_id: number,
    include_anchor = true,
    messages_marked_unread_till_now = 0,
    num_after = INITIAL_BATCH_SIZE - 1,
    narrow: string,
): void {
    const opts = {
        anchor: message_id,
        include_anchor,
        num_before: 0,
        num_after,
        narrow,
        op: "remove",
        flag: "read",
    };
    void channel.post({
        url: "/json/messages/flags/narrow",
        data: opts,
        success(raw_data) {
            const data = update_flags_for_narrow_response_schema.parse(raw_data);
            messages_marked_unread_till_now += data.updated_count;
            unsubscribed_ignored_channels = [
                ...new Set([
                    ...unsubscribed_ignored_channels,
                    ...data.ignored_because_not_subscribed_channels,
                ]),
            ];
            if (!data.found_newest) {
                assert(data.last_processed_id !== null);
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
                do_mark_unread_by_narrow(
                    data.last_processed_id,
                    false,
                    messages_marked_unread_till_now,
                    FOLLOWUP_BATCH_SIZE,
                    narrow,
                );
            } else {
                if (loading_indicator_displayed) {
                    finish_loading(messages_marked_unread_till_now);
                }
                if (unsubscribed_ignored_channels.length > 0) {
                    handle_skipped_unsubscribed_streams(unsubscribed_ignored_channels);
                    unsubscribed_ignored_channels = [];
                }
            }
        },
        error(xhr) {
            handle_mark_unread_from_here_error(xhr, {
                retry() {
                    do_mark_unread_by_narrow(
                        message_id,
                        include_anchor,
                        messages_marked_unread_till_now,
                        num_after,
                        narrow,
                    );
                },
            });
        },
    });
}

function do_mark_unread_by_ids(message_ids_to_update: number[]): void {
    // TODO: Add support for locally echoing when we're offline.
    void channel.post({
        url: "/json/messages/flags",
        data: {messages: JSON.stringify(message_ids_to_update), op: "remove", flag: "read"},
        success(raw_data) {
            if (loading_indicator_displayed) {
                finish_loading(message_ids_to_update.length);
            }
            const data = update_flags_for_response_schema.parse(raw_data);
            const ignored_because_not_subscribed_channels =
                data.ignored_because_not_subscribed_channels;
            if (ignored_because_not_subscribed_channels.length > 0) {
                handle_skipped_unsubscribed_streams(ignored_because_not_subscribed_channels);
            }
        },
        error(xhr) {
            handle_mark_unread_from_here_error(xhr, {
                retry() {
                    do_mark_unread_by_ids(message_ids_to_update);
                },
            });
        },
    });
}

function finish_loading(messages_marked_unread_till_now: number): void {
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

function handle_mark_unread_from_here_error(
    xhr: JQuery.jqXHR<unknown>,
    {retry}: {retry: () => void},
): void {
    let parsed;
    if (xhr.readyState === 0) {
        // client cancelled the request
    } else if (
        (parsed = z
            .object({code: z.literal("RATE_LIMIT_HIT"), ["retry-after"]: z.number()})
            .safeParse(xhr.responseJSON)).success
    ) {
        // If we hit the rate limit, just continue without showing any error.
        const milliseconds_to_wait = 1000 * parsed.data["retry-after"];
        setTimeout(retry, milliseconds_to_wait);
    } else {
        // TODO: Ideally, this case would communicate the
        // failure to the user, with some manual retry
        // offered, since the most likely cause is a 502.
        blueslip.error("Unexpected error marking messages as unread", {
            status: xhr.status,
            body: xhr.responseText,
        });
    }
}

export function process_read_messages_event(message_ids: number[]): void {
    /*
        This code has a lot in common with notify_server_messages_read,
        but there are subtle differences due to the fact that the
        server can tell us about unread messages that we didn't
        actually read locally (and which we may not have even
        loaded locally).
    */
    const options = {from: "server" as const};

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

    if (message_lists.current !== undefined && !message_lists.current.has_unread_messages()) {
        unread_ui.hide_unread_banner();
    }

    unread_ui.update_unread_counts();
}

export function process_unread_messages_event({
    message_ids,
    message_details,
}: {
    message_ids: number[];
    message_details: MessageDetails;
}): void {
    // This is the reverse of process_read_messages_event.
    message_ids = unread.get_read_message_ids(message_ids);
    if (message_ids.length === 0) {
        return;
    }

    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        const message_info = message_details[message_id];
        assert(message_info !== undefined);
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

        if (message_info.type === "private") {
            unread.process_unread_message({
                id: message_id,
                mentioned: message_info.mentioned,
                mentioned_me_directly,
                type: "private",
                unread: true,
                user_ids_string: people.pm_lookup_key_from_user_ids(message_info.user_ids),
            });
        } else if (message_info.type === "stream") {
            unread.process_unread_message({
                id: message_id,
                mentioned: message_info.mentioned,
                mentioned_me_directly,
                stream_id: message_info.stream_id,
                topic: message_info.topic,
                type: "stream",
                unread: true,
            });
        } else {
            message_info satisfies never;
        }
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
export function notify_server_messages_read(
    messages: Message[],
    options: {from?: "pointer" | "server"} = {},
): void {
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

export function notify_server_message_read(
    message: Message,
    options?: {from?: "pointer" | "server"},
): void {
    notify_server_messages_read([message], options);
}

function process_scrolled_to_bottom(): void {
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
export function process_visible(): void {
    if (
        message_lists.current !== undefined &&
        viewport_is_visible_and_focused() &&
        message_viewport.bottom_rendered_message_visible() &&
        message_lists.current.view.is_fetched_end_rendered()
    ) {
        process_scrolled_to_bottom();
    }
}

export function mark_stream_as_read(stream_id: number): void {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "is", operand: "unread", negated: false},
            {operator: "channel", operand: stream_id.toString()},
        ],
        "add",
    );
}

export function mark_stream_as_unread(stream_id: number): void {
    bulk_update_read_flags_for_narrow(
        [{operator: "channel", operand: stream_id.toString()}],
        "remove",
    );
}

export function mark_topic_as_read(stream_id: number, topic: string): void {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "is", operand: "unread", negated: false},
            {operator: "channel", operand: stream_id.toString()},
            {operator: "topic", operand: topic},
        ],
        "add",
    );
}

export function mark_topic_as_unread(stream_id: number, topic: string): void {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "channel", operand: stream_id.toString()},
            {operator: "topic", operand: topic},
        ],
        "remove",
    );
}

export function mark_all_as_read(modal_id?: string): void {
    bulk_update_read_flags_for_narrow(all_unread_messages_narrow, "add", {}, modal_id);
}

export function mark_muted_topic_messages_as_read(modal_id?: string): void {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "is", operand: "unread", negated: false},
            {operator: "is", operand: "muted", negated: false},
        ],
        "add",
        {},
        modal_id,
    );
}

export function mark_unfollowed_topic_messages_as_read(modal_id?: string): void {
    bulk_update_read_flags_for_narrow(
        [
            {operator: "is", operand: "unread", negated: false},
            {operator: "is", operand: "followed", negated: true},
            {operator: "is", operand: "dm", negated: true},
        ],
        "add",
        {},
        modal_id,
    );
}

export function mark_pm_as_read(user_ids_string: string): void {
    // user_ids_string is a stringified list of user ids which are
    // participants in the conversation other than the current
    // user. Eg: "123,124" or "123"
    const unread_msg_ids = unread.get_msg_ids_for_user_ids_string(user_ids_string);
    message_flags.mark_as_read(unread_msg_ids);
}

export function viewport_is_visible_and_focused(): boolean {
    if (
        overlays.any_active() ||
        modals.any_active() ||
        !is_window_focused() ||
        $("#message_feed_container").css("display") === "none"
    ) {
        return false;
    }
    return true;
}

export function initialize(): void {
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
