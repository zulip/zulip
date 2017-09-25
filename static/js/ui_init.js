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

    if (!message.sent_by_me) {
        // The actions and reactions icon hover logic is handled entirely by CSS
        return;
    }

    // But the message edit hover icon is determined by whether the message is still editablex
    if ((message_edit.get_editability(message) === message_edit.editability_types.FULL) &&
        !message.status_message) {
        message_row.find(".edit_content").html('<i class="icon-vector-pencil edit_content_button"></i>');
    } else {
        message_row.find(".edit_content").html('<i class="icon-vector-file-text-alt edit_content_button" data-msgid="' + id + '"></i>');
    }
}

$(function () {
    var throttled_mousewheelhandler = $.throttle(50, function (e, delta) {
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
    });

    message_viewport.message_pane.on('wheel', function (e) {
        var delta = e.originalEvent.deltaY;
        if (!overlays.is_active()) {
            // In the message view, we use a throttled mousewheel handler.
            throttled_mousewheelhandler(e, delta);
        }
        // If in a modal, we neither handle the event nor
        // preventDefault, allowing the modal to scroll normally.
    });

    $(window).resize($.throttle(50, resize.handler));

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
        if (   ((delta < 0) && (scroll <= 0))
            || ((delta > 0) && (scroll >= max_scroll))) {
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

    $("#subscriptions_table").on("mouseover", ".subscription_header", function () {
        $(this).addClass("active");
    });

    $("#subscriptions_table").on("mouseout", ".subscription_header", function () {
        $(this).removeClass("active");
    });

    $("#stream").on('blur', function () { compose_actions.decorate_stream_bar(this.value); });

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
                blueslip.debug("message_selected missing selected row", {
                    previously_selected: event.previously_selected,
                    selected_id: event.id,
                    selected_idx: event.msg_list.selected_idx(),
                    selected_idx_exact: event.msg_list._items.indexOf(event.msg_list.get(event.id)),
                    render_start: event.msg_list.view._render_win_start,
                    render_end: event.msg_list.view._render_win_end,
                    selected_id_from_idx: event.msg_list._items[event.msg_list.selected_idx()].id,
                    msg_list_sorted: _.isEqual(
                        _.pluck(event.msg_list._items, 'id'),
                        _.chain(current_msg_list._items).pluck('id').clone().value().sort()
                    ),
                    found_in_dom: row_from_dom.length,
                });
            }
            if (event.target_scroll_offset !== undefined) {
                message_viewport.set_message_offset(event.target_scroll_offset);
            } else {
                // Scroll to place the message within the current view;
                // but if this is the initial placement of the pointer,
                // just place it in the very center
                message_viewport.recenter_view(row, {from_scroll: event.from_scroll,
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

    $('#streams_header h4').tooltip({ placement: 'right',
                                       animation: false });

    $('#streams_header i[data-toggle="tooltip"]').tooltip({ placement: 'left',
                                       animation: false });

    $('.message_failed i[data-toggle="tooltip"]').tooltip();

    $('.copy_message[data-toggle="tooltip"]').tooltip();

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

    if (feature_flags.full_width) {
        ui.switchToFullWidth();
    }

    // initialize other stuff
    reload.initialize();
    server_events.initialize();
    people.initialize();
    unread.initialize();
    bot_data.initialize(); // Must happen after people.initialize()
    message_fetch.initialize();
    emoji.initialize();
    markdown.initialize(); // Must happen after emoji.initialize()
    composebox_typeahead.initialize();
    search.initialize();
    tutorial.initialize();
    notifications.initialize();
    gear_menu.initialize();
    settings_sections.initialize();
    hashchange.initialize();
    pointer.initialize();
    unread_ui.initialize();
    activity.initialize();
    emoji_picker.initialize();
    compose_fade.initialize();
    pm_list.initialize();
    stream_list.initialize();
    drafts.initialize();
    sent_messages.initialize();
    compose.initialize();
    hotspots.initialize();
    ui.initialize();
});


}());
