import $ from "jquery";

import {all_messages_data} from "./all_messages_data";
import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as huddle_data from "./huddle_data";
import * as message_feed_loading from "./message_feed_loading";
import * as message_feed_top_notices from "./message_feed_top_notices";
import * as message_helper from "./message_helper";
import * as message_lists from "./message_lists";
import * as message_util from "./message_util";
import * as narrow_banner from "./narrow_banner";
import {page_params} from "./page_params";
import * as people from "./people";
import * as recent_view_ui from "./recent_view_ui";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as ui_report from "./ui_report";

let first_messages_fetch = true;
export let initial_narrow_pointer;
export let initial_narrow_offset;

const consts = {
    // Because most views are centered on the first unread message,
    // the user has a higher probability of wantingto scroll down
    // than, so extra fetched history after the cursor is more likely
    // to be used and thus worth more to fetch.
    //
    // It's rare to have hundreds of unreads after the cursor, asking
    // for a larger number of messages after the cursor is cheap.
    narrow_before: 60,
    narrow_after: 150,
    initial_backfill_fetch_size: 1000,
    maximum_initial_backfill_size: 15000,
    narrowed_view_backward_batch_size: 100,
    narrowed_view_forward_batch_size: 100,
    recent_view_fetch_more_batch_size: 2000,
    catch_up_batch_size: 2000,
    // Delay in milliseconds after processing a catch-up request
    // before sending the next one.
    catch_up_backfill_delay: 150,
};

function process_result(data, opts) {
    let messages = data.messages;

    messages = messages.map((message) => message_helper.process_new_message(message));
    const has_found_oldest = opts.msg_list?.data.fetch_status.has_found_oldest() ?? false;
    const has_found_newest = opts.msg_list?.data.fetch_status.has_found_newest() ?? false;

    // In some rare situations, we expect to discover new unread
    // messages not tracked in unread.ts during this fetching process.
    message_util.do_unread_count_updates(messages, true);

    if (messages.length !== 0) {
        if (opts.msg_list) {
            // Since this adds messages to the MessageList and renders MessageListView,
            // we don't need to call it if msg_list was not defined by the caller.
            message_util.add_old_messages(messages, opts.msg_list);
        } else {
            opts.msg_list_data.add_messages(messages);
        }
    }

    huddle_data.process_loaded_messages(messages);
    stream_list.update_streams_sidebar();
    stream_list.maybe_scroll_narrow_into_view();

    if (
        message_lists.current !== undefined &&
        opts.msg_list === message_lists.current &&
        opts.msg_list.narrowed &&
        opts.msg_list.visibly_empty()
    ) {
        // The view appears to be empty. However, because in stream
        // narrows, we fetch messages including those that might be
        // hidden by topic muting, it's possible that we received all
        // the messages we requested, and all of them are in muted
        // topics, but there are older messages for this stream that
        // we need to ask the server for.
        if (has_found_oldest && has_found_newest) {
            // Even after loading more messages, we have
            // no messages to display in this narrow.
            narrow_banner.show_empty_narrow_message();
        }

        if (opts.num_before > 0 && !has_found_oldest) {
            maybe_load_older_messages({msg_list: opts.msg_list});
        }
        if (opts.num_after > 0 && !has_found_newest) {
            maybe_load_newer_messages({msg_list: opts.msg_list});
        }
    }

    if (opts.cont !== undefined) {
        opts.cont(data, opts);
    }
}

function get_messages_success(data, opts) {
    const update_loading_indicator =
        message_lists.current !== undefined && opts.msg_list === message_lists.current;
    const msg_list_data = opts.msg_list_data ?? opts.msg_list.data;
    const has_found_newest = msg_list_data.fetch_status.has_found_newest();
    const has_found_oldest = msg_list_data.fetch_status.has_found_oldest();

    const current_fetch_found_oldest = !has_found_oldest && data.found_oldest;
    const current_fetch_found_newest = !has_found_newest && data.found_newest;

    if (opts.num_before > 0 || current_fetch_found_oldest) {
        msg_list_data.fetch_status.finish_older_batch({
            update_loading_indicator,
            found_oldest: data.found_oldest,
            history_limited: data.history_limited,
        });
        message_feed_top_notices.update_top_of_narrow_notices(opts.msg_list);
    }

    if (opts.num_after > 0 || current_fetch_found_newest) {
        opts.fetch_again = msg_list_data.fetch_status.finish_newer_batch(data.messages, {
            update_loading_indicator,
            found_newest: data.found_newest,
        });
    }

    if (opts.msg_list && opts.msg_list.narrowed && opts.msg_list !== message_lists.current) {
        // We unnarrowed before receiving new messages so
        // don't bother processing the newly arrived messages.
        return;
    }
    if (!data) {
        // The server occasionally returns no data during a
        // restart.  Ignore those responses and try again
        setTimeout(() => {
            load_messages(opts);
        }, 0);
        return;
    }

    process_result(data, opts);
}

// This function modifies the data.narrow filters to use integer IDs
// instead of strings if it is supported. We currently don't set or
// convert user emails to user IDs directly in the Filter code
// because doing so breaks the app in various modules that expect a
// string of user emails.
function handle_operators_supporting_id_based_api(data) {
    const operators_supporting_ids = new Set(["dm", "pm-with"]);
    const operators_supporting_id = new Set([
        "id",
        "stream",
        "sender",
        "group-pm-with",
        "dm-including",
    ]);

    if (data.narrow === undefined) {
        return data;
    }

    data.narrow = JSON.parse(data.narrow);
    data.narrow = data.narrow.map((filter) => {
        if (operators_supporting_ids.has(filter.operator)) {
            filter.operand = people.emails_strings_to_user_ids_array(filter.operand);
        }

        if (operators_supporting_id.has(filter.operator)) {
            if (filter.operator === "id") {
                // The message ID may not exist locally,
                // so send the filter to the server as is.
                return filter;
            }

            if (filter.operator === "stream") {
                const stream_id = stream_data.get_stream_id(filter.operand);
                if (stream_id !== undefined) {
                    filter.operand = stream_id;
                }

                return filter;
            }

            // The other operands supporting object IDs all work with user objects.
            const person = people.get_by_email(filter.operand);
            if (person !== undefined) {
                filter.operand = person.user_id;
            }
        }

        return filter;
    });

    data.narrow = JSON.stringify(data.narrow);
    return data;
}

export function load_messages(opts, attempt = 1) {
    if (typeof opts.anchor === "number") {
        // Messages that have been locally echoed messages have
        // floating point temporary IDs, which is intended to be a.
        // completely client-side detail.  We need to round these to
        // the nearest integer before sending a request to the server.
        opts.anchor = opts.anchor.toFixed(0);
    }
    let data = {anchor: opts.anchor, num_before: opts.num_before, num_after: opts.num_after};
    const msg_list_data = opts.msg_list_data ?? opts.msg_list.data;

    if (msg_list_data === undefined) {
        blueslip.error("Message list data is undefined!");
    }

    // This block is a hack; structurally, we want to set
    //   data.narrow = opts.msg_list.data.filter.public_terms()
    //
    // But support for the all_messages_data sharing of data with
    // the combined feed view and the (hacky) page_params.narrow feature
    // requires a somewhat ugly bundle of conditionals.
    if (msg_list_data.filter.is_in_home()) {
        if (page_params.narrow_stream !== undefined) {
            data.narrow = JSON.stringify(page_params.narrow);
        }
        // Otherwise, we don't pass narrow for the combined feed view; this is
        // required to display messages if their muted status changes without a new
        // network request, and so we need the server to send us message history from muted
        // streams and topics even though the combined feed view's in:home
        // operators will filter those.
    } else {
        let terms = msg_list_data.filter.public_terms();
        if (page_params.narrow !== undefined) {
            terms = [...terms, ...page_params.narrow];
        }
        data.narrow = JSON.stringify(terms);
    }

    let update_loading_indicator =
        message_lists.current !== undefined && opts.msg_list === message_lists.current;
    if (opts.num_before > 0) {
        msg_list_data.fetch_status.start_older_batch({
            update_loading_indicator,
        });
    }

    if (opts.num_after > 0) {
        // We hide the bottom loading indicator when we're fetching both top and bottom messages.
        update_loading_indicator = update_loading_indicator && opts.num_before === 0;
        msg_list_data.fetch_status.start_newer_batch({
            update_loading_indicator,
        });
    }

    data.client_gravatar = true;
    data = handle_operators_supporting_id_based_api(data);

    if (page_params.is_spectator) {
        // This is a bit of a hack; ideally we'd unify this logic in
        // some way with the above logic, and not need to do JSON
        // parsing/stringifying here.
        const web_public_narrow = {negated: false, operator: "channels", operand: "web-public"};

        if (!data.narrow) {
            /* For the combined feed, this will be the only operator. */
            data.narrow = JSON.stringify([web_public_narrow]);
        } else {
            // Otherwise, we append the operator.  This logic is not
            // ideal in that in theory an existing `streams:` operator
            // could be present, but not in a useful way.  We don't
            // attempt to validate the narrow is compatible with
            // spectators here; the server will return an error if
            // appropriate.
            data.narrow = JSON.parse(data.narrow);
            data.narrow.push(web_public_narrow);
            data.narrow = JSON.stringify(data.narrow);
        }
    }

    channel.get({
        url: "/json/messages",
        data,
        success(data) {
            if (!$("#connection-error").hasClass("get-events-error")) {
                ui_report.hide_error($("#connection-error"));
            }

            get_messages_success(data, opts);
        },
        error(xhr) {
            if (xhr.status === 400 && !$("#connection-error").hasClass("get-events-error")) {
                // We successfully reached the server, so hide the
                // connection error notice, even if the request failed
                // for other reasons.
                ui_report.hide_error($("#connection-error"));
            }

            if (
                opts.msg_list !== undefined &&
                opts.msg_list !== message_lists.current &&
                opts.msg_list.narrowed
            ) {
                // This fetch was for a narrow, and we unnarrowed
                // before getting an error, so don't bother trying
                // again or doing further processing.
                return;
            }
            if (xhr.status === 400) {
                // Bad request: We probably specified a narrow operator
                // for a nonexistent stream or something.  We shouldn't
                // retry or display a connection error.
                //
                // FIXME: This logic unconditionally ignores the actual JSON
                // error in the xhr status. While we have empty narrow messages
                // for many common errors, and those have nicer HTML formatting,
                // we certainly don't for every possible 400 error.
                message_feed_loading.hide_indicators();

                if (
                    message_lists.current !== undefined &&
                    opts.msg_list === message_lists.current &&
                    opts.msg_list.narrowed &&
                    opts.msg_list.visibly_empty()
                ) {
                    narrow_banner.show_empty_narrow_message();
                }

                // TODO: This should probably do something explicit with
                // `FetchStatus` to mark the message list as not eligible for
                // further fetches. Currently, that happens implicitly via
                // failing to call finish_older_batch / finish_newer_batch
                return;
            }

            ui_report.show_error($("#connection-error"));

            // We need to respect the server's rate-limiting headers, but beyond
            // that, we also want to avoid contributing to a thundering herd if
            // the server is giving us 500s/502s.
            //
            // So we do the maximum of the retry-after header and an exponential
            // backoff with ratio 2 and half jitter. Starts at 1-2s and ends at
            // 16-32s after 5 failures.
            const backoff_scale = Math.min(2 ** attempt, 32);
            const backoff_delay_secs = ((1 + Math.random()) / 2) * backoff_scale;
            let rate_limit_delay_secs = 0;
            if (xhr.status === 429 && xhr.responseJSON?.code === "RATE_LIMIT_HIT") {
                // Add a bit of jitter to the required delay suggested by the
                // server, because we may be racing with other copies of the web
                // app.
                rate_limit_delay_secs = xhr.responseJSON["retry-after"] + Math.random() * 0.5;
            }
            const delay_secs = Math.max(backoff_delay_secs, rate_limit_delay_secs);
            setTimeout(() => {
                load_messages(opts, attempt + 1);
            }, delay_secs * 1000);
        },
    });
}

export function load_messages_for_narrow(opts) {
    load_messages({
        anchor: opts.anchor,
        num_before: consts.narrow_before,
        num_after: consts.narrow_after,
        msg_list: opts.msg_list,
        cont: opts.cont,
    });
}

export function get_backfill_anchor(msg_list_data) {
    const oldest_msg = msg_list_data.first_including_muted();
    if (oldest_msg) {
        return oldest_msg.id;
    }

    return "first_unread";
}

export function get_frontfill_anchor(msg_list) {
    const last_msg = msg_list.data.last_including_muted();

    if (last_msg) {
        return last_msg.id;
    }

    // This fallthrough only occurs in a rare race, where the user
    // navigates to a currently empty narrow, and the `GET /messages`
    // request sees 0 matching messages, but loses the race with a
    // simultaneous `GET /events` request returning a just-sent
    // message matching this narrow. In that case,
    // get_messages_success will see no matching messages, even though
    // we know via `FetchStatus._expected_max_message_id` that we are
    // expecting to see a new message here, and thus
    // `FetchStatus.has_found_newest` remains false.
    //
    // In this situation, we know there are no messages older than the
    // ones we're looking for, so returning "oldest" should correctly
    // allow the follow-up request to find all messages that raced in
    // this way.
    //
    // Can be manually reproduced as follows:
    // * Add a long sleep at the end of `GET /messages` API requests
    //   in the server.
    // * Open two browser windows.
    // * Narrow to an empty topic in the first. You'll see a loading indicator.
    // * In the second window, send a message to the empty topic.
    // * When the first browser window's `GET /messages` request finishes,
    //   this code path will be reached.
    return "oldest";
}

export function maybe_load_older_messages(opts) {
    // This function gets called when you scroll to the top
    // of your window, and you want to get messages older
    // than what the browsers originally fetched.
    const msg_list_data = opts.msg_list_data ?? opts.msg_list.data;
    if (!msg_list_data.fetch_status.can_load_older_messages()) {
        // We may already be loading old messages or already
        // got the oldest one.
        return;
    }

    do_backfill({
        ...opts,
        num_before: opts.recent_view
            ? consts.recent_view_fetch_more_batch_size
            : consts.narrowed_view_backward_batch_size,
    });
}

export function do_backfill(opts) {
    const msg_list_data = opts.msg_list_data ?? opts.msg_list.data;
    const anchor = get_backfill_anchor(msg_list_data);

    // `load_messages` behaves differently for `msg_list` and `msg_list_data` as
    // parameters as which one is passed affects the behavior of the function.
    // So, we need to need them as they were provided to us.
    load_messages({
        anchor,
        num_before: opts.num_before,
        num_after: 0,
        msg_list: opts.msg_list,
        msg_list_data: opts.msg_list_data,
        cont() {
            if (opts.cont) {
                opts.cont();
            }
        },
    });
}

export function maybe_load_newer_messages(opts) {
    // This function gets called when you scroll to the bottom
    // of your window, and you want to get messages newer
    // than what the browsers originally fetched.
    const msg_list = opts.msg_list;

    if (!msg_list.data.fetch_status.can_load_newer_messages()) {
        // We may already be loading new messages or already
        // got the newest one.
        return;
    }

    const anchor = get_frontfill_anchor(msg_list);

    function load_more(_data, args) {
        if (
            args.fetch_again &&
            message_lists.current !== undefined &&
            args.msg_list === message_lists.current
        ) {
            maybe_load_newer_messages({msg_list: message_lists.current});
        }
    }

    load_messages({
        anchor,
        num_before: 0,
        num_after: consts.narrowed_view_forward_batch_size,
        msg_list,
        cont: load_more,
    });
}

export function set_initial_pointer_and_offset({narrow_pointer, narrow_offset}) {
    initial_narrow_pointer = narrow_pointer;
    initial_narrow_offset = narrow_offset;
}

export function initialize(finished_initial_fetch) {
    // get the initial message list
    function load_more(data) {
        if (first_messages_fetch) {
            // See server_events.js for this callback.
            // Start processing server events.
            finished_initial_fetch();
            recent_view_ui.hide_loading_indicator();
            first_messages_fetch = false;
        }

        if (data.found_oldest) {
            return;
        }

        if (all_messages_data.num_items() >= consts.maximum_initial_backfill_size) {
            return;
        }

        // If we fall through here, we need to keep fetching more data, and
        // we'll call back to the function we're in.
        //
        // But we do it with a bit of delay, to reduce risk that we
        // hit rate limits with these backfills.
        const oldest_id = data.messages.at(0).id;
        setTimeout(() => {
            load_messages({
                anchor: oldest_id,
                num_before: consts.catch_up_batch_size,
                num_after: 0,
                msg_list_data: all_messages_data,
                cont: load_more,
            });
        }, consts.catch_up_backfill_delay);
    }

    // Since `all_messages_data` contains continuous message history
    // which always contains the latest message, it makes sense for
    // Recent view to display the same data and be in sync.
    all_messages_data.set_add_messages_callback((messages) => {
        recent_view_ui.process_messages(messages, all_messages_data);
    });

    // TODO: Ideally we'd have loading indicators for Recent Conversations
    // at both top and bottom be managed by load_messages, but that
    // likely depends on other reorganizations of the early loading
    // sequence.
    recent_view_ui.show_loading_indicator();
    load_messages({
        anchor: "newest",
        num_before: consts.initial_backfill_fetch_size,
        num_after: 0,
        msg_list_data: all_messages_data,
        cont: load_more,
    });
}
