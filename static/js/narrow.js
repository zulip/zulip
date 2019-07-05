const util = require("./util");
let unnarrow_times;

const LARGER_THAN_MAX_MESSAGE_ID = 10000000000000000;

function report_narrow_time(initial_core_time, initial_free_time, network_time) {
    channel.post({
        url: '/json/report/narrow_times',
        data: {initial_core: initial_core_time.toString(),
               initial_free: initial_free_time.toString(),
               network: network_time.toString()},
    });
}

function maybe_report_narrow_time(msg_list) {
    if (msg_list.network_time === undefined || msg_list.initial_core_time === undefined ||
        msg_list.initial_free_time === undefined) {
        return;
    }
    report_narrow_time(msg_list.initial_core_time - msg_list.start_time,
                       msg_list.initial_free_time - msg_list.start_time,
                       msg_list.network_time - msg_list.start_time);

}

function report_unnarrow_time() {
    if (unnarrow_times === undefined ||
        unnarrow_times.start_time === undefined ||
        unnarrow_times.initial_core_time === undefined ||
        unnarrow_times.initial_free_time === undefined) {
        return;
    }

    const initial_core_time = unnarrow_times.initial_core_time - unnarrow_times.start_time;
    const initial_free_time = unnarrow_times.initial_free_time - unnarrow_times.start_time;

    channel.post({
        url: '/json/report/unnarrow_times',
        data: {initial_core: initial_core_time.toString(),
               initial_free: initial_free_time.toString()},
    });

    unnarrow_times = {};
}

exports.save_pre_narrow_offset_for_reload = function () {
    if (current_msg_list.selected_id() !== -1) {
        if (current_msg_list.selected_row().length === 0) {
            blueslip.debug("narrow.activate missing selected row", {
                selected_id: current_msg_list.selected_id(),
                selected_idx: current_msg_list.selected_idx(),
                selected_idx_exact: current_msg_list.all_messages().indexOf(
                    current_msg_list.get(current_msg_list.selected_id())),
                render_start: current_msg_list.view._render_win_start,
                render_end: current_msg_list.view._render_win_end,
            });
        }
        current_msg_list.pre_narrow_offset = current_msg_list.selected_row().offset().top;
    }
};

function update_narrow_title(filter) {
    // Take the most detailed part of the narrow to use as the title.
    // If the operator is something other than "stream", "topic", or
    // "is", we shouldn't update the narrow title
    if (filter.has_operator("stream")) {
        if (filter.has_operator("topic")) {
            exports.narrow_title = filter.operands("topic")[0];
        } else {
            exports.narrow_title = filter.operands("stream")[0];
        }
    } else if (filter.has_operator("is")) {
        let title = filter.operands("is")[0];
        title = title.charAt(0).toUpperCase() + title.slice(1) + " messages";
        exports.narrow_title = title;
    } else if (filter.has_operator("pm-with") || filter.has_operator("group-pm-with")) {
        const emails = filter.public_operators()[0].operand;
        const user_ids = people.emails_strings_to_user_ids_string(emails);
        if (user_ids !== undefined) {
            const names = people.get_recipients(user_ids);
            if (filter.has_operator("pm-with")) {
                exports.narrow_title = names;
            } else {
                exports.narrow_title = names + " and others";
            }
        } else {
            if (emails.includes(',')) {
                exports.narrow_title = "Invalid users";
            } else {
                exports.narrow_title = "Invalid user";
            }
        }
    }
    notifications.redraw_title();
}

exports.narrow_title = "home";
exports.activate = function (raw_operators, opts) {
    /* Main entrypoint for switching to a new view / message list.
       Note that for historical reasons related to the current
       client-side caching structure, the "All messages"/home_msg_list
       view is reached via `narrow.deactivate()`.

       The name is based on "narrowing to a subset of the user's
       messages.".  Supported parameters:

       raw_operators: Narrowing/search operators; used to construct
       a Filter object that decides which messages belong in the
       view.  Required (See the above note on how `home_msg_list` works)

       All other options are encoded via the `opts` dictionary:

       * trigger: Optional parameter used mainly for logging and some
         custom UI behavior for certain buttons.  Generally aim to
         have this be unique for each UI widget that can trigger narrowing.

       * change_hash: Whether this narrow should change the URL
         fragment ("hash") in the URL bar.  Should be true unless the
         URL is already correct (E.g. because the hashchange logic
         itself is triggering the change of view).

       * then_select_id: If the caller wants us to do the narrow
         centered on a specific message ID ("anchor" in the API
         parlance), specify that here.  Useful e.g. when the user
         clicks on a specific message; implied by a `near:` operator.

       * then_select_offset: Offset from the top of the page in pixels
         at which to place the then_select_id message following
         rendering.  Important to avoid what would otherwise feel like
         visual glitches after clicking on a specific message's headig
         or rerendering due to server-side changes.
    */

    const start_time = new Date();
    const was_narrowed_already = narrow_state.active();
    // most users aren't going to send a bunch of a out-of-narrow messages
    // and expect to visit a list of narrows, so let's get these out of the way.
    notifications.clear_compose_notifications();

    // Open tooltips are only interesting for current narrow,
    // so hide them when activating a new one.
    $(".tooltip").hide();

    if (raw_operators.length === 0) {
        return exports.deactivate();
    }
    const filter = new Filter(raw_operators);
    const operators = filter.operators();

    update_narrow_title(filter);
    notifications.hide_history_limit_message();
    $(".all-messages-search-caution").hide();

    blueslip.debug("Narrowed", {operators: operators.map(e => e.operator),
                                trigger: opts ? opts.trigger : undefined,
                                previous_id: current_msg_list.selected_id()});

    opts = {
        then_select_id: -1,
        then_select_offset: undefined,
        change_hash: true,
        trigger: 'unknown',
        ...opts,
    };

    const id_info = {
        target_id: undefined,
        local_select_id: undefined,
        final_select_id: undefined,
    };

    // These two narrowing operators specify what message should be
    // selected and should be the center of the narrow.
    if (filter.has_operator("near")) {
        id_info.target_id = parseInt(filter.operands("near")[0], 10);
    }
    if (filter.has_operator("id")) {
        id_info.target_id = parseInt(filter.operands("id")[0], 10);
    }

    if (opts.then_select_id > 0) {
        // We override target_id in this case, since the user could be
        // having a near: narrow auto-reloaded.
        id_info.target_id = opts.then_select_id;
        if (opts.then_select_offset === undefined) {
            const row = current_msg_list.get_row(opts.then_select_id);
            if (row.length > 0) {
                opts.then_select_offset = row.offset().top;
            }
        }
    }

    if (!was_narrowed_already) {
        unread.set_messages_read_in_narrow(false);
    }

    // IMPORTANT!  At this point we are heavily committed to
    // populating the new narrow, so we update our narrow_state.
    // From here on down, any calls to the narrow_state API will
    // reflect the upcoming narrow.
    narrow_state.set_current_filter(filter);

    const muting_enabled = narrow_state.muting_enabled();

    // Save how far from the pointer the top of the message list was.
    exports.save_pre_narrow_offset_for_reload();

    let msg_data =  new MessageListData({
        filter: narrow_state.filter(),
        muting_enabled: muting_enabled,
    });

    // Populate the message list if we can apply our filter locally (i.e.
    // with no backend help) and we have the message we want to select.
    // Also update id_info accordingly.
    // original back.
    exports.maybe_add_local_messages({
        id_info: id_info,
        msg_data: msg_data,
    });

    if (!id_info.local_select_id) {
        // If we're not actually read to select an ID, we need to
        // trash the `MessageListData` object that we just constructed
        // and pass an empty one to MessageList, because the block of
        // messages in the MessageListData built inside
        // maybe_add_local_messages is likely not be contiguous with
        // the block we're about to request from the server instead.
        msg_data = new MessageListData({
            filter: narrow_state.filter(),
            muting_enabled: muting_enabled,
        });
    }

    const msg_list = new message_list.MessageList({
        data: msg_data,
        table_name: 'zfilt',
        collapse_messages: !narrow_state.filter().is_search(),
    });

    msg_list.start_time = start_time;

    // Show the new set of messages.  It is important to set current_msg_list to
    // the view right as it's being shown, because we rely on current_msg_list
    // being shown for deciding when to condense messages.
    $("body").addClass("narrowed_view");
    $("#zfilt").addClass("focused_table");
    $("#zhome").removeClass("focused_table");

    ui_util.change_tab_to('#home');
    message_list.set_narrowed(msg_list);
    current_msg_list = message_list.narrowed;

    let then_select_offset;
    if (id_info.target_id === id_info.final_select_id) {
        then_select_offset = opts.then_select_offset;
    }

    const select_immediately = id_info.local_select_id !== undefined;

    (function fetch_messages() {
        let anchor;

        // Either we're trying to center the narrow around a
        // particular message ID (which could be max_int), or we're
        // asking the server to figure out for us what the first
        // unread message is, and center the narrow around that.
        if (id_info.final_select_id === undefined) {
            anchor = "first_unread";
        } else if (id_info.final_select_id === -1) {
            // This case should never happen in this code path; it's
            // here in case we choose to extract this as an
            // independent reusable function.
            anchor = "oldest";
        } else if (id_info.final_select_id === LARGER_THAN_MAX_MESSAGE_ID) {
            anchor = "newest";
        } else {
            anchor = id_info.final_select_id;
        }

        message_fetch.load_messages_for_narrow({
            anchor: anchor,
            cont: function () {
                if (!select_immediately) {
                    exports.update_selection({
                        id_info: id_info,
                        select_offset: then_select_offset,
                    });
                }
                msg_list.network_time = new Date();
                maybe_report_narrow_time(msg_list);
            },
            pre_scroll_cont: function () {
                // Potentially display the notice that lets users know
                // that not all messages were searched.  One could
                // imagine including `filter.is_search()` in these
                // conditions, but there's a very legitimate use case
                // for moderation of searching for all messages sent
                // by a potential spammer user.
                if (!filter.contains_only_private_messages() &&
                    !filter.includes_full_stream_history() &&
                    !filter.is_personal_filter()) {
                    $(".all-messages-search-caution").show();
                    // Set the link to point to this search with streams:public added.
                    // It's a bit hacky to use the href, but
                    // !filter.includes_full_stream_history() implies streams:public
                    // wasn't already present.
                    $(".all-messages-search-caution a.search-shared-history").attr(
                        "href", window.location.hash.replace("#narrow/", "#narrow/streams/public/")
                    );
                }
            },
        });
    }());

    if (select_immediately) {
        message_scroll.hide_indicators();
        exports.update_selection({
            id_info: id_info,
            select_offset: then_select_offset,
        });
    } else {
        message_scroll.show_loading_older();
    }

    // Put the narrow operators in the URL fragment.
    // Disabled when the URL fragment was the source
    // of this narrow.
    if (opts.change_hash) {
        hashchange.save_narrow(operators);
    }

    if (page_params.search_pills_enabled && opts.trigger !== 'search') {
        search_pill_widget.widget.clear(true);

        for (const operator of operators) {
            const search_string = Filter.unparse([operator]);
            search_pill.append_search_string(search_string, search_pill_widget.widget);
        }
    }

    if (filter.contains_only_private_messages()) {
        compose.update_closed_compose_buttons_for_private();
    } else {
        compose.update_closed_compose_buttons_for_stream();
    }

    // Put the narrow operators in the search bar.
    // we append a space to make searching more convenient in some cases.
    if (filter && !filter.is_search()) {
        $('#search_query').val(Filter.unparse(operators) + " ");
    }

    search.update_button_visibility();

    compose_actions.on_narrow(opts);

    const current_filter = narrow_state.filter();

    top_left_corner.handle_narrow_activated(current_filter);
    stream_list.handle_narrow_activated(current_filter);
    typing_events.render_notifications_for_narrow();
    tab_bar.initialize();

    // this is to refresh the buddy list to sync with the new narrow for the stream member feature,
    // ideally, we should be able to check if the list has changed between the previous and the
    // current narrow (through something like buddy_data.maybe_redraw()) but for now,
    // we just do the bare minimum check to see if the stream member mode is active
    if (buddy_data.should_show_only_recipients()) {
        activity.redraw();
    }

    msg_list.initial_core_time = new Date();
    setTimeout(function () {
        resize.resize_stream_filters_container();
        msg_list.initial_free_time = new Date();
        maybe_report_narrow_time(msg_list);
    }, 0);
};

function min_defined(a, b) {
    if (a === undefined) {
        return b;
    }
    if (b === undefined) {
        return a;
    }
    return a < b ? a : b;
}

function load_local_messages(msg_data) {
    // This little helper loads messages into our narrow message
    // data and returns true unless it's empty.  We use this for
    // cases when our local cache (message_list.all) has at least
    // one message the user will expect to see in the new narrow.

    const in_msgs = message_list.all.all_messages();
    msg_data.add_messages(in_msgs);

    return !msg_data.empty();
}

exports.maybe_add_local_messages = function (opts) {
    // This function determines whether we need to go to the server to
    // fetch messages for the requested narrow, or whether we have the
    // data cached locally to render the narrow correctly without
    // waiting for the server.  There are two high-level outcomes:
    //
    // 1. We're centering this narrow on the first unread message: In
    // this case final_select_id is left undefined or first unread
    // message id locally.
    //
    // 2. We're centering this narrow on the most recent matching
    // message. In this case we select final_select_id to the latest
    // message in the local cache (if the local cache has the latest
    // messages for this narrow) or max_int (if it doesn't).
    //
    // In either case, this function does two very closely related
    // things, both of which are somewhat optional:
    //
    //  - update id_info with more complete values
    //  - add messages into our message list from our local cache
    const id_info = opts.id_info;
    const msg_data = opts.msg_data;
    const unread_info = narrow_state.get_first_unread_info();

    // If we don't have a specific message we're hoping to select
    // (i.e. no `target_id`) and the narrow's filter doesn't
    // allow_use_first_unread_when_narrowing, we want to just render
    // the latest messages matching the filter.  To ensure this, we
    // set an initial value final_select_id to `max_int`.
    //
    // While that's a confusing naming choice (`final_select_id` is
    // meant to be final in the context of the caller), this sets the
    // default behavior to be fetching and then selecting the very
    // latest message in this narrow.
    //
    // If we're able to render the narrow locally, we'll end up
    // overwriting this value with the ID of the latest message in the
    // narrow later in this function.
    if (!id_info.target_id && !narrow_state.filter().allow_use_first_unread_when_narrowing()) {
        // Note that this may be overwritten; see above comment.
        id_info.final_select_id = LARGER_THAN_MAX_MESSAGE_ID;
    }

    if (unread_info.flavor === 'cannot_compute') {
        // Full-text search and potentially other future cases where
        // we can't check which messages match on the frontend, so it
        // doesn't matter what's in our cache, we must go to the server.
        if (id_info.target_id) {
            // TODO: Ideally, in this case we should be asking the
            // server to give us the first unread or the target_id,
            // whichever is first (i.e. basically the `found` logic
            // below), but the server doesn't support that query.
            id_info.final_select_id = id_info.target_id;
        }
        // if we can't compute a next unread id, just return without
        // setting local_select_id, so that we go to the server.
        return;
    }

    // We can now assume narrow_state.filter().can_apply_locally(),
    // because !can_apply_locally => cannot_compute

    if (unread_info.flavor === 'found' &&
            narrow_state.filter().allow_use_first_unread_when_narrowing()) {
        // We have at least one unread message in this narrow, and the
        // narrow is one where we use the first unread message in
        // narrowing positioning decisions.  So either we aim for the
        // first unread message, or the target_id (if any), whichever
        // is earlier.  See #2091 for a detailed explanation of why we
        // need to look at unread here.
        id_info.final_select_id = min_defined(
            id_info.target_id,
            unread_info.msg_id
        );

        if (!load_local_messages(msg_data)) {
            return;
        }

        // Now that we know what message ID we're going to land on, we
        // can see if we can take the user there locally.
        if (msg_data.get(id_info.final_select_id)) {
            id_info.local_select_id = id_info.final_select_id;
        }

        // If we don't have the first unread message locally, we must
        // go to the server to get it before we can render the narrow.
        return;
    }

    // In all cases below here, the first unread message is irrelevant
    // to our positioning decisions, either because there are no
    // unread messages (unread_info.flavor === 'not_found') or because
    // this is a mixed narrow where we prefer the bottom of the feed
    // to the first unread message for positioning (and the narrow
    // will be configured to not mark messages as read).

    if (!id_info.target_id) {
        // Without unread messages or a target ID, we're narrowing to
        // the very latest message or first unread if matching the narrow allows.

        if (!message_list.all.fetch_status.has_found_newest()) {
            // If message_list.all is not caught up, then we cannot
            // populate the latest messages for the target narrow
            // correctly from there, so we must go to the server.
            return;
        }
        if (!load_local_messages(msg_data)) {
            return;
        }
        // Otherwise, we have matching messages, and message_list.all
        // is caught up, so the last message in our now-populated
        // msg_data object must be the last message matching the
        // narrow the server could give us, so we can render locally.
        // and use local latest message id instead of max_int if set earlier.
        const last_msg = msg_data.last();
        id_info.final_select_id = last_msg.id;
        id_info.local_select_id = id_info.final_select_id;
        return;
    }

    // We have a target_id and no unread messages complicating things,
    // so we definitely want to land on the target_id message.
    id_info.final_select_id = id_info.target_id;

    // TODO: We could improve on this next condition by considering
    // cases where `message_list.all.has_found_oldest(); which would
    // come up with e.g. `near: 0` in a small organization.
    //
    // And similarly for `near: max_int` with has_found_newest.
    if (message_list.all.empty() ||
        id_info.target_id < message_list.all.first().id ||
        id_info.target_id > message_list.all.last().id) {
        // If the target message is outside the range that we had
        // available for local population, we must go to the server.
        return;
    }
    if (!load_local_messages(msg_data)) {
        return;
    }
    if (msg_data.get(id_info.target_id)) {
        // We have a range of locally renderable messages, including
        // our target, so we can render the narrow locally.
        id_info.local_select_id = id_info.final_select_id;
        return;
    }

    // Note: Arguably, we could have a use_closest sort of condition
    // here to handle cases where `target_id` doesn't match the narrow
    // but is within the locally renderable range.  But
    // !can_apply_locally + target_id is a rare combination in the
    // first place, so we don't bother.
    return;
};

exports.update_selection = function (opts) {
    if (message_list.narrowed.empty()) {
        return;
    }

    const id_info = opts.id_info;
    const select_offset = opts.select_offset;

    let msg_id = id_info.final_select_id;
    if (msg_id === undefined) {
        msg_id = message_list.narrowed.first_unread_message_id();
    }

    const preserve_pre_narrowing_screen_position =
        message_list.narrowed.get(msg_id) !== undefined &&
        select_offset !== undefined;

    const then_scroll = !preserve_pre_narrowing_screen_position;

    message_list.narrowed.select_id(msg_id, {
        then_scroll: then_scroll,
        use_closest: true,
        force_rerender: true,
    });

    if (preserve_pre_narrowing_screen_position) {
        // Scroll so that the selected message is in the same
        // position in the viewport as it was prior to
        // narrowing
        message_list.narrowed.view.set_message_offset(select_offset);
    }
    unread_ops.process_visible();
};

exports.activate_stream_for_cycle_hotkey = function (stream_name) {
    // This is the common code for A/D hotkeys.
    const filter_expr = [
        {operator: 'stream', operand: stream_name},
    ];
    exports.activate(filter_expr, {});
};


exports.stream_cycle_backward = function () {
    const curr_stream = narrow_state.stream();

    if (!curr_stream) {
        return;
    }

    const stream_name = topic_generator.get_prev_stream(curr_stream);

    if (!stream_name) {
        return;
    }

    exports.activate_stream_for_cycle_hotkey(stream_name);
};

exports.stream_cycle_forward = function () {
    const curr_stream = narrow_state.stream();

    if (!curr_stream) {
        return;
    }

    const stream_name = topic_generator.get_next_stream(curr_stream);

    if (!stream_name) {
        return;
    }

    exports.activate_stream_for_cycle_hotkey(stream_name);
};

exports.narrow_to_next_topic = function () {
    const curr_info = {
        stream: narrow_state.stream(),
        topic: narrow_state.topic(),
    };

    const next_narrow = topic_generator.get_next_topic(
        curr_info.stream,
        curr_info.topic
    );

    if (!next_narrow) {
        return;
    }

    const filter_expr = [
        {operator: 'stream', operand: next_narrow.stream},
        {operator: 'topic', operand: next_narrow.topic},
    ];

    exports.activate(filter_expr, {});
};

exports.narrow_to_next_pm_string = function () {

    const curr_pm = narrow_state.pm_string();

    const next_pm = topic_generator.get_next_unread_pm_string(curr_pm);

    if (!next_pm) {
        return;
    }

    // Hopefully someday we can narrow by user_ids_string instead of
    // mapping back to emails.
    const pm_with = people.user_ids_string_to_emails_string(next_pm);

    const filter_expr = [
        {operator: 'pm-with', operand: pm_with},
    ];

    // force_close parameter is true to not auto open compose_box
    const opts = {
        force_close: true,
    };

    exports.activate(filter_expr, opts);
};


// Activate narrowing with a single operator.
// This is just for syntactic convenience.
exports.by = function (operator, operand, opts) {
    exports.activate([{operator: operator, operand: operand}], opts);
};

exports.by_topic = function (target_id, opts) {
    // don't use current_msg_list as it won't work for muted messages or for out-of-narrow links
    const original = message_store.get(target_id);
    if (original.type !== 'stream') {
        // Only stream messages have topics, but the
        // user wants us to narrow in some way.
        exports.by_recipient(target_id, opts);
        return;
    }

    // We don't check msg_list.can_mark_messages_read here only because
    // the target msg_list isn't initialized yet; in any case, the
    // message is about to be marked read in the new view.
    unread_ops.notify_server_message_read(original);

    const search_terms = [
        {operator: 'stream', operand: original.stream},
        {operator: 'topic', operand: original.topic},
    ];
    opts = { then_select_id: target_id, ...opts };
    exports.activate(search_terms, opts);
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function (target_id, opts) {
    opts = { then_select_id: target_id, ...opts };
    // don't use current_msg_list as it won't work for muted messages or for out-of-narrow links
    const message = message_store.get(target_id);

    // We don't check msg_list.can_mark_messages_read here only because
    // the target msg_list isn't initialized yet; in any case, the
    // message is about to be marked read in the new view.
    unread_ops.notify_server_message_read(message);

    switch (message.type) {
    case 'private':
        exports.by('pm-with', message.reply_to, opts);
        break;

    case 'stream':
        exports.by('stream', message.stream, opts);
        break;
    }
};

// Called by the narrow_to_compose_target hotkey.
exports.to_compose_target = function () {
    if (!compose_state.composing()) {
        return;
    }

    const opts = {
        trigger: 'narrow_to_compose_target',
    };

    if (compose_state.get_message_type() === 'stream') {
        const stream_name = compose_state.stream_name();
        const stream_id = stream_data.get_stream_id(stream_name);
        if (!stream_id) {
            return;
        }
        // If we are composing to a new topic, we narrow to the stream but
        // grey-out the message view instead of narrowing to an empty view.
        const topics = stream_topic_history.get_recent_topic_names(stream_id);
        const operators = [{operator: 'stream', operand: stream_name}];
        const topic = compose_state.topic();
        if (topics.includes(topic)) {
            operators.push({operator: 'topic', operand: topic});
        }
        exports.activate(operators, opts);
        return;
    }

    if (compose_state.get_message_type() === 'private') {
        const recipient_string = compose_state.private_message_recipient();
        const emails = util.extract_pm_recipients(recipient_string);
        const invalid = emails.filter(email => !people.is_valid_email_for_compose(email));
        // If there are no recipients or any recipient is
        // invalid, narrow to all PMs.
        if (emails.length === 0 || invalid.length > 0) {
            exports.by('is', 'private', opts);
            return;
        }
        exports.by('pm-with', util.normalize_recipients(recipient_string), opts);
    }
};

function handle_post_narrow_deactivate_processes() {
    compose_fade.update_message_list();

    // clear existing search pills
    if (page_params.search_pills_enabled) {
        search_pill_widget.widget.clear(true);
    }

    top_left_corner.handle_narrow_deactivated();
    stream_list.handle_narrow_deactivated();
    compose.update_closed_compose_buttons_for_stream();
    message_edit.handle_narrow_deactivated();
    widgetize.set_widgets_for_list();
    typing_events.render_notifications_for_narrow();
    tab_bar.initialize();
    exports.narrow_title = "home";
    notifications.redraw_title();
    notifications.hide_or_show_history_limit_message(home_msg_list);
    $(".all-messages-search-caution").hide();

    // When a different mode of the buddy list is active, we need to redraw
    // to ensure that we're showing the right list of users
    if (buddy_data.should_show_only_recipients()) {
        activity.redraw();
    }
}

exports.deactivate = function () {
    /*
      Switches current_msg_list from narrowed_msg_list to
      home_msg_list ("All messages"), ending the current narrow.  This
      is a very fast operation, because we keep home_msg_list's data
      cached and updated in the DOM at all times, making it suitable
      for rapid access via keyboard shortcuts.

      Long-term, we will likely want to make `home_msg_list` not
      special in any way, and instead just have a generic
      message_list_data structure caching system that happens to have
      home_msg_list in it.
     */
    search.clear_search_form();
    if (narrow_state.filter() === undefined) {
        return;
    }
    unnarrow_times = {start_time: new Date()};
    blueslip.debug("Unnarrowed");

    if (message_scroll.actively_scrolling()) {
        // There is no way to intercept in-flight scroll events, and they will
        // cause you to end up in the wrong place if you are actively scrolling
        // on an unnarrow. Wait a bit and try again once the scrolling is over.
        setTimeout(exports.deactivate, 50);
        return;
    }

    if (!compose_state.has_message_content()) {
        compose_actions.cancel();
    }

    narrow_state.reset_current_filter();

    exports.hide_empty_narrow_message();

    $("body").removeClass('narrowed_view');
    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    current_msg_list = home_msg_list;
    condense.condense_and_collapse($("#zhome div.message_row"));

    message_scroll.hide_indicators();
    hashchange.save_narrow();

    if (current_msg_list.selected_id() !== -1) {
        const preserve_pre_narrowing_screen_position =
            current_msg_list.selected_row().length > 0 &&
            current_msg_list.pre_narrow_offset !== undefined;
        let message_id_to_select;
        const select_opts = {
            then_scroll: true,
            use_closest: true,
            empty_ok: true,
        };

        // We fall back to the closest selected id, if the user has removed a
        // stream from the home view since leaving it the old selected id might
        // no longer be there
        // Additionally, we pass empty_ok as the user may have removed **all** streams
        // from their home view
        if (unread.messages_read_in_narrow) {
            // We read some unread messages in a narrow. Instead of going back to
            // where we were before the narrow, go to our first unread message (or
            // the bottom of the feed, if there are no unread messages).
            message_id_to_select = current_msg_list.first_unread_message_id();
        } else {
            // We narrowed, but only backwards in time (ie no unread were read). Try
            // to go back to exactly where we were before narrowing.
            if (preserve_pre_narrowing_screen_position) {
                // We scroll the user back to exactly the offset from the selected
                // message that they were at the time that they narrowed.
                // TODO: Make this correctly handle the case of resizing while narrowed.
                select_opts.target_scroll_offset = current_msg_list.pre_narrow_offset;
            }
            message_id_to_select = current_msg_list.selected_id();
        }
        current_msg_list.select_id(message_id_to_select, select_opts);
    }

    handle_post_narrow_deactivate_processes();

    unnarrow_times.initial_core_time = new Date();
    setTimeout(function () {
        resize.resize_stream_filters_container();
        unnarrow_times.initial_free_time = new Date();
        report_unnarrow_time();
    });
};

exports.restore_home_state = function () {
    // If we click on the All Messages link while already at All Messages, unnarrow.
    // If we click on the All Messages link from another nav pane, just go
    // back to the state you were in (possibly still narrowed) before
    // you left the All Messages pane.
    if (!overlays.is_active()) {
        exports.deactivate();
    }
    navigate.maybe_scroll_to_selected();
};

function set_invalid_narrow_message(invalid_narrow_message) {
    const search_string_display = $("#empty_search_stop_words_string");
    search_string_display.text(invalid_narrow_message);
}

function show_search_query() {
    // when search bar contains multiple filters, only show search queries
    const current_filter = narrow_state.filter();
    const search_query = current_filter.operands("search")[0];
    const query_words = search_query.split(" ");

    const search_string_display = $("#empty_search_stop_words_string");
    let query_contains_stop_words = false;

    // Also removes previous search_string if any
    search_string_display.text(i18n.t("You searched for:"));

    // Add in stream:foo and topic:bar if present
    if (current_filter.has_operator("stream") || current_filter.has_operator("topic")) {
        let stream_topic_string = "";
        const stream = current_filter.operands('stream')[0];
        const topic = current_filter.operands('topic')[0];
        if (stream) {
            stream_topic_string = "stream: " + stream;
        }
        if (topic) {
            stream_topic_string = stream_topic_string + " topic: " + topic;
        }

        search_string_display.append(' ');
        search_string_display.append($('<span>').text(stream_topic_string));
    }

    for (const query_word of query_words) {
        search_string_display.append(' ');

        // if query contains stop words, it is enclosed by a <del> tag
        if (page_params.stop_words.includes(query_word)) {
            // stop_words do not need sanitization so this is unnecessary but it is fail-safe.
            search_string_display.append($('<del>').text(query_word));
            query_contains_stop_words = true;
        } else {
            // We use .text("...") to sanitize the user-given query_string.
            search_string_display.append($('<span>').text(query_word));
        }
    }

    if (query_contains_stop_words) {
        search_string_display.html(i18n.t(
            "Some common words were excluded from your search.") + "<br/>" + search_string_display.html());
    }
}

function pick_empty_narrow_banner() {
    const default_banner = $('#empty_narrow_message');

    const current_filter = narrow_state.filter();

    if (current_filter === undefined) {
        return default_banner;
    }

    const first_term = current_filter.operators()[0];
    const first_operator = first_term.operator;
    const first_operand = first_term.operand;
    const num_operators = current_filter.operators().length;

    if (num_operators !== 1) {
        // For invalid-multi-operator narrows, we display an invalid narrow message
        const streams = current_filter.operands("stream");

        let invalid_narrow_message = "";
        // No message can have multiple streams
        if (streams.length > 1) {
            invalid_narrow_message = i18n.t("You are searching for messages that belong to more than one stream, which is not possible.");
        }
        // No message can have multiple topics
        if (current_filter.operands("topic").length > 1) {
            invalid_narrow_message = i18n.t("You are searching for messages that belong to more than one topic, which is not possible.");
        }
        // No message can have multiple senders
        if (current_filter.operands("sender").length > 1) {
            invalid_narrow_message = i18n.t("You are searching for messages that are sent by more than one person, which is not possible.");
        }
        if (invalid_narrow_message !== "") {
            set_invalid_narrow_message(invalid_narrow_message);
            return $("#empty_search_narrow_message");
        }

        // For empty stream searches within other narrows, we display the stop words
        if (current_filter.operands("search").length > 0) {
            show_search_query();
            return $("#empty_search_narrow_message");
        }
        // For other multi-operator narrows, we just use the default banner
        return default_banner;
    } else if (first_operator === "is") {
        if (first_operand === "starred") {
            // You have no starred messages.
            return $("#empty_star_narrow_message");
        } else if (first_operand === "mentioned") {
            return $("#empty_narrow_all_mentioned");
        } else if (first_operand === "private") {
            // You have no private messages.
            return $("#empty_narrow_all_private_message");
        } else if (first_operand === "unread") {
            // You have no unread messages.
            return $("#no_unread_narrow_message");
        }
    } else if (first_operator === "stream" && !stream_data.is_subscribed(first_operand)) {
        // You are narrowed to a stream which does not exist or is a private stream
        // in which you were never subscribed.

        function should_display_subscription_button() {
            const stream_name = narrow_state.stream();

            if (!stream_name) {
                return false;
            }

            const stream_sub = stream_data.get_sub(first_operand);
            return stream_sub && stream_sub.should_display_subscription_button;
        }

        if (should_display_subscription_button()) {
            return $("#nonsubbed_stream_narrow_message");
        }

        return $("#nonsubbed_private_nonexistent_stream_narrow_message");
    } else if (first_operator === "search") {
        // You are narrowed to empty search results.
        show_search_query();
        return $("#empty_search_narrow_message");
    } else if (first_operator === "pm-with") {
        if (!people.is_valid_bulk_emails_for_compose(first_operand.split(','))) {
            if (!first_operand.includes(',')) {
                return $("#non_existing_user");
            }
            return $("#non_existing_users");
        }
        if (!first_operand.includes(',')) {
            // You have no private messages with this person
            if (people.is_current_user(first_operand)) {
                return $("#empty_narrow_self_private_message");
            }
            return $("#empty_narrow_private_message");
        }
        return $("#empty_narrow_multi_private_message");
    } else if (first_operator === "sender") {
        if (people.get_by_email(first_operand)) {
            return $("#silent_user");
        }
        return $("#non_existing_user");
    } else if (first_operator === "group-pm-with") {
        return $("#empty_narrow_group_private_message");
    }
    return default_banner;
}

exports.show_empty_narrow_message = function () {
    $(".empty_feed_notice").hide();
    pick_empty_narrow_banner().show();
    $("#left_bar_compose_reply_button_big").attr("title", i18n.t("There are no messages to reply to."));
    $("#left_bar_compose_reply_button_big").attr("disabled", "disabled");
};

exports.hide_empty_narrow_message = function () {
    $(".empty_feed_notice").hide();
    $("#left_bar_compose_reply_button_big").attr("title", i18n.t("Reply (r)"));
    $("#left_bar_compose_reply_button_big").removeAttr("disabled");
};

window.narrow = exports;
