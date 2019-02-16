var narrow = (function () {

var exports = {};

var unnarrow_times;

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

    var initial_core_time = unnarrow_times.initial_core_time - unnarrow_times.start_time;
    var initial_free_time = unnarrow_times.initial_free_time - unnarrow_times.start_time;

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

exports.narrow_title = "home";
exports.activate = function (raw_operators, opts) {
    var start_time = new Date();
    var was_narrowed_already = narrow_state.active();
    // most users aren't going to send a bunch of a out-of-narrow messages
    // and expect to visit a list of narrows, so let's get these out of the way.
    notifications.clear_compose_notifications();

    if (raw_operators.length === 0) {
        return exports.deactivate();
    }
    var filter = new Filter(raw_operators);
    var operators = filter.operators();

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
        exports.narrow_title = filter.operands("is")[0];
    } else if (filter.has_operator("pm-with")) {
        exports.narrow_title = "private";
    } else if (filter.has_operator("group-pm-with")) {
        exports.narrow_title = "private group";
    }

    notifications.redraw_title();
    notifications.hide_history_limit_message();
    blueslip.debug("Narrowed", {operators: _.map(operators,
                                                 function (e) { return e.operator; }),
                                trigger: opts ? opts.trigger : undefined,
                                previous_id: current_msg_list.selected_id()});

    opts = _.defaults({}, opts, {
        then_select_id: -1,
        then_select_offset: undefined,
        change_hash: true,
        trigger: 'unknown',
    });

    var id_info = {
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
            var row = current_msg_list.get_row(opts.then_select_id);
            if (row.length > 0) {
                opts.then_select_offset = row.offset().top;
            }
        }
    }

    if (!was_narrowed_already) {
        unread.messages_read_in_narrow = false;
    }

    // IMPORTANT!  At this point we are heavily committed to
    // populating the new narrow, so we update our narrow_state.
    // From here on down, any calls to the narrow_state API will
    // reflect the upcoming narrow.
    narrow_state.set_current_filter(filter);

    var muting_enabled = narrow_state.muting_enabled();

    // Save how far from the pointer the top of the message list was.
    exports.save_pre_narrow_offset_for_reload();

    var msg_data =  new MessageListData({
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

    var msg_list = new message_list.MessageList({
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
    message_list.narrowed = msg_list;
    current_msg_list = message_list.narrowed;

    var then_select_offset;
    if (id_info.target_id === id_info.final_select_id) {
        then_select_offset = opts.then_select_offset;
    }

    var select_immediately = id_info.local_select_id !== undefined;

    (function fetch_messages() {
        var anchor;
        var use_first_unread;

        if (id_info.final_select_id !== undefined) {
            anchor = id_info.final_select_id;
            use_first_unread = false;
        } else {
            anchor = -1;
            use_first_unread = true;
        }

        message_fetch.load_messages_for_narrow({
            then_select_id: anchor,
            use_first_unread_anchor: use_first_unread,
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
        _.each(operators, function (operator) {
            var search_string = Filter.unparse([operator]);
            search_pill.append_search_string(search_string, search_pill_widget.widget);
        });
    }

    if (filter.has_operator("is") && filter.operands("is")[0] === "private"
        || filter.has_operator("pm-with") || filter.has_operator("group-pm-with")) {
        compose.update_stream_button_for_private();
    } else {
        compose.update_stream_button_for_stream();
    }

    // Put the narrow operators in the search bar.
    $('#search_query').val(Filter.unparse(operators));
    search.update_button_visibility();

    compose_actions.on_narrow(opts);

    var current_filter = narrow_state.filter();

    top_left_corner.handle_narrow_activated(current_filter);
    stream_list.handle_narrow_activated(current_filter);
    typing_events.render_notifications_for_narrow();
    tab_bar.initialize();

    msg_list.initial_core_time = new Date();
    setTimeout(function () {
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

    var in_msgs = message_list.all.all_messages();
    msg_data.add_messages(in_msgs);

    return !msg_data.empty();
}

exports.maybe_add_local_messages = function (opts) {
    // This function does two very closely related things, both of
    // which are somewhat optional:
    //
    //  - update id_info with more complete values
    //  - add messages into our message list from our local cache
    var id_info = opts.id_info;
    var msg_data = opts.msg_data;
    var unread_info = narrow_state.get_first_unread_info();

    if (unread_info.flavor === 'cannot_compute') {
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

    if (unread_info.flavor === 'found') {
        // We have at least one unread message in this narrow.  So
        // either we aim for the first unread message, or the
        // target_id (if any), whichever is earlier.  See #2091 for a
        // detailed explanation of why we need to look at unread here.
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

    // Now we know that there are no unread messages, because
    //   unread_info.flavor === 'not_found'

    if (!id_info.target_id) {
        // Without unread messages or a target ID, we're narrowing to
        // the very latest message matching the narrow.

        // TODO: A possible optimization in this code path is to set
        // `id_info.final_select_id` to be `max_int` here, i.e. saving the
        // server the first_unread query when we need the server.
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
        var last_msg = msg_data.last();
        id_info.final_select_id = last_msg.id;
        id_info.local_select_id = id_info.final_select_id;
        return;
    }

    // We have a target_id and no unread messages complicating things,
    // so we definitely want to land on the target_id message.
    id_info.final_select_id = id_info.target_id;

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

    var id_info = opts.id_info;
    var select_offset = opts.select_offset;

    var msg_id = id_info.final_select_id;
    if (msg_id === undefined) {
        msg_id = message_list.narrowed.first_unread_message_id();
    }

    var preserve_pre_narrowing_screen_position =
        message_list.narrowed.get(msg_id) !== undefined &&
        select_offset !== undefined;

    var then_scroll = !preserve_pre_narrowing_screen_position;

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

exports.stream_topic = function () {
    // This function returns the stream/topic that we most
    // specifically care about, according (mostly) to the
    // currently selected message.
    var msg = current_msg_list.selected_message();

    if (msg) {
        return {
            stream: msg.stream || undefined,
            topic: util.get_message_topic(msg) || undefined,
        };
    }

    // We may be in an empty narrow.  In that case we use
    // our narrow parameters to return the stream/topic.
    return {
        stream: narrow_state.stream(),
        topic: narrow_state.topic(),
    };
};

exports.activate_stream_for_cycle_hotkey = function (stream_name) {
    // This is the common code for A/D hotkeys.
    var filter_expr = [
        {operator: 'stream', operand: stream_name},
    ];
    exports.activate(filter_expr, {});
};


exports.stream_cycle_backward = function () {
    var curr_stream = narrow_state.stream();

    if (!curr_stream) {
        return;
    }

    var stream_name = topic_generator.get_prev_stream(curr_stream);

    if (!stream_name) {
        return;
    }

    exports.activate_stream_for_cycle_hotkey(stream_name);
};

exports.stream_cycle_forward = function () {
    var curr_stream = narrow_state.stream();

    if (!curr_stream) {
        return;
    }

    var stream_name = topic_generator.get_next_stream(curr_stream);

    if (!stream_name) {
        return;
    }

    exports.activate_stream_for_cycle_hotkey(stream_name);
};

exports.narrow_to_next_topic = function () {
    var curr_info = exports.stream_topic();

    if (!curr_info) {
        return;
    }

    var next_narrow = topic_generator.get_next_topic(
        curr_info.stream,
        curr_info.topic
    );

    if (!next_narrow) {
        return;
    }

    var filter_expr = [
        {operator: 'stream', operand: next_narrow.stream},
        {operator: 'topic', operand: next_narrow.topic},
    ];

    exports.activate(filter_expr, {});
};

exports.narrow_to_next_pm_string = function () {

    var curr_pm = narrow_state.pm_string();

    var next_pm = topic_generator.get_next_unread_pm_string(curr_pm);

    if (!next_pm) {
        return;
    }

    // Hopefully someday we can narrow by user_ids_string instead of
    // mapping back to emails.
    var pm_with = people.user_ids_string_to_emails_string(next_pm);

    var filter_expr = [
        {operator: 'pm-with', operand: pm_with},
    ];

    // force_close parameter is true to not auto open compose_box
    var opts = {
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
    var original = message_store.get(target_id);
    if (original.type !== 'stream') {
        // Only stream messages have topics, but the
        // user wants us to narrow in some way.
        exports.by_recipient(target_id, opts);
        return;
    }
    unread_ops.notify_server_message_read(original);
    var search_terms = [
        {operator: 'stream', operand: original.stream},
        {operator: 'topic', operand: util.get_message_topic(original)},
    ];
    opts = _.defaults({}, opts, {then_select_id: target_id});
    exports.activate(search_terms, opts);
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function (target_id, opts) {
    opts = _.defaults({}, opts, {then_select_id: target_id});
    // don't use current_msg_list as it won't work for muted messages or for out-of-narrow links
    var message = message_store.get(target_id);
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

    var opts = {
        trigger: 'narrow_to_compose_target',
    };

    if (compose_state.get_message_type() === 'stream') {
        var stream_name = compose_state.stream_name();
        var stream_id = stream_data.get_stream_id(stream_name);
        if (!stream_id) {
            return;
        }
        // If we are composing to a new topic, we narrow to the stream but
        // grey-out the message view instead of narrowing to an empty view.
        var topics = topic_data.get_recent_names(stream_id);
        var operators = [{operator: 'stream', operand: stream_name}];
        var topic = compose_state.topic();
        if (topics.indexOf(topic) !== -1) {
            operators.push({operator: 'topic', operand: topic});
        }
        exports.activate(operators, opts);
        return;
    }

    if (compose_state.get_message_type() === 'private') {
        var recipient_string = compose_state.recipient();
        var emails = util.extract_pm_recipients(recipient_string);
        var invalid = _.reject(emails, people.is_valid_email_for_compose);
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
    compose.update_stream_button_for_stream();
    message_edit.handle_narrow_deactivated();
    widgetize.set_widgets_for_list();
    typing_events.render_notifications_for_narrow();
    tab_bar.initialize();
    exports.narrow_title = "home";
    notifications.redraw_title();
    notifications.hide_or_show_history_limit_message(home_msg_list);
}

exports.deactivate = function () {
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
        var preserve_pre_narrowing_screen_position =
            current_msg_list.selected_row().length > 0 &&
            current_msg_list.pre_narrow_offset !== undefined;
        var message_id_to_select;
        var select_opts = {
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

function show_search_query() {
    // Don't need to handle "search:" filter because search_query does not contain it.
    var search_query = narrow_state.search_string();
    var query_words = search_query.split(" ");

    var search_string_display = $("#empty_search_stop_words_string");
    var query_contains_stop_words = false;

    // Also removes previous search_string if any
    search_string_display.text(i18n.t("You searched for:"));

    _.each(query_words, function (query_word) {
        search_string_display.append(' ');

        // if query contains stop words, it is enclosed by a <del> tag
        if (_.contains(page_params.stop_words, query_word)) {
            // stop_words do not need sanitization so this is unnecesary but it is fail-safe.
            search_string_display.append($('<del>').text(query_word));
            query_contains_stop_words = true;
        } else {
            // We use .text("...") to sanitize the user-given query_string.
            search_string_display.append($('<span>').text(query_word));
        }
    });

    if (query_contains_stop_words) {
        search_string_display.html(i18n.t(
            "Some common words were excluded from your search.") + "<br/>" + search_string_display.html());
    }
}

function pick_empty_narrow_banner() {
    var default_banner = $('#empty_narrow_message');

    var current_filter = narrow_state.filter();

    if (current_filter === undefined) {
        return default_banner;
    }

    var first_term = current_filter.operators()[0];
    var first_operator = first_term.operator;
    var first_operand = first_term.operand;
    var num_operators = current_filter.operators().length;

    if (num_operators !== 1) {
        // For multi-operator narrows, we just use the default banner
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
        var stream_sub = stream_data.get_sub(narrow_state.stream());
        if (!stream_sub || stream_sub.invite_only) {
            return $("#nonsubbed_private_nonexistent_stream_narrow_message");
        }
        return $("#nonsubbed_stream_narrow_message");
    } else if (first_operator === "search") {
        // You are narrowed to empty search results.
        show_search_query();
        return $("#empty_search_narrow_message");
    } else if (first_operator === "pm-with") {
        if (!people.is_valid_bulk_emails_for_compose(first_operand.split(','))) {
            if (first_operand.indexOf(',') === -1) {
                return $("#non_existing_user");
            }
            return $("#non_existing_users");
        }
        if (first_operand.indexOf(',') === -1) {
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

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = narrow;
}
window.narrow = narrow;
