var narrow = (function () {

var exports = {};

var current_filter;

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
        return [];
    }
    return current_filter.operators();
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
        var key = elem[0];
        if (seen.has(key)) {
            result.del(key);
        } else {
            result.set(key, elem[1]);
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

exports.activate = function (operators, opts) {
    // most users aren't going to send a bunch of a out-of-narrow messages
    // and expect to visit a list of narrows, so let's get these out of the way.
    notifications.clear_compose_notifications();

    if (operators.length === 0) {
        return exports.deactivate();
    }
    var filter = new Filter(operators);
    blueslip.debug("Narrowed", {operators: _.map(filter.operators(),
                                                 function (e) { return e[0]; }),
                                trigger: opts ? opts.trigger : undefined,
                                previous_id: current_msg_list.selected_id(),
                                previous_is_summarized: current_msg_list.is_summarized_message(
                                    current_msg_list.get(current_msg_list.selected_id()))});

    var had_message_content = compose.has_message_content();

    if (!had_message_content) {
        compose.cancel();
    }
    else {
        compose_fade.update_message_list();
    }

    opts = _.defaults({}, opts, {
        then_select_id: home_msg_list.selected_id(),
        select_first_unread: false,
        change_hash: true,
        trigger: 'unknown'
    });
    if (filter.has_operator("near")) {
        opts.then_select_id = filter.operands("near")[0];
        opts.select_first_unread = false;
    }
    if (filter.has_operator("id")) {
        opts.then_select_id = filter.operands("id")[0];
        opts.select_first_unread = false;
    }

    if (opts.then_select_id === -1) {
        // If we're loading the page via a narrowed URL, we may not
        // have setup the home view yet.  In that case, use the
        // initial pointer.  We can remove this code if we later move
        // to a model where home_msg_list.selected_id() is always
        // initialized early.
        opts.then_select_id = page_params.initial_pointer;
        opts.select_first_unread = false;
    }

    var was_narrowed_already = exports.active();
    var then_select_id = opts.then_select_id;
    var then_select_offset;
    if (!opts.select_first_unread && current_msg_list.get_row(then_select_id).length > 0) {
        then_select_offset = current_msg_list.get_row(then_select_id).offset().top -
            viewport.scrollTop();
    }

    if (!was_narrowed_already) {
        message_tour.start_tour(current_msg_list.selected_id());
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
                selected_idx_exact: current_msg_list._items.indexOf(current_msg_list.get(current_msg_list.selected_id())),
                render_start: current_msg_list.view._render_win_start,
                render_end: current_msg_list.view._render_win_end
            });
        }
        current_msg_list.pre_narrow_offset = current_msg_list.selected_row().offset().top - viewport.scrollTop();
    }

    narrowed_msg_list = new MessageList('zfilt', current_filter, {
        collapse_messages: ! current_filter.is_search(),
        muting_enabled: muting_enabled,
        summarize_read: this.summary_enabled()
    });


    current_msg_list = narrowed_msg_list;

    function maybe_select_closest() {
        if (! narrowed_msg_list.empty()) {
            if (opts.select_first_unread) {
                then_select_id = narrowed_msg_list.last().id;
                var first_unread = _.find(narrowed_msg_list.all(),
                                          unread.message_unread);
                if (first_unread) {
                    then_select_id = first_unread.id;
                }
            }

            var preserve_pre_narrowing_screen_position =
                !opts.select_first_unread &&
                (narrowed_msg_list.get(then_select_id) !== undefined) &&
                (then_select_offset !== undefined);

            var then_scroll = !preserve_pre_narrowing_screen_position;

            narrowed_msg_list.select_id(then_select_id, {then_scroll: then_scroll,
                                                         use_closest: true
                                                        });

            if (preserve_pre_narrowing_screen_position) {
                // Scroll so that the selected message is in the same
                // position in the viewport as it was prior to
                // narrowing
                viewport.scrollTop(narrowed_msg_list.get_row(then_select_id).offset().top
                                   - then_select_offset);
            }
        }
    }

    // Don't bother populating a message list when it won't contain
    // the message we want anyway or if the filter can't be applied
    // locally.
    if (all_msg_list.get(then_select_id) !== undefined && current_filter.can_apply_locally()) {
        add_messages(all_msg_list.all(), narrowed_msg_list);
    }

    var defer_selecting_closest = narrowed_msg_list.empty();
    load_old_messages({
        anchor: then_select_id,
        num_before: 50,
        num_after: 50,
        msg_list: narrowed_msg_list,
        cont: function (messages) {
            if (defer_selecting_closest) {
                maybe_select_closest();
            }
        },
        cont_will_add_messages: false
    });

    // Show the new set of messages.
    $("body").addClass("narrowed_view");
    $("#zfilt").addClass("focused_table");
    $("#zhome").removeClass("focused_table");

    // Deal with message condensing/uncondensing.
    // In principle, this code causes us to scroll around because divs
    // above us could change size -- which is problematic, because it
    // could cause us to lose our position. But doing this here, right
    // after showing the table, seems to cause us to win the race.
    _.each($("tr.message_row"), ui.process_condensing);

    reset_load_more_status();
    if (! defer_selecting_closest) {
        maybe_select_closest();
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
        }
        else {
            compose.start('private');
        }
    }

    $(document).trigger($.Event('narrow_activated.zulip', {msg_list: narrowed_msg_list,
                                                            filter: current_filter,
                                                            trigger: opts.trigger}));
};

// Activate narrowing with a single operator.
// This is just for syntactic convenience.
exports.by = function (operator, operand, opts) {
    exports.activate([[operator, operand]], opts);
};

exports.by_subject = function (target_id, opts) {
    // don't use current_msg_list as it won't work for muted messages or for out-of-narrow links
    var original = msg_metadata_cache[target_id];
    if (original.type !== 'stream') {
        // Only stream messages have subjects, but the
        // user wants us to narrow in some way.
        exports.by_recipient(target_id, opts);
        return;
    }
    mark_message_as_read(original);
    opts = _.defaults({}, opts, {then_select_id: target_id});
    exports.activate([
            ['stream',  original.stream],
            ['topic', original.subject]
        ], opts);
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function (target_id, opts) {
    opts = _.defaults({}, opts, {then_select_id: target_id});
    // don't use current_msg_list as it won't work for muted messages or for out-of-narrow links
    var message = msg_metadata_cache[target_id];
    mark_message_as_read(message);
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
    narrow.activate([["near", target_id]], opts);
};

exports.by_id = function (target_id, opts) {
    opts = _.defaults({}, opts, {then_select_id: target_id});
    narrow.activate([["id", target_id]], opts);
};

exports.by_conversation_and_time = function (target_id, opts) {
    var args = [["near", target_id]];
    var original = msg_metadata_cache[target_id];
    opts = _.defaults({}, opts, {then_select_id: target_id});

    if (original.type !== 'stream') {
        args.push(["pm-with", original.reply_to]);
    } else {
        args.push(['stream',  original.stream]);
        args.push(['topic',  original.subject]);
    }
    narrow.activate(args, opts);
};

exports.deactivate = function () {
    if (current_filter === undefined) {
        return;
    }
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

    $('#search_query').val('');
    reset_load_more_status();

    var visited_messages = message_tour.get_tour();
    home_msg_list.advance_past_messages(visited_messages);
    message_tour.finish_tour();

    current_msg_list = home_msg_list;
    if (current_msg_list.selected_id() !== -1) {
        var preserve_pre_narrowing_screen_position =
            (current_msg_list.selected_row().length > 0) &&
            (current_msg_list.pre_narrow_offset !== undefined);

        if (feature_flags.summarize_read_while_narrowed) {
            // TODO: avoid a full re-render
            // Necessary to replace messages read in the narrow with summary blocks
            current_msg_list.start_summary_exemption();
            current_msg_list.rerender();
        }

        // We fall back to the closest selected id, if the user has removed a stream from the home
        // view since leaving it the old selected id might no longer be there
        current_msg_list.select_id(current_msg_list.selected_id(), {
            then_scroll: !preserve_pre_narrowing_screen_position,
            use_closest: true
        });

        if (preserve_pre_narrowing_screen_position) {
            // We scroll the user back to exactly the offset from the selected
            // message that he was at the time that he narrowed.
            // TODO: Make this correctly handle the case of resizing while narrowed.
            viewport.scrollTop(current_msg_list.selected_row().offset().top - current_msg_list.pre_narrow_offset);
        }
    }

    hashchange.save_narrow();
    compose_fade.update_message_list();

    $(document).trigger($.Event('narrow_deactivated.zulip', {msg_list: current_msg_list}));
};

exports.restore_home_state = function () {
    // If we click on the Home link while already at Home, unnarrow.
    // If we click on the Home link from another nav pane, just go
    // back to the state you were in (possibly still narrowed) before
    // you left the Home pane.
    if (!ui.home_tab_obscured()) {
        exports.deactivate();
    }
    maybe_scroll_to_selected();
};

function pick_empty_narrow_banner() {
    var default_banner = $('#empty_narrow_message');
    if (current_filter === undefined) {
        return default_banner;
    }

    var first_operator = current_filter.operators()[0][0];
    var first_operand = current_filter.operators()[0][1];

    if (first_operator === "is") {
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
        return $("#nonsubbed_stream_narrow_message");
    } else if (first_operator === "search") {
        // You are narrowed to empty search results.
        return $("#empty_search_narrow_message");
    } else if (first_operator === "pm-with") {
        if (first_operand.indexOf(',') === -1) {
            // You have no private messages with this person
            return $("#empty_narrow_private_message");
        } else {
            return $("#empty_narrow_multi_private_message");
        }
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
    return "#narrow/pm-with/" + hashchange.encodeHashComponent(reply_to);
};

exports.by_sender_uri = function (reply_to) {
    return "#narrow/sender/" + hashchange.encodeHashComponent(reply_to);
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
    } else {
        return "#narrow/pm-with/" + hashchange.encodeHashComponent(message.reply_to) +
            "/near/" + hashchange.encodeHashComponent(message.id);
    }
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
    return (!exports.narrowed_to_topic() && !exports.narrowed_to_search() && !exports.narrowed_to_pms());
};

exports.summary_enabled = function () {
    if (!feature_flags.summarize_read_while_narrowed) {
        return false;
    }

    if (current_filter === undefined){
        return 'home'; // Home view, but this shouldn't run anyway
    }

    var operators = current_filter.operators();

    if (operators.length === 1 && (
        current_filter.has_operand("in", "home") ||
        current_filter.has_operand("in", "all"))) {
        return 'home';
    }

    if (operators.length === 1 && (
        current_filter.operands("stream").length === 1 ||
        current_filter.has_operand("is", "private"))) {
        return 'stream';
    }
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = narrow;
}
