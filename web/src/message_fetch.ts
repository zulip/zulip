import assert from "minimalistic-assert";
import * as z from "zod/mini";

import {all_messages_data} from "./all_messages_data.ts";
import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as direct_message_group_data from "./direct_message_group_data.ts";
import {Filter} from "./filter.ts";
import * as message_feed_loading from "./message_feed_loading.ts";
import * as message_feed_top_notices from "./message_feed_top_notices.ts";
import * as message_helper from "./message_helper.ts";
import type {MessageList} from "./message_list.ts";
import type {MessageListData} from "./message_list_data.ts";
import * as message_list_data_cache from "./message_list_data_cache.ts";
import * as message_lists from "./message_lists.ts";
import {raw_message_schema} from "./message_store.ts";
import * as message_util from "./message_util.ts";
import * as message_viewport from "./message_viewport.ts";
import * as narrow_banner from "./narrow_banner.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as popup_banners from "./popup_banners.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import type {NarrowTerm} from "./state_data.ts";
import {narrow_term_schema} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_list from "./stream_list.ts";
import * as util from "./util.ts";

export const response_schema = z.object({
    anchor: z.number(),
    found_newest: z.boolean(),
    found_oldest: z.boolean(),
    found_anchor: z.boolean(),
    history_limited: z.boolean(),
    messages: z.array(raw_message_schema),
    result: z.string(),
    msg: z.string(),
});

type MessageFetchResponse = z.infer<typeof response_schema>;

type MessageFetchOptions = {
    anchor: string | number;
    num_before: number;
    num_after: number;
    cont: (data: MessageFetchResponse, args: MessageFetchOptions) => void;
    fetch_again?: boolean;
    msg_list_data: MessageListData;
    msg_list?: MessageList | undefined;
    validate_filter_topic_post_fetch?: boolean | undefined;
};

type MessageFetchAPIParams = {
    anchor: number | string;
    num_before: number;
    num_after: number;
    client_gravatar: boolean;
    narrow?: string;
    allow_empty_topic_name: boolean;
};

let first_messages_fetch = true;
let initial_backfill_for_all_messages_done = false;
export let initial_narrow_pointer: number | undefined;
export let initial_narrow_offset: number | undefined;

const consts = {
    // Because most views are centered on the first unread message,
    // the user has a higher probability of wanting to scroll down
    // than, so extra fetched history after the cursor is more likely
    // to be used and thus worth more to fetch.
    //
    // It's rare to have hundreds of unreads after the cursor, asking
    // for a larger number of messages after the cursor is cheap.
    narrow_before: 60,
    narrow_after: 150,

    // Batch sizes when at the top/bottom of a narrowed view.
    narrowed_view_backward_batch_size: 100,
    narrowed_view_forward_batch_size: 100,

    // Initial backfill parameters to populate message history.
    initial_backfill_fetch_size: 1000,
    catch_up_batch_size: 2000,
    // We fetch at least minimum_initial_backfill_size messages of
    // history, but after that will stop fetching at either
    // maximum_initial_backfill_size messages or
    // target_days_of_history days, whichever comes first.
    minimum_initial_backfill_size: 9000,
    maximum_initial_backfill_size: 25000,
    target_days_of_history: 180,
    // Delay in milliseconds after processing a catch-up request
    // before sending the next one.
    catch_up_backfill_delay: 150,

    // Parameters for asking for more history in the recent view.
    recent_view_fetch_more_batch_size: 2000,
    recent_view_minimum_load_more_fetch_size: 50000,
    recent_view_load_more_increment_per_click: 25000,
};

export function load_messages_around_anchor(
    anchor: string,
    cont: () => void,
    msg_list_data: MessageListData,
): void {
    load_messages({
        anchor,
        num_before: consts.narrowed_view_backward_batch_size,
        num_after: consts.narrowed_view_forward_batch_size,
        msg_list_data,
        cont,
    });
}

export function fetch_more_if_required_for_current_msg_list(
    has_found_oldest: boolean,
    has_found_newest: boolean,
    looking_for_new_msgs: boolean,
    looking_for_old_msgs: boolean,
): void {
    assert(message_lists.current !== undefined);
    if (has_found_oldest && has_found_newest && message_lists.current.visibly_empty()) {
        // Even after loading more messages, we have
        // no messages to display in this narrow.
        narrow_banner.show_empty_narrow_message(message_lists.current.data.filter);
        message_lists.current.update_trailing_bookend();
        compose_closed_ui.update_buttons_for_private();
        compose_recipient.check_posting_policy_for_compose_box();
    }

    if (looking_for_old_msgs && !has_found_oldest) {
        maybe_load_older_messages({
            msg_list: message_lists.current,
            msg_list_data: message_lists.current.data,
        });
    }
    if (looking_for_new_msgs && !has_found_newest) {
        maybe_load_newer_messages({msg_list: message_lists.current});
    }
}

function process_result(data: MessageFetchResponse, opts: MessageFetchOptions): void {
    const raw_messages = data.messages;

    const messages = raw_messages.map((raw_message) =>
        message_helper.process_new_message(raw_message),
    );
    const has_found_oldest = opts.msg_list?.data.fetch_status.has_found_oldest() ?? false;
    const has_found_newest = opts.msg_list?.data.fetch_status.has_found_newest() ?? false;

    // In some rare situations, we expect to discover new unread
    // messages not tracked in unread.ts during this fetching process.
    message_util.do_unread_count_updates(messages, true);

    const is_contiguous_history = true;
    if (messages.length > 0) {
        if (opts.msg_list) {
            if (opts.validate_filter_topic_post_fetch) {
                opts.msg_list.data.filter.try_adjusting_for_moved_with_target(messages[0]);
            }
            // Since this adds messages to the MessageList and renders MessageListView,
            // we don't need to call it if msg_list was not defined by the caller.
            opts.msg_list.add_messages(messages, {}, is_contiguous_history);
        } else {
            opts.msg_list_data.add_messages(messages, is_contiguous_history);
        }
    }

    direct_message_group_data.process_loaded_messages(messages);
    stream_list.update_streams_sidebar();
    stream_list.maybe_scroll_narrow_into_view(!first_messages_fetch);

    if (
        message_lists.current !== undefined &&
        opts.msg_list === message_lists.current &&
        // The view appears to be empty. However, because in stream
        // narrows, we fetch messages including those that might be
        // hidden by topic muting, it's possible that we received all
        // the messages we requested, and all of them are in muted
        // topics, but there are older messages for this stream that
        // we need to ask the server for.
        (message_lists.current.visibly_empty() || !message_viewport.can_scroll())
    ) {
        const looking_for_new_msgs = opts.num_after > 0;
        const looking_for_old_msgs = opts.num_before > 0;
        fetch_more_if_required_for_current_msg_list(
            has_found_oldest,
            has_found_newest,
            looking_for_new_msgs,
            looking_for_old_msgs,
        );
    }

    if (opts.cont !== undefined) {
        opts.cont(data, opts);
    }
}

function get_messages_success(data: MessageFetchResponse, opts: MessageFetchOptions): void {
    const update_loading_indicator =
        message_lists.current !== undefined && opts.msg_list === message_lists.current;
    const msg_list_data = opts.msg_list_data;
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
        if (opts.msg_list) {
            message_feed_top_notices.update_top_of_narrow_notices(opts.msg_list);
        }
    }

    if (opts.num_after > 0 || current_fetch_found_newest) {
        opts.fetch_again = msg_list_data.fetch_status.finish_newer_batch(data.messages, {
            update_loading_indicator,
            found_newest: data.found_newest,
        });
    }

    if (
        opts.msg_list &&
        !opts.msg_list.should_preserve_current_rendered_state() &&
        opts.msg_list !== message_lists.current
    ) {
        // We changed narrow before receiving new messages but
        // since the message list data is cached, we just
        // update the cached data and don't update the msg list.
        opts.msg_list_data = opts.msg_list.data;
        opts.msg_list = undefined;
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

// This function modifies the narrow data to use integer IDs instead of
// strings if it is supported for that operator. We currently don't set
// or convert user emails to IDs directly in the Filter code because
// doing so breaks the app in various modules that expect a string of
// user emails.
function handle_operators_supporting_id_based_api(narrow_parameter: string): string {
    // We use the canonical operator when checking these sets, so legacy
    // operators, such as "pm-with" and "stream", are not included here.
    const operators_supporting_ids = new Set(["dm"]);
    const operators_supporting_id = new Set(["id", "channel", "sender", "dm-including"]);
    const parsed_narrow_data = z.array(narrow_term_schema).parse(JSON.parse(narrow_parameter));

    const narrow_terms: {
        operator: string;
        operand: number[] | number | string;
        negated?: boolean | undefined;
    }[] = [];
    for (const raw_term of parsed_narrow_data) {
        const narrow_term: {
            operator: string;
            operand: number[] | number | string;
            negated?: boolean | undefined;
        } = raw_term;

        const canonical_operator = Filter.canonicalize_operator(raw_term.operator);

        if (operators_supporting_ids.has(canonical_operator)) {
            const user_ids_array = people.emails_strings_to_user_ids_array(raw_term.operand);
            assert(user_ids_array !== undefined);
            narrow_term.operand = user_ids_array;
        }

        if (operators_supporting_id.has(canonical_operator)) {
            if (canonical_operator === "id") {
                // The message ID may not exist locally,
                // so send the term to the server as is.
                narrow_terms.push(narrow_term);
                continue;
            }

            if (canonical_operator === "channel") {
                // An unknown channel will have an empty string set for
                // the operand. And the page_params.narrow may have a
                // channel name as the operand. But all other cases
                // should have the channel ID set as the string value
                // for the operand.
                const stream = stream_data.get_sub_by_id_string(raw_term.operand);
                if (stream !== undefined) {
                    narrow_term.operand = stream.stream_id;
                }
                narrow_terms.push(narrow_term);
                continue;
            }

            // The other operands supporting integer IDs all work with
            // a single user object.
            const person = people.get_by_email(raw_term.operand);
            if (person !== undefined) {
                narrow_term.operand = person.user_id;
            }
        }
        narrow_terms.push(narrow_term);
    }

    return JSON.stringify(narrow_terms);
}

export function get_narrow_for_message_fetch(filter: Filter): string {
    let narrow_data = filter.public_terms();
    if (page_params.narrow !== undefined) {
        narrow_data = [...narrow_data, ...page_params.narrow];
    }
    if (page_params.is_spectator) {
        const web_public_narrow: NarrowTerm[] = [
            {operator: "channels", operand: "web-public", negated: false},
        ];
        // This logic is not ideal in that, in theory, an existing `channels`
        // operator could be present, but not in a useful way. We don't attempt
        // to validate the narrow is compatible with spectators here; the server
        // will return an error if appropriate.
        narrow_data = [...narrow_data, ...web_public_narrow];
    }

    let narrow_param_string = "";
    if (narrow_data.length > 0) {
        narrow_param_string = JSON.stringify(narrow_data);
        narrow_param_string = handle_operators_supporting_id_based_api(narrow_param_string);
    }
    return narrow_param_string;
}

export function get_parameters_for_message_fetch_api(
    opts: MessageFetchOptions,
): MessageFetchAPIParams {
    if (typeof opts.anchor === "number") {
        // Messages that have been locally echoed messages have
        // floating point temporary IDs, which is intended to be a.
        // completely client-side detail.  We need to round these to
        // the nearest integer before sending a request to the server.
        opts.anchor = opts.anchor.toFixed(0);
    }
    const data: MessageFetchAPIParams = {
        anchor: opts.anchor,
        num_before: opts.num_before,
        num_after: opts.num_after,
        client_gravatar: true,
        allow_empty_topic_name: true,
    };
    const msg_list_data = opts.msg_list_data;

    if (msg_list_data === undefined) {
        blueslip.error("Message list data is undefined!");
    }

    const narrow = get_narrow_for_message_fetch(msg_list_data.filter);
    if (narrow !== "") {
        data.narrow = narrow;
    }
    return data;
}

// We keep track of the load messages timeout at a module level
// to prevent multiple load messages requests from the error codepath
// from stacking up by cancelling the previous timeout.
let load_messages_timeout: ReturnType<typeof setTimeout> | undefined;

export function load_messages(opts: MessageFetchOptions, attempt = 1): void {
    const data = get_parameters_for_message_fetch_api(opts);
    let update_loading_indicator =
        message_lists.current !== undefined && opts.msg_list === message_lists.current;
    if (opts.num_before > 0) {
        opts.msg_list_data.fetch_status.start_older_batch({
            update_loading_indicator,
        });
    }

    if (opts.num_after > 0) {
        // We hide the bottom loading indicator when we're fetching both top and bottom messages.
        update_loading_indicator = update_loading_indicator && opts.num_before === 0;
        opts.msg_list_data.fetch_status.start_newer_batch({
            update_loading_indicator,
        });
    }

    if (load_messages_timeout !== undefined) {
        clearTimeout(load_messages_timeout);
    }

    void channel.get({
        url: "/json/messages",
        data,
        success(raw_data) {
            popup_banners.close_connection_error_popup_banner("message_fetch");
            const data = response_schema.parse(raw_data);
            get_messages_success(data, opts);
        },
        error(xhr) {
            if (xhr.status === 400) {
                // Even though the request failed, we did reach the
                // server, and can hide the connection error notice.
                popup_banners.close_connection_error_popup_banner("message_fetch");
            }

            if (
                opts.msg_list !== undefined &&
                opts.msg_list !== message_lists.current &&
                !opts.msg_list.is_combined_feed_view
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
                    !opts.msg_list.is_combined_feed_view &&
                    opts.msg_list.visibly_empty()
                ) {
                    narrow_banner.show_empty_narrow_message(opts.msg_list.data.filter);
                }

                // TODO: This should probably do something explicit with
                // `FetchStatus` to mark the message list as not eligible for
                // further fetches. Currently, that happens implicitly via
                // failing to call finish_older_batch / finish_newer_batch
                return;
            }

            const delay_secs = util.get_retry_backoff_seconds(xhr, attempt, true);
            popup_banners.open_connection_error_popup_banner({
                caller: "message_fetch",
                retry_delay_secs: delay_secs,
                on_retry_callback() {
                    load_messages(opts, attempt + 1);
                },
            });

            load_messages_timeout = setTimeout(() => {
                load_messages(opts, attempt + 1);
            }, delay_secs * 1000);
        },
    });
}

export function load_messages_for_narrow(opts: {
    anchor: string | number;
    msg_list: MessageList;
    cont: () => void;
    validate_filter_topic_post_fetch?: boolean | undefined;
}): void {
    load_messages({
        anchor: opts.anchor,
        num_before: consts.narrow_before,
        num_after: consts.narrow_after,
        msg_list: opts.msg_list,
        msg_list_data: opts.msg_list.data,
        cont: opts.cont,
        validate_filter_topic_post_fetch: opts.validate_filter_topic_post_fetch,
    });
}

export function get_backfill_anchor(msg_list_data: MessageListData): string | number {
    const oldest_msg = msg_list_data.first_including_muted();
    if (oldest_msg) {
        return oldest_msg.id;
    }

    return "first_unread";
}

export function get_frontfill_anchor(msg_list: MessageList): number | string {
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

export function maybe_load_older_messages(opts: {
    recent_view?: boolean;
    first_unread_message_id?: number;
    cont?: () => void;
    msg_list?: MessageList | undefined;
    msg_list_data: MessageListData;
}): void {
    // This function gets called when you scroll to the top
    // of your window, and you want to get messages older
    // than what the browsers originally fetched.
    const msg_list_data = opts.msg_list_data;
    if (!msg_list_data.fetch_status.can_load_older_messages()) {
        // We may already be loading old messages or already
        // got the oldest one.
        if (opts.recent_view) {
            recent_view_ui.set_backfill_in_progress(false);
        }
        return;
    }

    if (opts.recent_view && recent_view_ui.is_backfill_in_progress) {
        // The recent view "load more" button does a tail-recursive
        // backfill, so that one doesn't have to click dozens of times
        // to get a large amount of history.
        //
        // We can afford to do this in our server load budget, because
        // this is a rare operation; prior to May 2024, Zulip fetched
        // all history since the oldest unread unconditionally.

        let fetched_substantial_history = false;
        if (msg_list_data.num_items() >= consts.recent_view_minimum_load_more_fetch_size) {
            fetched_substantial_history = true;
        }

        let found_first_unread = opts.first_unread_message_id === undefined;
        // This is a soft check because `first_unread_message_id` can be deleted.
        const first_message = msg_list_data.first();
        if (
            opts.first_unread_message_id &&
            first_message &&
            first_message.id <= opts.first_unread_message_id
        ) {
            found_first_unread = true;
        }

        if (fetched_substantial_history && found_first_unread) {
            // Increase bar for `fetched_substantial_history` for next
            // `Load more` click.
            opts.cont = () => {
                consts.recent_view_minimum_load_more_fetch_size +=
                    consts.recent_view_load_more_increment_per_click;
                recent_view_ui.set_backfill_in_progress(false);
            };
        } else {
            opts.cont = () =>
                setTimeout(() => {
                    maybe_load_older_messages(opts);
                }, consts.catch_up_backfill_delay);
        }
    }
    do_backfill({
        msg_list: opts.msg_list,
        msg_list_data: opts.msg_list_data,
        cont() {
            if (opts.cont) {
                opts.cont();
            }
        },
        num_before: opts.recent_view
            ? consts.recent_view_fetch_more_batch_size
            : consts.narrowed_view_backward_batch_size,
    });
}

export function do_backfill(opts: {
    num_before: number;
    cont?: () => void;
    msg_list_data: MessageListData;
    msg_list?: MessageList | undefined;
}): void {
    const msg_list_data = opts.msg_list_data;
    const anchor = get_backfill_anchor(msg_list_data);

    // `load_messages` behaves differently for `msg_list` and `msg_list_data` as
    // parameters as which one is passed affects the behavior of the function.
    // So, we need to need them as they were provided to us.
    load_messages({
        anchor,
        num_before: opts.num_before,
        num_after: 0,
        msg_list: opts.msg_list,
        msg_list_data,
        cont() {
            if (opts.cont) {
                opts.cont();
            }
        },
    });
}

export function maybe_load_newer_messages(opts: {msg_list: MessageList}): void {
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

    function load_more(_data: MessageFetchResponse, args: MessageFetchOptions): void {
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
        msg_list_data: opts.msg_list.data,
        cont: load_more,
    });
}

export function set_initial_pointer_and_offset({
    narrow_pointer,
    narrow_offset,
}: {
    narrow_pointer: number | undefined;
    narrow_offset: number | undefined;
}): void {
    initial_narrow_pointer = narrow_pointer;
    initial_narrow_offset = narrow_offset;
}

export function initialize(finished_initial_fetch: () => void): void {
    const fetch_target_day_timestamp =
        Date.now() / 1000 - consts.target_days_of_history * 24 * 60 * 60;
    // get the initial message list
    function load_more(data: MessageFetchResponse): void {
        if (first_messages_fetch) {
            // See server_events.js for this callback.
            // Start processing server events.
            finished_initial_fetch();
            recent_view_ui.hide_loading_indicator();
            first_messages_fetch = false;
        }

        if (data.found_oldest) {
            initial_backfill_for_all_messages_done = true;
            return;
        }

        // Stop once we've hit the minimum backfill quantity of
        // messages if we've received a message older than
        // `target_days_of_history`.
        const latest_message = all_messages_data.first();
        assert(latest_message !== undefined);
        if (
            all_messages_data.num_items() >= consts.minimum_initial_backfill_size &&
            latest_message.timestamp < fetch_target_day_timestamp
        ) {
            initial_backfill_for_all_messages_done = true;
            return;
        }

        if (all_messages_data.num_items() >= consts.maximum_initial_backfill_size) {
            initial_backfill_for_all_messages_done = true;
            return;
        }

        // If we fall through here, we need to keep fetching more data, and
        // we'll call back to the function we're in.
        //
        // But we do it with a bit of delay, to reduce risk that we
        // hit rate limits with these backfills.
        const oldest_message = data.messages.at(0);
        assert(oldest_message !== undefined);
        const oldest_id = oldest_message.id;
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
    all_messages_data.set_add_messages_callback((messages, rows_order_changed) => {
        try {
            recent_view_ui.process_messages(messages, rows_order_changed, all_messages_data);
        } catch (error) {
            blueslip.error("Error in recent_view_ui.process_messages", undefined, error);
        }

        if (
            !recent_view_ui.is_backfill_in_progress &&
            !first_messages_fetch &&
            initial_backfill_for_all_messages_done
        ) {
            // We only populate other cached data for major backfills.
            return;
        }

        // Since we backfill a lot more messages here compared to rendered message list,
        // we can try populating them if we can do so locally.
        for (const msg_list_data of message_list_data_cache.all()) {
            if (msg_list_data === all_messages_data) {
                continue;
            }

            if (!msg_list_data.filter.can_apply_locally()) {
                continue;
            }

            if (msg_list_data.visibly_empty()) {
                // If the message list is visibly empty, we don't want to add
                // message here to break the continuous message history.
                // We will rely here on our backfill logic to render any visible
                // messages if we can.
                continue;
            }

            // This callback is only called when backfilling messages,
            // so we need to check for the presence of any message from
            // the message list in the all_messages_data to
            // check for continuous message history for the message list.
            const first_message = msg_list_data.first();
            assert(first_message !== undefined);
            if (all_messages_data.get(first_message.id) !== undefined) {
                const messages_to_populate = all_messages_data.message_range(0, first_message.id);
                if (msg_list_data.rendered_message_list_id) {
                    const msg_list = message_lists.rendered_message_lists.get(
                        msg_list_data.rendered_message_list_id,
                    );
                    assert(msg_list !== undefined);
                    msg_list.add_messages(messages_to_populate, {});
                } else {
                    msg_list_data.add_messages(messages_to_populate);
                }
            }
        }
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
