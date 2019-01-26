(function () {

// This is where most of our initialization takes place.
// TODO: Organize it a lot better.  In particular, move bigger
//       functions to other modules.

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

var current_message_hover;
function message_unhover() {
    if (current_message_hover === undefined) {
        return;
    }
    current_message_hover.find('span.edit_content').html("");
    current_message_hover.removeClass('message_hovered');
    current_message_hover = undefined;
}

function message_hover(message_row) {
    var message;

    var id = parseInt(message_row.attr("zid"), 10);
    if (current_message_hover && message_row && current_message_hover.attr("zid") === message_row.attr("zid")) {
        return;
    }
    // Don't allow on-hover editing for local-only messages
    if (message_row.hasClass('local')) {
        return;
    }
    message = current_msg_list.get(rows.id(message_row));
    message_unhover();
    message_row.addClass('message_hovered');
    current_message_hover = message_row;

    if (!message_edit.is_topic_editable(message)) {
        // The actions and reactions icon hover logic is handled entirely by CSS
        return;
    }

    // But the message edit hover icon is determined by whether the message is still editable
    if (message_edit.get_editability(message) === message_edit.editability_types.FULL &&
        !message.status_message) {
        message_row.find(".edit_content").html('<i class="fa fa-pencil edit_content_button" aria-hidden="true" title="Edit"></i>');
    } else {
        message_row.find(".edit_content").html('<i class="fa fa-file-text-o edit_content_button" aria-hidden="true" title="View source" data-msgid="' + id + '"></i>');
    }
}

exports.initialize_kitchen_sink_stuff = function () {
    // TODO:
    //      This function is a historical dumping ground
    //      for lots of miscellaneous setup.  Almost all of
    //      the code here can probably be moved to more
    //      specific-purpose modules like message_viewport.js.

    var throttled_mousewheelhandler = _.throttle(function (e, delta) {
        // Most of the mouse wheel's work will be handled by the
        // scroll handler, but when we're at the top or bottom of the
        // page, the pointer may still need to move.

        if (delta < 0) {
            if (message_viewport.at_top()) {
                navigate.up();
            }
        } else if (delta > 0) {
            if (message_viewport.at_bottom()) {
                navigate.down();
            }
        }

        message_viewport.last_movement_direction = delta;
    }, 50);

    message_viewport.message_pane.on('wheel', function (e) {
        var delta = e.originalEvent.deltaY;
        if (!overlays.is_active()) {
            // In the message view, we use a throttled mousewheel handler.
            throttled_mousewheelhandler(e, delta);
        }
        // If in a modal, we neither handle the event nor
        // preventDefault, allowing the modal to scroll normally.
    });

    $(window).resize(_.throttle(resize.handler, 50));

    // Scrolling in overlays. input boxes, and other elements that
    // explicitly scroll should not scroll the main view.  Stop
    // propagation in all cases.  Also, ignore the event if the
    // element is already at the top or bottom.  Otherwise we get a
    // new scroll event on the parent (?).
    $('.modal-body, .scrolling_list, input, textarea').on('wheel', function (e) {
        var self = $(this);
        var scroll = self.scrollTop();
        var delta = e.originalEvent.deltaY;

        // The -1 fudge factor is important here due to rounding errors.  Better
        // to err on the side of not scrolling.
        var max_scroll = this.scrollHeight - self.innerHeight() - 1;

        e.stopPropagation();
        if (delta < 0 && scroll <= 0 ||
            delta > 0 && scroll >= max_scroll) {
            e.preventDefault();
        }
    });

    // Ignore wheel events in the compose area which weren't already handled above.
    $('#compose').on('wheel', function (e) {
        e.stopPropagation();
        e.preventDefault();
    });

    // A little hackish, because it doesn't seem to totally get us the
    // exact right width for the floating_recipient_bar and compose
    // box, but, close enough for now.
    resize.handler();

    if (!page_params.left_side_userlist) {
        $("#navbar-buttons").addClass("right-userlist");
    }

    if (page_params.high_contrast_mode) {
        $("body").addClass("high-contrast");
    }

    if (!page_params.dense_mode) {
        $("body").addClass("less_dense_mode");
    } else {
        $("body").addClass("more_dense_mode");
    }

    $("#main_div").on("mouseover", ".message_row", function () {
        var row = $(this).closest(".message_row");
        message_hover(row);
    });

    $("#main_div").on("mouseleave", ".message_row", function () {
        message_unhover();
    });

    $("#main_div").on("mouseover", ".message_sender", function () {
        var row = $(this).closest(".message_row");
        row.addClass("sender_name_hovered");
    });

    $("#main_div").on("mouseout", ".message_sender", function () {
        var row = $(this).closest(".message_row");
        row.removeClass("sender_name_hovered");
    });

    $("#main_div").on("mouseenter", ".youtube-video a", function () {
        $(this).addClass("fa fa-play");
    });

    $("#main_div").on("mouseleave", ".youtube-video a", function () {
        $(this).removeClass("fa fa-play");
    });

    $("#subscriptions_table").on("mouseover", ".subscription_header", function () {
        $(this).addClass("active");
    });

    $("#subscriptions_table").on("mouseout", ".subscription_header", function () {
        $(this).removeClass("active");
    });

    $("#stream_message_recipient_stream").on('blur', function () {
        compose_actions.decorate_stream_bar(this.value);
    });

    $(window).on('blur', function () {
        $(document.body).addClass('window_blurred');
    });

    $(window).on('focus', function () {
        $(document.body).removeClass('window_blurred');
    });

    $(document).on('message_selected.zulip', function (event) {
        if (current_msg_list !== event.msg_list) {
            return;
        }
        if (event.id === -1) {
            // If the message list is empty, don't do anything
            return;
        }
        var row = event.msg_list.get_row(event.id);
        $('.selected_message').removeClass('selected_message');
        row.addClass('selected_message');

        if (event.then_scroll) {
            if (row.length === 0) {
                var row_from_dom = current_msg_list.get_row(event.id);
                var messages = event.msg_list.all_messages();
                blueslip.debug("message_selected missing selected row", {
                    previously_selected: event.previously_selected,
                    selected_id: event.id,
                    selected_idx: event.msg_list.selected_idx(),
                    selected_idx_exact: messages.indexOf(event.msg_list.get(event.id)),
                    render_start: event.msg_list.view._render_win_start,
                    render_end: event.msg_list.view._render_win_end,
                    selected_id_from_idx: messages[event.msg_list.selected_idx()].id,
                    msg_list_sorted: _.isEqual(
                        _.pluck(messages, 'id'),
                        _.chain(current_msg_list.all_messages()).pluck('id').clone().value().sort()
                    ),
                    found_in_dom: row_from_dom.length,
                });
            }
            if (event.target_scroll_offset !== undefined) {
                current_msg_list.view.set_message_offset(event.target_scroll_offset);
            } else {
                // Scroll to place the message within the current view;
                // but if this is the initial placement of the pointer,
                // just place it in the very center
                message_viewport.recenter_view(row,
                                               {from_scroll: event.from_scroll,
                                                force_center: event.previously_selected === -1});
            }
        }
    });

    $("#main_div").on("mouseenter", ".message_time", function (e) {
        var time_elem = $(e.target);
        var row = time_elem.closest(".message_row");
        var message = current_msg_list.get(rows.id(row));
        timerender.set_full_datetime(message, time_elem);
    });

    $('#streams_header h4').tooltip({placement: 'right',
                                     animation: false});

    $('#streams_header i[data-toggle="tooltip"]').tooltip({placement: 'left',
                                                           animation: false});

    $('#userlist-header #userlist-title').tooltip({placement: 'right',
                                                   animation: false});

    $('#userlist-header #user_filter_icon').tooltip({placement: 'left',
                                                     animation: false});

    $('.message_failed i[data-toggle="tooltip"]').tooltip();

    $('.copy_message[data-toggle="tooltip"]').tooltip();

    $('#keyboard-icon').tooltip();

    $("body").on("mouseover", ".message_edit_content", function () {
        $(this).closest(".message_row").find(".copy_message").show();
    });

    $("body").on("mouseout", ".message_edit_content", function () {
        $(this).closest(".message_row").find(".copy_message").hide();
    });

    $("body").on("mouseenter", ".copy_message", function () {
        $(this).show();
        $(this).tooltip('show');
    });

    $("body").on("mouseleave", ".copy_message", function () {
        $(this).tooltip('hide');
    });

    if (!page_params.realm_allow_message_editing) {
        $("#edit-message-hotkey-help").hide();
    }

    if (page_params.realm_presence_disabled) {
        $("#user-list").hide();
        $("#group-pm-list").hide();
    }
};

exports.initialize_everything = function () {
    // initialize other stuff
    people.initialize();
    scroll_bar.initialize();
    message_viewport.initialize();
    exports.initialize_kitchen_sink_stuff();
    echo.initialize();
    stream_color.initialize();
    stream_edit.initialize();
    stream_data.initialize();
    muting.initialize();
    subs.initialize();
    condense.initialize();
    lightbox.initialize();
    click_handlers.initialize();
    copy_and_paste.initialize();
    overlays.initialize();
    invite.initialize();
    timerender.initialize();
    if (!page_params.search_pills_enabled) {
        tab_bar.initialize();
    }
    server_events.initialize();
    user_status.initialize();
    compose_pm_pill.initialize();
    search_pill_widget.initialize();
    reload.initialize();
    user_groups.initialize();
    unread.initialize();
    bot_data.initialize(); // Must happen after people.initialize()
    message_fetch.initialize();
    message_scroll.initialize();
    emoji.initialize();
    markdown.initialize(); // Must happen after emoji.initialize()
    compose.initialize();
    composebox_typeahead.initialize(); // Must happen after compose.initialize()
    search.initialize();
    tutorial.initialize();
    notifications.initialize();
    gear_menu.initialize();
    settings_panel_menu.initialize();
    settings_sections.initialize();
    settings_toggle.initialize();
    hashchange.initialize();
    pointer.initialize();
    unread_ui.initialize();
    activity.initialize();
    emoji_picker.initialize();
    compose_fade.initialize();
    pm_list.initialize();
    stream_list.initialize();
    topic_list.initialize();
    topic_zoom.initialize();
    drafts.initialize();
    sent_messages.initialize();
    hotspots.initialize();
    ui.initialize();
    night_mode.initialize();
    panels.initialize();
    typing.initialize();
    starred_messages.initialize();
    user_status_ui.initialize();
};

$(function () {
    exports.initialize_everything();
});


}());
