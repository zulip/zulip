var narrow = (function () {

var exports = {};

var current_filter;
var unnarrow_times;

// A small concession to unit testing follows:
exports._set_current_filter = function (filter) {
    current_filter = filter;
};

exports.active = function () {
    return current_filter !== undefined;
};

exports.filter = function () {
    return current_filter;
};

exports.predicate = function () {
    if (current_filter === undefined) {
        return function () { return true; };
    }
    return current_filter.predicate();
};

exports.operators = function () {
    if (current_filter === undefined) {
        return new Filter(page_params.narrow).operators();
    }
    return current_filter.operators();
};

exports.update_email = function (user_id, new_email) {
    if (current_filter !== undefined) {
        current_filter.update_email(user_id, new_email);
    }
};


/* Operators we should send to the server. */
exports.public_operators = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    return current_filter.public_operators();
};

exports.search_string = function () {
    return Filter.unparse(exports.operators());
};

// Collect operators which appear only once into an object,
// and discard those which appear more than once.
function collect_single(operators) {
    var seen   = new Dict();
    var result = new Dict();
    _.each(operators, function (elem) {
        var key = elem.operator;
        if (seen.has(key)) {
            result.del(key);
        } else {
            result.set(key, elem.operand);
            seen.set(key, true);
        }
    });
    return result;
}

// Modify default compose parameters (stream etc.) based on
// the current narrowed view.
//
// This logic is here and not in the 'compose' module because
// it will get more complicated as we add things to the narrow
// operator language.
exports.set_compose_defaults = function (opts) {
    var single = collect_single(exports.operators());

    // Set the stream, subject, and/or PM recipient if they are
    // uniquely specified in the narrow view.

    if (single.has('stream')) {
        opts.stream = stream_data.get_name(single.get('stream'));
    }

    if (single.has('topic')) {
        opts.subject = single.get('topic');
    }

    if (single.has('pm-with')) {
        opts.private_message_recipient = single.get('pm-with');
    }
};

exports.stream = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    var stream_operands = current_filter.operands("stream");
    if (stream_operands.length === 1) {
        return stream_operands[0];
    }
    return undefined;
};

exports.topic = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    var operands = current_filter.operands("topic");
    if (operands.length === 1) {
        return operands[0];
    }
    return undefined;
};

function report_narrow_time(initial_core_time, initial_free_time, network_time) {
    channel.post({
        url: '/json/report_narrow_time',
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
        url: '/json/report_unnarrow_time',
        data: {initial_core: initial_core_time.toString(),
               initial_free: initial_free_time.toString()},
    });

    unnarrow_times = {};
}

exports.narrow_title = "home";
exports.activate = function (raw_operators, opts) {
    var start_time = new Date();
    var was_narrowed_already = exports.active();
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
    }

    notifications.redraw_title();

    blueslip.debug("Narrowed", {operators: _.map(operators,
                                                 function (e) { return e.operator; }),
                                trigger: opts ? opts.trigger : undefined,
                                previous_id: current_msg_list.selected_id()});

    var had_message_content = compose.has_message_content();

    if (!had_message_content) {
        compose.cancel();
    } else {
        compose_fade.update_message_list();
    }

    opts = _.defaults({}, opts, {
        then_select_id: home_msg_list.selected_id(),
        select_first_unread: false,
        first_unread_from_server: false,
        from_reload: false,
        change_hash: true,
        trigger: 'unknown',
    });
    if (filter.has_operator("near")) {
        opts.then_select_id = parseInt(filter.operands("near")[0], 10);
        opts.select_first_unread = false;
    }
    if (filter.has_operator("id")) {
        opts.then_select_id = parseInt(filter.operands("id")[0], 10);
        opts.select_first_unread = false;
    }

    if (opts.then_select_id === -1 && !opts.first_unread_from_server) {
        // According to old comments, this shouldn't happen anymore
        blueslip.warn("Setting then_select_id to page_params.initial_pointer.");
        opts.then_select_id = page_params.initial_pointer;
        opts.select_first_unread = false;
    }

    var then_select_id = opts.then_select_id;
    var then_select_offset;

    if (!was_narrowed_already) {
        unread.messages_read_in_narrow = false;
    }

    if (!opts.select_first_unread && current_msg_list.get_row(then_select_id).length > 0) {
        then_select_offset = current_msg_list.get_row(then_select_id).offset().top;
    }

    // For legacy reasons, we need to set current_filter before calling
    // muting_enabled.
    current_filter = filter;
    var muting_enabled = exports.muting_enabled();

    // Save how far from the pointer the top of the message list was.
    if (current_msg_list.selected_id() !== -1) {
        if (current_msg_list.selected_row().length === 0) {
            blueslip.debug("narrow.activate missing selected row", {
                selected_id: current_msg_list.selected_id(),
                selected_idx: current_msg_list.selected_idx(),
                selected_idx_exact: current_msg_list._items.indexOf(
                                        current_msg_list.get(current_msg_list.selected_id())),
                render_start: current_msg_list.view._render_win_start,
                render_end: current_msg_list.view._render_win_end,
            });
        }
        current_msg_list.pre_narrow_offset = current_msg_list.selected_row().offset().top;
    }

    if (opts.first_unread_from_server && opts.from_reload) {
        then_select_id = page_params.initial_narrow_pointer;
        then_select_offset = page_params.initial_narrow_offset;
        opts.first_unread_from_server = false;
        opts.select_first_unread = false;
        home_msg_list.pre_narrow_offset = page_params.initial_offset;
    }

    var msg_list = new message_list.MessageList('zfilt', current_filter, {
        collapse_messages: ! current_filter.is_search(),
        muting_enabled: muting_enabled,
    });
    msg_list.start_time = start_time;

    // Show the new set of messages.  It is important to set current_msg_list to
    // the view right as it's being shown, because we rely on current_msg_list
    // being shown for deciding when to condense messages.
    $("body").addClass("narrowed_view");
    $("#zfilt").addClass("focused_table");
    $("#zhome").removeClass("focused_table");

    ui.change_tab_to('#home');
    message_list.narrowed = msg_list;
    current_msg_list = message_list.narrowed;

    function maybe_select_closest() {
        if (! message_list.narrowed.empty()) {
            if (opts.select_first_unread) {
                then_select_id = message_list.narrowed.last().id;
                var first_unread =
                    _.find(message_list.narrowed.all_messages(), unread.message_unread);
                if (first_unread) {
                    then_select_id = first_unread.id;
                }
            }

            var preserve_pre_narrowing_screen_position =
                !opts.select_first_unread &&
                (message_list.narrowed.get(then_select_id) !== undefined) &&
                (then_select_offset !== undefined);

            var then_scroll = !preserve_pre_narrowing_screen_position;

            message_list.narrowed.select_id(then_select_id, {then_scroll: then_scroll,
                                                         use_closest: true,
                                                         force_rerender: true,
                                                        });

            if (preserve_pre_narrowing_screen_position) {
                // Scroll so that the selected message is in the same
                // position in the viewport as it was prior to
                // narrowing
                message_viewport.set_message_offset(then_select_offset);
            }
        }
    }

    // Don't bother populating a message list when it won't contain
    // the message we want anyway or if the filter can't be applied
    // locally.
    if (message_list.all.get(then_select_id) !== undefined && current_filter.can_apply_locally()) {
        message_store.add_messages(message_list.all.all_messages(), message_list.narrowed,
                                   {delay_render: true});
    }

    var defer_selecting_closest = message_list.narrowed.empty();
    message_store.load_old_messages({
        anchor: then_select_id.toFixed(),
        num_before: 50,
        num_after: 50,
        msg_list: message_list.narrowed,
        use_first_unread_anchor: opts.first_unread_from_server,
        cont: function () {
            ui.hide_loading_more_messages_indicator();
            if (defer_selecting_closest) {
                maybe_select_closest();
            }
            msg_list.network_time = new Date();
            maybe_report_narrow_time(msg_list);
        },
        cont_will_add_messages: false,
    });

    if (! defer_selecting_closest) {
        message_store.reset_load_more_status();
        maybe_select_closest();
    } else {
        ui.show_loading_more_messages_indicator();
    }

    // Put the narrow operators in the URL fragment.
    // Disabled when the URL fragment was the source
    // of this narrow.
    if (opts.change_hash) {
        hashchange.save_narrow(operators);
    }

    // Put the narrow operators in the search bar.
    $('#search_query').val(Filter.unparse(operators));
    search.update_button_visibility();

    if (!had_message_content && opts.trigger === 'sidebar' && exports.narrowed_by_reply()) {
        if (exports.narrowed_to_topic()) {
            compose.start('stream');
        } else {
            compose.start('private');
        }
    }

    $(document).trigger($.Event('narrow_activated.zulip', {msg_list: message_list.narrowed,
                                                            filter: current_filter,
                                                            trigger: opts.trigger}));
    msg_list.initial_core_time = new Date();
    setTimeout(function () {
        msg_list.initial_free_time = new Date();
        maybe_report_narrow_time(msg_list);
    }, 0);
};

// Activate narrowing with a single operator.
// This is just for syntactic convenience.
exports.by = function (operator, operand, opts) {
    exports.activate([{operator: operator, operand: operand}], opts);
};

exports.by_subject = function (target_id, opts) {
    // don't use current_msg_list as it won't work for muted messages or for out-of-narrow links
    var original = message_store.get(target_id);
    if (original.type !== 'stream') {
        // Only stream messages have topics, but the
        // user wants us to narrow in some way.
        exports.by_recipient(target_id, opts);
        return;
    }
    unread_ui.mark_message_as_read(original);
    var search_terms = [
        {operator: 'stream', operand: original.stream},
        {operator: 'topic', operand: original.subject},
    ];
    opts = _.defaults({}, opts, {then_select_id: target_id});
    exports.activate(search_terms, opts);
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function (target_id, opts) {
    opts = _.defaults({}, opts, {then_select_id: target_id});
    // don't use current_msg_list as it won't work for muted messages or for out-of-narrow links
    var message = message_store.get(target_id);
    unread_ui.mark_message_as_read(message);
    switch (message.type) {
    case 'private':
        exports.by('pm-with', message.reply_to, opts);
        break;

    case 'stream':
        exports.by('stream', message.stream, opts);
        break;
    }
};

exports.by_time_travel = function (target_id, opts) {
    opts = _.defaults({}, opts, {then_select_id: target_id});
    narrow.activate([{operator: "near", operand: target_id}], opts);
};

exports.by_id = function (target_id, opts) {
    opts = _.defaults({}, opts, {then_select_id: target_id});
    narrow.activate([{operator: "id", operand: target_id}], opts);
};

exports.by_conversation_and_time = function (target_id, opts) {
    var args = [{operator: "near", operand: target_id}];
    var original = message_store.get(target_id);
    opts = _.defaults({}, opts, {then_select_id: target_id});

    if (original.type !== 'stream') {
        args.push({operator: "pm-with", operand: original.reply_to});
    } else {
        args.push({operator: 'stream', operand: original.stream});
        args.push({operator: 'topic', operand: original.subject});
    }
    narrow.activate(args, opts);
};

exports.deactivate = function () {
    if (current_filter === undefined) {
        return;
    }
    unnarrow_times = {start_time: new Date()};
    blueslip.debug("Unnarrowed");

    if (ui.actively_scrolling()) {
        // There is no way to intercept in-flight scroll events, and they will
        // cause you to end up in the wrong place if you are actively scrolling
        // on an unnarrow. Wait a bit and try again once the scrolling is over.
        setTimeout(exports.deactivate, 50);
        return;
    }

    if (!compose.has_message_content()) {
        compose.cancel();
    }

    current_filter = undefined;

    exports.hide_empty_narrow_message();

    $("body").removeClass('narrowed_view');
    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    current_msg_list = home_msg_list;
    condense.condense_and_collapse($("#zhome tr.message_row"));

    $('#search_query').val('');
    message_store.reset_load_more_status();
    hashchange.save_narrow();

    if (current_msg_list.selected_id() !== -1) {
        var preserve_pre_narrowing_screen_position =
            (current_msg_list.selected_row().length > 0) &&
            (current_msg_list.pre_narrow_offset !== undefined);
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
        // from her home view
        if (unread.messages_read_in_narrow) {
            // We read some unread messages in a narrow. Instead of going back to
            // where we were before the narrow, go to our first unread message (or
            // the bottom of the feed, if there are no unread messages).
            var first_unread = _.find(current_msg_list.all_messages(), unread.message_unread);
            if (first_unread) {
                message_id_to_select = first_unread.id;
            } else {
                message_id_to_select = current_msg_list.last().id;
            }
        } else {
            // We narrowed, but only backwards in time (ie no unread were read). Try
            // to go back to exactly where we were before narrowing.
            if (preserve_pre_narrowing_screen_position) {
                // We scroll the user back to exactly the offset from the selected
                // message that he was at the time that he narrowed.
                // TODO: Make this correctly handle the case of resizing while narrowed.
                select_opts.target_scroll_offset = current_msg_list.pre_narrow_offset;
            }
            message_id_to_select = current_msg_list.selected_id();
        }
        current_msg_list.select_id(message_id_to_select, select_opts);
    }

    compose_fade.update_message_list();

    $(document).trigger($.Event('narrow_deactivated.zulip', {msg_list: current_msg_list}));

    exports.narrow_title = "home";
    notifications.redraw_title();

    unnarrow_times.initial_core_time = new Date();
    setTimeout(function () {
        unnarrow_times.initial_free_time = new Date();
        report_unnarrow_time();
    });
};

exports.restore_home_state = function () {
    // If we click on the Home link while already at Home, unnarrow.
    // If we click on the Home link from another nav pane, just go
    // back to the state you were in (possibly still narrowed) before
    // you left the Home pane.
    if (!ui.home_tab_obscured()) {
        exports.deactivate();
    }
    navigate.maybe_scroll_to_selected();
};

function pick_empty_narrow_banner() {
    var default_banner = $('#empty_narrow_message');
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
        }
    } else if ((first_operator === "stream") && !stream_data.is_subscribed(first_operand)) {
        // You are narrowed to a stream to which you aren't subscribed.
        if (!stream_data.get_sub(narrow.stream())) {
            return $("#nonsubbed_private_nonexistent_stream_narrow_message");
        }
        return $("#nonsubbed_stream_narrow_message");
    } else if (first_operator === "search") {
        // You are narrowed to empty search results.
        return $("#empty_search_narrow_message");
    } else if (first_operator === "pm-with") {
        if (first_operand.indexOf(',') === -1) {
            // You have no private messages with this person
            return $("#empty_narrow_private_message");
        }
        return $("#empty_narrow_multi_private_message");
    } else if (first_operator === "sender") {
        if (people.get_by_email(first_operand)) {
            return $("#silent_user");
        }
        return $("#non_existing_user");
    }
    return default_banner;
}

exports.show_empty_narrow_message = function () {
    $(".empty_feed_notice").hide();
    pick_empty_narrow_banner().show();
};

exports.hide_empty_narrow_message = function () {
    $(".empty_feed_notice").hide();
};

exports.pm_with_uri = function (reply_to) {
    return hashchange.operators_to_hash([
        {operator: 'pm-with', operand: reply_to},
    ]);
};

exports.huddle_with_uri = function (user_ids_string) {
    // This method is convenient is convenient for callers
    // that have already converted emails to a comma-delimited
    // list of user_ids.  We should be careful to keep this
    // consistent with hashchange.decode_operand.
    return "#narrow/pm-with/" + user_ids_string + '-group';
};

exports.by_sender_uri = function (reply_to) {
    return hashchange.operators_to_hash([
        {operator: 'sender', operand: reply_to},
    ]);
};

exports.by_stream_uri = function (stream) {
    return "#narrow/stream/" + hashchange.encodeHashComponent(stream);
};

exports.by_stream_subject_uri = function (stream, subject) {
    return "#narrow/stream/" + hashchange.encodeHashComponent(stream) +
           "/subject/" + hashchange.encodeHashComponent(subject);
};

exports.by_message_uri = function (message_id) {
    return "#narrow/id/" + hashchange.encodeHashComponent(message_id);
};

exports.by_near_uri = function (message_id) {
    return "#narrow/near/" + hashchange.encodeHashComponent(message_id);
};

exports.by_conversation_and_time_uri = function (message) {
    if (message.type === "stream") {
        return "#narrow/stream/" + hashchange.encodeHashComponent(message.stream) +
            "/subject/" + hashchange.encodeHashComponent(message.subject) +
            "/near/" + hashchange.encodeHashComponent(message.id);
    }
    return "#narrow/pm-with/" + hashchange.encodeHashComponent(message.reply_to) +
        "/near/" + hashchange.encodeHashComponent(message.id);
};

// Are we narrowed to PMs: all PMs or PMs with particular people.
exports.narrowed_to_pms = function () {
    if (current_filter === undefined) {
        return false;
    }
    return (current_filter.has_operator("pm-with") ||
            current_filter.has_operand("is", "private"));
};

// We auto-reply under certain conditions, namely when you're narrowed
// to a PM (or huddle), and when you're narrowed to some stream/subject pair
exports.narrowed_by_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    var operators = current_filter.operators();
    return ((operators.length === 1 &&
             current_filter.operands("pm-with").length === 1) ||
            (operators.length === 2 &&
             current_filter.operands("stream").length === 1 &&
             current_filter.operands("topic").length === 1));
};

exports.narrowed_to_topic = function () {
    if (current_filter === undefined) {
        return false;
    }
    return (current_filter.has_operator("stream") &&
            current_filter.has_operator("topic"));
};

exports.narrowed_to_search = function () {
    return (current_filter !== undefined) && current_filter.is_search();
};

exports.muting_enabled = function () {
    return (!exports.narrowed_to_topic() && !exports.narrowed_to_search() &&
            !exports.narrowed_to_pms());
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = narrow;
}
