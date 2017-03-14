var ui = (function () {

var exports = {};

var actively_scrolling = false;

exports.have_scrolled_away_from_top = true;

exports.actively_scrolling = function () {
    return actively_scrolling;
};

// What, if anything, obscures the home tab?
exports.home_tab_obscured = function () {
    if ($('.modal:visible').length > 0) {
        return 'modal';
    }
    if (! $('#home').hasClass('active')) {
        return 'other_tab';
    }
    return false;
};

exports.change_tab_to = function (tabname) {
    $('#gear-menu a[href="' + tabname + '"]').tab('show');
};

exports.focus_on = function (field_id) {
    // Call after autocompleting on a field, to advance the focus to
    // the next input field.

    // Bootstrap's typeahead does not expose a callback for when an
    // autocomplete selection has been made, so we have to do this
    // manually.
    $("#" + field_id).focus();
};

exports.blur_active_element = function () {
    // this blurs anything that may perhaps be actively focused on.
    document.activeElement.blur();
};

function amount_to_paginate() {
    // Some day we might have separate versions of this function
    // for Page Up vs. Page Down, but for now it's the same
    // strategy in either direction.
    var info = message_viewport.message_viewport_info();
    var page_size = info.visible_height;

    // We don't want to page up a full page, because Zulip users
    // are especially worried about missing messages, so we want
    // a little bit of the old page to stay on the screen.  The
    // value chosen here is roughly 2 or 3 lines of text, but there
    // is nothing sacred about it, and somebody more anal than me
    // might wish to tie this to the size of some particular DOM
    // element.
    var overlap_amount = 55;

    var delta = page_size - overlap_amount;

    // If the user has shrunk their browser a whole lot, pagination
    // is not going to be very pleasant, but we can at least
    // ensure they go in the right direction.
    if (delta < 1) {
        delta = 1;
    }

    return delta;
}

exports.page_up_the_right_amount = function () {
    // This function's job is to scroll up the right amount,
    // after the user hits Page Up.  We do this ourselves
    // because we can't rely on the browser to account for certain
    // page elements, like the compose box, that sit in fixed
    // positions above the message pane.  For other scrolling
    // related adjustements, try to make those happen in the
    // scroll handlers, not here.
    var delta = amount_to_paginate();
    message_viewport.scrollTop(message_viewport.scrollTop() - delta);
};

exports.page_down_the_right_amount = function () {
    // see also: page_up_the_right_amount
    var delta = amount_to_paginate();
    message_viewport.scrollTop(message_viewport.scrollTop() + delta);
};

exports.replace_emoji_with_text = function (element) {
    element.find(".emoji").replaceWith(function () {
        return $(this).attr("alt");
    });
};

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

/* Arguments used in the report_* functions are,
   response- response that we want to display
   status_box- element being used to display the response
   cls- class that we want to add/remove to/from the status_box
   type- used to define more complex logic for special cases (currently being
         used only for subscriptions-status) */

exports.report_message = function (response, status_box, cls, type) {
    if (cls === undefined) {
        cls = 'alert';
    }

    if (type === undefined) {
        type = ' ';
    }

    if (type === 'subscriptions-status') {
        status_box.removeClass(status_classes).addClass(cls).children('#response')
              .text(response).stop(true).fadeTo(0, 1);
    } else {
        status_box.removeClass(status_classes).addClass(cls)
              .text(response).stop(true).fadeTo(0, 1);
    }

    status_box.show();
};

exports.report_error = function (response, xhr, status_box, type) {
    if (xhr && xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        response += ": " + JSON.parse(xhr.responseText).msg;
    }

    ui.report_message(response, status_box, 'alert-error', type);
};

exports.report_success = function (response, status_box, type) {
    ui.report_message(response, status_box, 'alert-success', type);
};

function update_message_in_all_views(message_id, callback) {
    _.each([message_list.all, home_msg_list, message_list.narrowed], function (list) {
        if (list === undefined) {
            return;
        }
        var row = list.get_row(message_id);
        if (row === undefined) {
            // The row may not exist, e.g. if you do an action on a message in
            // a narrowed view
            return;
        }
        callback(row);
    });
}

exports.find_message = function (message_id) {
    // Try to find the message object. It might be in the narrow list
    // (if it was loaded when narrowed), or only in the message_list.all
    // (if received from the server while in a different narrow)
    var message;
    _.each([message_list.all, home_msg_list, message_list.narrowed], function (msg_list) {
        if (msg_list !== undefined && message === undefined) {
            message = msg_list.get(message_id);
        }
    });
    return message;
};

exports.update_starred = function (message_id, starred) {
    // Update the message object pointed to by the various message
    // lists.
    var message = exports.find_message(message_id);

    // If it isn't cached in the browser, no need to do anything
    if (message === undefined) {
        return;
    }

    unread_ui.mark_message_as_read(message);

    message.starred = starred;

    // Avoid a full re-render, but update the star in each message
    // table in which it is visible.
    update_message_in_all_views(message_id, function update_row(row) {
        var elt = row.find(".star");
        if (starred) {
            elt.addClass("icon-vector-star").removeClass("icon-vector-star-empty").removeClass("empty-star");
        } else {
            elt.removeClass("icon-vector-star").addClass("icon-vector-star-empty").addClass("empty-star");
        }
        var title_state = message.starred ? "Unstar" : "Star";
        elt.attr("title", title_state + " this message");
    });
};

var local_messages_to_show = [];
var show_message_timestamps = _.throttle(function () {
    _.each(local_messages_to_show, function (message_id) {
        update_message_in_all_views(message_id, function update_row(row) {
            row.find('.message_time').toggleClass('notvisible', false);
        });
    });
    local_messages_to_show = [];
}, 100);

exports.show_local_message_arrived = function (message_id) {
    local_messages_to_show.push(message_id);
    show_message_timestamps();
};

exports.show_message_failed = function (message_id, failed_msg) {
    // Failed to send message, so display inline retry/cancel
    update_message_in_all_views(message_id, function update_row(row) {
        var failed_div = row.find('.message_failed');
        failed_div.toggleClass('notvisible', false);
        failed_div.find('.failed_text').attr('title', failed_msg);
    });
};

exports.show_failed_message_success = function (message_id) {
    // Previously failed message succeeded
    update_message_in_all_views(message_id, function update_row(row) {
        row.find('.message_failed').toggleClass('notvisible', true);
    });
};

exports.lightbox = function (data) {
    switch (data.type) {
        case "photo":
            exports.lightbox_photo(data.image, data.user);
            break;
        case "youtube":
            exports.youtube_video(data.id);
            break;
        default:
            break;
    }

    $("#overlay").addClass("show");
    popovers.hide_all();
};

$(document).ready(function () {
    var info_overlay_toggle = components.toggle({
        name: "info-overlay-toggle",
        selected: 0,
        values: [
            { label: "Keyboard shortcuts", key: "keyboard-shortcuts" },
            { label: "Message formatting", key: "markdown-help" },
            { label: "Search operators", key: "search-operators" },
        ],
        callback: function (name, key) {
            $(".overlay-modal").hide();
            $("#" + key).show();
        },
    }).get();

    $(".informational-overlays .overlay-tabs")
        .append($(info_overlay_toggle).addClass("large"));
});

exports.show_info_overlay = function (target) {
    var el = {
        overlay: $(".informational-overlays"),
    };

    if (!el.overlay.hasClass("show")) {
        $(el.overlay).addClass("show");
    }

    if (target) {
        components.toggle.lookup("info-overlay-toggle").goto(target);
    }
};

exports.hide_info_overlay = function () {
    $(".informational-overlays").removeClass("show");
};

exports.lightbox_photo = function (image, user) {
    // image should be an Image Object in JavaScript.
    var url = $(image).attr("src");
    var title = $(image).parent().attr("title");

    $("#overlay .player-container").hide();
    $("#overlay .image-actions, .image-description, .download").show();

    var img = new Image();
    img.src = url;
    $("#overlay .image-preview").html("").show()
        .append(img);

    $(".image-description .title").text(title || "N/A");
    $(".image-description .user").text(user);

    $(".image-actions .open, .image-actions .download").attr("href", url);
};

exports.exit_lightbox_photo = function () {
    $("#overlay").removeClass("show");
    $(".player-container iframe").remove();
    document.activeElement.blur();
};

exports.youtube_video = function (id) {
    $("#overlay .image-preview, .image-description, .download").hide();

    var iframe = document.createElement("iframe");
    iframe.width = window.innerWidth;
    iframe.height = window.innerWidth * 0.5625;
    iframe.src = "https://www.youtube.com/embed/" + id;
    iframe.setAttribute("frameborder", 0);
    iframe.setAttribute("allowfullscreen", true);

    $("#overlay .player-container").html("").show().append(iframe);
    $(".image-actions .open").attr("href", "https://youtu.be/" + id);
};
// k3O01EfM5fU

var loading_more_messages_indicator_showing = false;
exports.show_loading_more_messages_indicator = function () {
    if (! loading_more_messages_indicator_showing) {
        loading.make_indicator($('#loading_more_messages_indicator'),
                                    {abs_positioned: true});
        loading_more_messages_indicator_showing = true;
        floating_recipient_bar.hide();
    }
};

exports.hide_loading_more_messages_indicator = function () {
    if (loading_more_messages_indicator_showing) {
        loading.destroy_indicator($("#loading_more_messages_indicator"));
        loading_more_messages_indicator_showing = false;
    }
};

/* EXPERIMENTS */

/* This method allows an advanced user to use the console
 * to switch the application to span full width of the browser.
 */
exports.switchToFullWidth = function () {
    $("#full-width-style").remove();
    $('head').append('<style id="full-width-style" type="text/css">' +
                         '#home .alert-bar, .recipient-bar-content, #compose-container, .app-main, .header-main { max-width: none; }' +
                     '</style>');
    return ("Switched to full width");
};

/* END OF EXPERIMENTS */

$(function () {
    var throttled_mousewheelhandler = $.throttle(50, function (e, delta) {
        // Most of the mouse wheel's work will be handled by the
        // scroll handler, but when we're at the top or bottom of the
        // page, the pointer may still need to move.

        if (delta > 0) {
            if (message_viewport.at_top()) {
                navigate.up();
            }
        } else if (delta < 0) {
            if (message_viewport.at_bottom()) {
                navigate.down();
            }
        }

        message_viewport.last_movement_direction = delta;
    });

    message_viewport.message_pane.mousewheel(function (e, delta) {
        // Ignore mousewheel events if a modal is visible.  It's weird if the
        // user can scroll the main view by wheeling over the grayed-out area.
        // Similarly, ignore events on settings page etc.
        //
        // We don't handle the compose box here, because it *should* work to
        // select the compose box and then wheel over the message stream.
        var obscured = exports.home_tab_obscured();
        if (!obscured) {
            throttled_mousewheelhandler(e, delta);
        } else if (obscured === 'modal') {
            // The modal itself has a handler invoked before this one (see below).
            // preventDefault here so that the tab behind the modal doesn't scroll.
            //
            // This needs to include the events that would be ignored by throttling.
            // That's why this code can't be moved into throttled_mousewheelhandler.
            e.preventDefault();
        }
        // If on another tab, we neither handle the event nor preventDefault, allowing
        // the tab to scroll normally.
    });

    $(window).resize($.throttle(50, resize.handler));

    // Scrolling in modals, input boxes, and other elements that
    // explicitly scroll should not scroll the main view.  Stop
    // propagation in all cases.  Also, ignore the event if the
    // element is already at the top or bottom.  Otherwise we get a
    // new scroll event on the parent (?).
    $('.modal-body, .scrolling_list, input, textarea').mousewheel(function (e, delta) {
        var self = $(this);
        var scroll = self.scrollTop();

        // The -1 fudge factor is important here due to rounding errors.  Better
        // to err on the side of not scrolling.
        var max_scroll = this.scrollHeight - self.innerHeight() - 1;

        e.stopPropagation();
        if (   ((delta > 0) && (scroll <= 0))
            || ((delta < 0) && (scroll >= max_scroll))) {
            e.preventDefault();
        }
    });

    // Override the #compose mousewheel prevention below just for the emoji box
    $('.emoji_popover').mousewheel(function (e) {
        e.stopPropagation();
    });

    // Ignore wheel events in the compose area which weren't already handled above.
    $('#compose').mousewheel(function (e) {
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

    $("#stream").on('blur', function () { compose.decorate_stream_bar(this.value); });

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

    if (!page_params.realm_allow_message_editing) {
        $("#edit-message-hotkey-help").hide();
    }

    if (page_params.realm_presence_disabled) {
        $("#user-list").hide();
        $("#group-pm-list").hide();
    }

    if (feature_flags.full_width) {
        exports.switchToFullWidth();
    }

    // initialize other stuff
    reload.initialize();
    composebox_typeahead.initialize();
    search.initialize();
    tutorial.initialize();
    notifications.initialize();
    gear_menu.initialize();
    hashchange.initialize();
    invite.initialize();
    pointer.initialize();
    unread_ui.initialize();
    activity.initialize();
    emoji.initialize();
});


function scroll_finished() {
    actively_scrolling = false;

    if ($('#home').hasClass('active')) {
        if (!pointer.suppress_scroll_pointer_update) {
            pointer.keep_pointer_in_view();
        } else {
            pointer.suppress_scroll_pointer_update = false;
        }
        floating_recipient_bar.update();
        if (message_viewport.scrollTop() === 0 &&
            ui.have_scrolled_away_from_top) {
            ui.have_scrolled_away_from_top = false;
            message_store.load_more_messages(current_msg_list);
        } else if (!ui.have_scrolled_away_from_top) {
            ui.have_scrolled_away_from_top = true;
        }
        // When the window scrolls, it may cause some messages to
        // enter the screen and become read.  Calling
        // unread_ui.process_visible will update necessary
        // data structures and DOM elements.
        setTimeout(unread_ui.process_visible, 0);
    }
}

var scroll_timer;
function scroll_finish() {
    actively_scrolling = true;
    clearTimeout(scroll_timer);
    scroll_timer = setTimeout(scroll_finished, 100);
}

// Save the compose content cursor position and restore when we
// shift-tab back in (see hotkey.js).
var saved_compose_cursor = 0;

$(function () {
    message_viewport.message_pane.scroll($.throttle(50, function () {
        unread_ui.process_visible();
        scroll_finish();
    }));

    $('#new_message_content').blur(function () {
        saved_compose_cursor = $(this).caret();
    });
});

exports.restore_compose_cursor = function () {
    $('#new_message_content')
        .focus()
        .caret(saved_compose_cursor);
};

$(function () {
    if (window.bridge !== undefined) {
        // Disable "spellchecking" in our desktop app. The "spellchecking"
        // in our Mac app is actually autocorrect, and frustrates our
        // users.
        $("#new_message_content").attr('spellcheck', 'false');
        // Modify the zephyr mirroring error message in our desktop
        // app, since it doesn't work from the desktop version.
        $("#webathena_login_menu").hide();
        $("#normal-zephyr-mirror-error-text").addClass("notdisplayed");
        $("#desktop-zephyr-mirror-error-text").removeClass("notdisplayed");
    }
});

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = ui;
}
