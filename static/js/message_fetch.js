"use strict";

const huddle_data = require("./huddle_data");
const people = require("./people");

const consts = {
    backfill_idle_time: 10 * 1000,
    error_retry_time: 5000,
    backfill_batch_size: 1000,
    narrow_before: 50,
    narrow_after: 50,
    num_before_home_anchor: 200,
    num_after_home_anchor: 200,
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
        current_msg_list === message_list.narrowed &&
        message_list.narrowed.empty()
    ) {
        // Even after trying to load more messages, we have no
        // messages to display in this narrow.
        narrow.show_empty_narrow_message();
    }

    messages.forEach(message_store.set_message_booleans);
    messages = messages.map(message_store.add_message_metadata);

    // In case any of the newly fetched messages are new, add them to
    // our unread data structures.  It's important that this run even
    // when fetching in a narrow, since we might return unread
    // messages that aren't in the home view data set (e.g. on a muted
    // stream).
    message_util.do_unread_count_updates(messages);

    // If we're loading more messages into the home view, save them to
    // the message_list.all as well, as the home_msg_list is reconstructed
    // from message_list.all.
    if (opts.msg_list === home_msg_list) {
        message_util.add_old_messages(messages, message_list.all);
    }

    if (messages.length !== 0) {
        message_util.add_old_messages(messages, opts.msg_list);
    }

    huddle_data.process_loaded_messages(messages);
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
    recent_topics.process_messages(messages);

    stream_list.maybe_scroll_narrow_into_view();

    if (opts.cont !== undefined) {
        opts.cont(data, opts);
    }
}

function get_messages_success(data, opts) {
    const update_loading_indicator = opts.msg_list === current_msg_list;
    if (opts.num_before > 0) {
        opts.msg_list.data.fetch_status.finish_older_batch({
            update_loading_indicator,
            found_oldest: data.found_oldest,
            history_limited: data.history_limited,
        });
        if (opts.msg_list === home_msg_list) {
            // When we update home_msg_list, we need to also update
            // the fetch_status data structure for message_list.all,
            // which is never rendered (and just used for
            // prepopulating narrowed views).
            message_list.all.data.fetch_status.finish_older_batch({
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
        if (opts.msg_list === home_msg_list) {
            // When we update home_msg_list, we need to also update
            // the fetch_status data structure for message_list.all,
            // which is never rendered (and just used for
            // prepopulating narrowed views).
            opts.fetch_again = message_list.all.data.fetch_status.finish_newer_batch(
                data.messages,
                {
                    update_loading_indicator: false,
                    found_newest: data.found_newest,
                },
            );
        }
    }

    if (opts.msg_list.narrowed && opts.msg_list !== current_msg_list) {
        // We unnarrowed before receiving new messages so
        // don't bother processing the newly arrived messages.
        return;
    }
    if (!data) {
        // The server occasionally returns no data during a
        // restart.  Ignore those responses and try again
        setTimeout(() => {
            exports.load_messages(opts);
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
    const operators_supporting_ids = ["pm-with"];
    const operators_supporting_id = ["sender", "group-pm-with", "stream"];

    if (data.narrow === undefined) {
        return data;
    }

    data.narrow = JSON.parse(data.narrow);
    data.narrow = data.narrow.map((filter) => {
        if (operators_supporting_ids.includes(filter.operator)) {
            filter.operand = people.emails_strings_to_user_ids_array(filter.operand);
        }

        if (operators_supporting_id.includes(filter.operator)) {
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

exports.load_messages = function (opts) {
    if (typeof opts.anchor === "number") {
        // Messages that have been locally echoed messages have
        // floating point temporary IDs, which is intended to be a.
        // completely client-side detail.  We need to round these to
        // the nearest integer before sending a request to the server.
        opts.anchor = opts.anchor.toFixed();
    }
    let data = {anchor: opts.anchor, num_before: opts.num_before, num_after: opts.num_after};

    if (opts.msg_list.narrowed && narrow_state.active()) {
        let operators = narrow_state.public_operators();
        if (page_params.narrow !== undefined) {
            operators = operators.concat(page_params.narrow);
        }
        data.narrow = JSON.stringify(operators);
    }
    if (opts.msg_list === home_msg_list && page_params.narrow_stream !== undefined) {
        data.narrow = JSON.stringify(page_params.narrow);
    }

    let update_loading_indicator = opts.msg_list === current_msg_list;
    if (opts.num_before > 0) {
        opts.msg_list.data.fetch_status.start_older_batch({
            update_loading_indicator,
        });
        if (opts.msg_list === home_msg_list) {
            message_list.all.data.fetch_status.start_older_batch({
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
        if (opts.msg_list === home_msg_list) {
            message_list.all.data.fetch_status.start_newer_batch({
                update_loading_indicator,
            });
        }
    }

    data.client_gravatar = true;
    data = handle_operators_supporting_id_based_api(data);

    channel.get({
        url: "/json/messages",
        data,
        idempotent: true,
        success(data) {
            get_messages_success(data, opts);
        },
        error(xhr) {
            if (opts.msg_list.narrowed && opts.msg_list !== current_msg_list) {
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
                const data = {
                    messages: [],
                };
                process_result(data, opts);
                return;
            }

            // We might want to be more clever here
            $("#connection-error").addClass("show");
            setTimeout(() => {
                exports.load_messages(opts);
            }, consts.error_retry_time);
        },
    });
};

exports.load_messages_for_narrow = function (opts) {
    const msg_list = message_list.narrowed;

    exports.load_messages({
        anchor: opts.anchor,
        num_before: consts.narrow_before,
        num_after: consts.narrow_after,
        msg_list,
        cont: opts.cont,
    });
};

exports.get_backfill_anchor = function (msg_list) {
    if (msg_list === home_msg_list) {
        msg_list = message_list.all;
    }

    const oldest_msg = msg_list.first();
    if (oldest_msg) {
        return oldest_msg.id;
    }

    // msg_list is empty, which is an impossible
    // case, raise a fatal error.
    blueslip.fatal("There are no message available to backfill.");
    return;
};

exports.get_frontfill_anchor = function (msg_list) {
    if (msg_list === home_msg_list) {
        msg_list = message_list.all;
    }

    const last_msg = msg_list.last();

    if (last_msg) {
        return last_msg.id;
    }

    // Although it is impossible that we reach here since we
    // are already checking `msg_list.fetch_status.can_load_newer_messages`
    // and user cannot be scrolling down on an empty message_list to
    // fetch more data, and if user is, then the available data is wrong
    // and we raise a fatal error.
    blueslip.fatal("There are no message available to frontfill.");
    return;
};

exports.maybe_load_older_messages = function (opts) {
    // This function gets called when you scroll to the top
    // of your window, and you want to get messages older
    // than what the browsers originally fetched.
    const msg_list = opts.msg_list;
    if (!msg_list.data.fetch_status.can_load_older_messages()) {
        // We may already be loading old messages or already
        // got the oldest one.
        return;
    }

    exports.do_backfill({
        msg_list,
        num_before: consts.backward_batch_size,
    });
};

exports.do_backfill = function (opts) {
    const msg_list = opts.msg_list;
    const anchor = exports.get_backfill_anchor(msg_list);

    exports.load_messages({
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
};

exports.maybe_load_newer_messages = function (opts) {
    // This function gets called when you scroll to the bottom
    // of your window, and you want to get messages newer
    // than what the browsers originally fetched.
    const msg_list = opts.msg_list;

    if (!msg_list.data.fetch_status.can_load_newer_messages()) {
        // We may already be loading new messages or already
        // got the newest one.
        return;
    }

    const anchor = exports.get_frontfill_anchor(msg_list);

    function load_more(data, args) {
        if (args.fetch_again && args.msg_list === current_msg_list) {
            exports.maybe_load_newer_messages({msg_list: current_msg_list});
        }
    }

    exports.load_messages({
        anchor,
        num_before: 0,
        num_after: consts.forward_batch_size,
        msg_list,
        cont: load_more,
    });
};

exports.start_backfilling_messages = function () {
    // backfill more messages after the user is idle
    $(document).idle({
        idle: consts.backfill_idle_time,
        onIdle() {
            exports.do_backfill({
                num_before: consts.backfill_batch_size,
                msg_list: home_msg_list,
            });
        },
    });
};

exports.initialize = function () {
    // get the initial message list
    function load_more(data) {
        // If we haven't selected a message in the home view yet, and
        // the home view isn't empty, we select the anchor message here.
        if (home_msg_list.selected_id() === -1 && !home_msg_list.empty()) {
            // We fall back to the closest selected id, as the user
            // may have removed a stream from the home view while we
            // were loading data.
            home_msg_list.select_id(data.anchor, {
                then_scroll: true,
                use_closest: true,
                target_scroll_offset: page_params.initial_offset,
            });
        }

        if (data.found_newest) {
            server_events.home_view_loaded();
            exports.start_backfilling_messages();
            return;
        }

        // If we fall through here, we need to keep fetching more data, and
        // we'll call back to the function we're in.
        const messages = data.messages;
        const latest_id = messages[messages.length - 1].id;

        exports.load_messages({
            anchor: latest_id,
            num_before: 0,
            num_after: consts.catch_up_batch_size,
            msg_list: home_msg_list,
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
    exports.load_messages({
        anchor,
        num_before: consts.num_before_home_anchor,
        num_after: consts.num_after_home_anchor,
        msg_list: home_msg_list,
        cont: load_more,
    });
};

window.message_fetch = exports;
