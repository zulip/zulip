import $ from "jquery";

import {all_messages_data} from "./all_messages_data";
import * as channel from "./channel";
import {Filter} from "./filter";
import * as huddle_data from "./huddle_data";
import * as message_helper from "./message_helper";
import * as message_list from "./message_list";
import * as message_lists from "./message_lists";
import * as message_scroll from "./message_scroll";
import * as message_store from "./message_store";
import * as message_util from "./message_util";
import * as narrow_banner from "./narrow_banner";
import {page_params} from "./page_params";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as recent_topics_ui from "./recent_topics_ui";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as ui_report from "./ui_report";

const consts = {
    backfill_idle_time: 10 * 1000,
    error_retry_time: 5000,
    backfill_batch_size: 1000,
    narrow_before: 50,
    narrow_after: 50,
    num_before_home_anchor: 200,
    num_after_home_anchor: 200,
    recent_topics_initial_fetch_size: 400,
    backward_batch_size: 100,
    forward_batch_size: 100,
    catch_up_batch_size: 1000,
};

function process_result(data, opts) {
    let messages = data.messages;

    if (!$("#connection-error").hasClass("get-events-error")) {
        ui_report.hide_error($("#connection-error"));
    }

    if (
        messages.length === 0 &&
        message_lists.current === message_list.narrowed &&
        message_list.narrowed.empty()
    ) {
        // Even after trying to load more messages, we have no
        // messages to display in this narrow.
        narrow_banner.show_empty_narrow_message();
    }

    messages = messages.map((message) => {
        message_store.set_message_booleans(message);
        return message_helper.process_new_message(message);
    });

    // In case any of the newly fetched messages are new, add them to
    // our unread data structures.  It's important that this run even
    // when fetching in a narrow, since we might return unread
    // messages that aren't in the home view data set (e.g. on a muted
    // stream).
    message_util.do_unread_count_updates(messages);

    // If we're loading more messages into the home view, save them to
    // the all_messages_data as well, as the message_lists.home is
    // reconstructed from all_messages_data.
    if (opts.msg_list === message_lists.home) {
        all_messages_data.add_messages(messages);
    }

    if (messages.length !== 0) {
        message_util.add_old_messages(messages, opts.msg_list);
    }

    huddle_data.process_loaded_messages(messages);
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
    recent_topics_ui.process_messages(messages);

    stream_list.maybe_scroll_narrow_into_view();

    if (opts.cont !== undefined) {
        opts.cont(data, opts);
    }
}

function get_messages_success(data, opts) {
    const update_loading_indicator = opts.msg_list === message_lists.current;
    if (opts.num_before > 0) {
        opts.msg_list.data.fetch_status.finish_older_batch({
            update_loading_indicator,
            found_oldest: data.found_oldest,
            history_limited: data.history_limited,
        });
        if (opts.msg_list === message_lists.home) {
            // When we update message_lists.home, we need to also update
            // the fetch_status data structure for all_messages_data.
            all_messages_data.fetch_status.finish_older_batch({
                update_loading_indicator: false,
                found_oldest: data.found_oldest,
                history_limited: data.history_limited,
            });
        }
        message_scroll.update_top_of_narrow_notices(opts.msg_list);
    }

    if (opts.num_after > 0) {
        opts.fetch_again = opts.msg_list.data.fetch_status.finish_newer_batch(data.messages, {
            update_loading_indicator,
            found_newest: data.found_newest,
        });
        if (opts.msg_list === message_lists.home) {
            // When we update message_lists.home, we need to also update
            // the fetch_status data structure for all_messages_data.
            opts.fetch_again = all_messages_data.fetch_status.finish_newer_batch(data.messages, {
                update_loading_indicator: false,
                found_newest: data.found_newest,
            });
        }
    }

    if (opts.msg_list.narrowed && opts.msg_list !== message_lists.current) {
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

// This function modifies the data.narrow filters to use user IDs
// instead of emails string if it is supported. We currently don't set
// or convert the emails string to user IDs directly into the Filter code
// because doing so breaks the app in various modules that expect emails string.
function handle_operators_supporting_id_based_api(data) {
    const operators_supporting_ids = new Set(["pm-with"]);
    const operators_supporting_id = new Set(["sender", "group-pm-with", "stream"]);

    if (data.narrow === undefined) {
        return data;
    }

    data.narrow = JSON.parse(data.narrow);
    data.narrow = data.narrow.map((filter) => {
        if (operators_supporting_ids.has(filter.operator)) {
            filter.operand = people.emails_strings_to_user_ids_array(filter.operand);
        }

        if (operators_supporting_id.has(filter.operator)) {
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

export function load_messages(opts) {
    if (typeof opts.anchor === "number") {
        // Messages that have been locally echoed messages have
        // floating point temporary IDs, which is intended to be a.
        // completely client-side detail.  We need to round these to
        // the nearest integer before sending a request to the server.
        opts.anchor = opts.anchor.toFixed(0);
    }
    let data = {anchor: opts.anchor, num_before: opts.num_before, num_after: opts.num_after};

    // This block is a hack; structurally, we want to set
    //   data.narrow = opts.msg_list.data.filter.public_operators()
    //
    // But support for the all_messages_data sharing of data with
    // message_lists.home and the (hacky) page_params.narrow feature
    // requires a somewhat ugly bundle of conditionals.
    if (opts.msg_list === message_lists.home) {
        if (page_params.narrow_stream !== undefined) {
            data.narrow = JSON.stringify(page_params.narrow);
        }
        // Otherwise, we don't pass narrow for message_lists.home; this is
        // required because it shares its data with all_msg_list, and
        // so we need the server to send us message history from muted
        // streams and topics even though message_lists.home's in:home
        // operators will filter those.
    } else {
        let operators = opts.msg_list.data.filter.public_operators();
        if (page_params.narrow !== undefined) {
            operators = operators.concat(page_params.narrow);
        }
        data.narrow = JSON.stringify(operators);
    }

    let update_loading_indicator = opts.msg_list === message_lists.current;
    if (opts.num_before > 0) {
        opts.msg_list.data.fetch_status.start_older_batch({
            update_loading_indicator,
        });
        if (opts.msg_list === message_lists.home) {
            all_messages_data.fetch_status.start_older_batch({
                update_loading_indicator,
            });
        }
    }

    if (opts.num_after > 0) {
        // We hide the bottom loading indicator when we're fetching both top and bottom messages.
        update_loading_indicator = update_loading_indicator && opts.num_before === 0;
        opts.msg_list.data.fetch_status.start_newer_batch({
            update_loading_indicator,
        });
        if (opts.msg_list === message_lists.home) {
            all_messages_data.fetch_status.start_newer_batch({
                update_loading_indicator,
            });
        }
    }

    data.client_gravatar = true;
    data = handle_operators_supporting_id_based_api(data);

    if (page_params.is_spectator) {
        // This is a bit of a hack; ideally we'd unify this logic in
        // some way with the above logic, and not need to do JSON
        // parsing/stringifying here.
        const web_public_narrow = {negated: false, operator: "streams", operand: "web-public"};

        if (!data.narrow) {
            /* For the "All messages" feed, this will be the only operator. */
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
        idempotent: true,
        success(data) {
            get_messages_success(data, opts);
        },
        error(xhr) {
            if (opts.msg_list.narrowed && opts.msg_list !== message_lists.current) {
                // We unnarrowed before getting an error so don't
                // bother trying again or doing further processing.
                return;
            }
            if (xhr.status === 400) {
                // Bad request: We probably specified a narrow operator
                // for a nonexistent stream or something.  We shouldn't
                // retry or display a connection error.
                //
                // FIXME: Warn the user when this has happened?
                message_scroll.hide_indicators();
                const data = {
                    messages: [],
                };
                process_result(data, opts);
                return;
            }

            // We might want to be more clever here
            $("#connection-error").addClass("show");
            setTimeout(() => {
                load_messages(opts);
            }, consts.error_retry_time);
        },
    });
}

export function load_messages_for_narrow(opts) {
    const msg_list = message_list.narrowed;

    load_messages({
        anchor: opts.anchor,
        num_before: consts.narrow_before,
        num_after: consts.narrow_after,
        msg_list,
        cont: opts.cont,
    });
}

export function get_backfill_anchor(msg_list) {
    const oldest_msg =
        msg_list === message_lists.home ? all_messages_data.first() : msg_list.first();

    if (oldest_msg) {
        return oldest_msg.id;
    }

    // msg_list is empty, which is an impossible
    // case, raise a fatal error.
    throw new Error("There are no message available to backfill.");
}

export function get_frontfill_anchor(msg_list) {
    const last_msg = msg_list === message_lists.home ? all_messages_data.last() : msg_list.last();

    if (last_msg) {
        return last_msg.id;
    }

    // Although it is impossible that we reach here since we
    // are already checking `msg_list.fetch_status.can_load_newer_messages`
    // and user cannot be scrolling down on an empty message_list to
    // fetch more data, and if user is, then the available data is wrong
    // and we raise a fatal error.
    throw new Error("There are no message available to frontfill.");
}

export function maybe_load_older_messages(opts) {
    // This function gets called when you scroll to the top
    // of your window, and you want to get messages older
    // than what the browsers originally fetched.
    const msg_list = opts.msg_list;
    if (!msg_list.data.fetch_status.can_load_older_messages()) {
        // We may already be loading old messages or already
        // got the oldest one.
        return;
    }

    do_backfill({
        msg_list,
        num_before: consts.backward_batch_size,
    });
}

export function do_backfill(opts) {
    const msg_list = opts.msg_list;
    const anchor = get_backfill_anchor(msg_list);

    load_messages({
        anchor,
        num_before: opts.num_before,
        num_after: 0,
        msg_list,
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

    function load_more(data, args) {
        if (args.fetch_again && args.msg_list === message_lists.current) {
            maybe_load_newer_messages({msg_list: message_lists.current});
        }
    }

    load_messages({
        anchor,
        num_before: 0,
        num_after: consts.forward_batch_size,
        msg_list,
        cont: load_more,
    });
}

export function start_backfilling_messages() {
    // backfill more messages after the user is idle
    $(document).idle({
        idle: consts.backfill_idle_time,
        onIdle() {
            do_backfill({
                num_before: consts.backfill_batch_size,
                msg_list: message_lists.home,
            });
        },
    });
}

export function initialize(home_view_loaded) {
    // get the initial message list
    function load_more(data) {
        // If we haven't selected a message in the home view yet, and
        // the home view isn't empty, we select the anchor message here.
        if (message_lists.home.selected_id() === -1 && !message_lists.home.empty()) {
            // We fall back to the closest selected id, as the user
            // may have removed a stream from the home view while we
            // were loading data.
            message_lists.home.select_id(data.anchor, {
                then_scroll: true,
                use_closest: true,
                target_scroll_offset: page_params.initial_offset,
            });
        }

        if (data.found_newest) {
            // See server_events.js for this callback.
            home_view_loaded();
            start_backfilling_messages();
            return;
        }

        // If we fall through here, we need to keep fetching more data, and
        // we'll call back to the function we're in.
        const messages = data.messages;
        const latest_id = messages[messages.length - 1].id;

        load_messages({
            anchor: latest_id,
            num_before: 0,
            num_after: consts.catch_up_batch_size,
            msg_list: message_lists.home,
            cont: load_more,
        });
    }

    let anchor;
    if (page_params.initial_pointer) {
        // If we're doing a server-initiated reload, similar to a
        // near: narrow query, we want to select a specific message.
        anchor = page_params.initial_pointer;
    } else {
        // Otherwise, we should just use the first unread message in
        // the user's unmuted history as our anchor.
        anchor = "first_unread";
    }
    load_messages({
        anchor,
        num_before: consts.num_before_home_anchor,
        num_after: consts.num_after_home_anchor,
        msg_list: message_lists.home,
        cont: load_more,
    });

    if (page_params.is_spectator) {
        // Since spectators never have old unreads, we can skip the
        // hacky fetch below for them (which would just waste resources).
        return;
    }

    // In addition to the algorithm above, which is designed to ensure
    // that we fetch all message history eventually starting with the
    // first unread message, we also need to ensure that the Recent
    // Topics page contains the very most recent threads on page load.
    //
    // Long term, we'll want to replace this with something that's
    // more performant (i.e. avoids this unnecessary extra fetch the
    // results of which are basically discarded) and better represents
    // more than a few hundred messages' history, but this strategy
    // allows "Recent topics" to always show current data (with gaps)
    // on page load; the data will be complete once the algorithm
    // above catches up to present.
    //
    // (Users will see a weird artifact where Recent topics has a gap
    // between E.g. 6 days ago and 37 days ago while the catchup
    // process runs, so this strategy still results in problematic
    // visual artifacts shortly after page load; just more forgiveable
    // ones).
    //
    // This MessageList is defined similarly to home_message_list,
    // without a `table_name` attached.
    const recent_topics_message_list = new message_list.MessageList({
        filter: new Filter([{operator: "in", operand: "home"}]),
        excludes_muted_topics: true,
    });
    load_messages({
        anchor: "newest",
        num_before: consts.recent_topics_initial_fetch_size,
        num_after: 0,
        msg_list: recent_topics_message_list,
    });
}
