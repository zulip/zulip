var ui = (function () {

var exports = {};

// We want to remember how far we were scrolled on each 'tab'.
// To do so, we need to save away the old position of the
// scrollbar when we switch to a new tab (and restore it
// when we switch back.)
var scroll_positions = {};
var gravatar_stamp = 1;

exports.focus_on = function (field_id) {
    // Call after autocompleting on a field, to advance the focus to
    // the next input field.

    // Bootstrap's typeahead does not expose a callback for when an
    // autocomplete selection has been made, so we have to do this
    // manually.
    $("#" + field_id).focus();
};

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

var current_email_elem;
function hide_email() {
    if (current_email_elem !== undefined) {
        current_email_elem.addClass('invisible');
        current_email_elem = undefined;
    }
}

function show_email(message_row) {
    hide_email();
    while (!message_row.hasClass('include-sender')) {
        message_row = message_row.prev();
    }
    var elem = message_row.find('.sender_email');
    elem.removeClass('invisible');
    current_email_elem = elem;
}

exports.report_message = function (response, status_box, cls) {
    if (cls === undefined)
        cls = 'alert';

    status_box.removeClass(status_classes).addClass(cls)
              .text(response).stop(true).fadeTo(0, 1);
    status_box.show();
};

exports.report_error = function (response, xhr, status_box) {
    if (xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        response += ": " + $.parseJSON(xhr.responseText).msg;
    }

    ui.report_message(response, status_box, 'alert-error');
};

exports.report_success = function (response, status_box) {
    ui.report_message(response, status_box, 'alert-success');
};

var clicking = false;
var mouse_moved = false;

function mousedown() {
    mouse_moved = false;
    clicking = true;
}

function mousemove() {
    if (clicking) {
        mouse_moved = true;
    }
}

function resizehandler(e) {
    var sidebar = $("#sidebar");
    var sidebar_nav = $(".sidebar-nav");
    var composebox = $("#compose");
    var top_statusbar = $("#top_statusbar");
    if (window.innerWidth <= 767) {
        sidebar.removeClass('nav-stacked');

        var space_taken_up_by_navbar = sidebar_nav.outerHeight(true);

        // .visible-phone only, so doesn't need undoing
        $("#nav_whitespace").height(space_taken_up_by_navbar);

        top_statusbar.css('top', space_taken_up_by_navbar);

        var message_list_width = $("#main_div").outerWidth();
        composebox.width(message_list_width);
        top_statusbar.width(message_list_width);
        sidebar_nav.width(message_list_width);
    } else {
        sidebar.addClass('nav-stacked');
        top_statusbar.css('top', 0);
        top_statusbar.width('');
        composebox.width('');
        sidebar_nav.width('');
    }

    // This function might run onReady (if we're in a narrow window),
    // but before we've loaded in the messages; in that case, don't
    // try to scroll to one.
    if (selected_message_id !== -1) {
        scroll_to_selected();
    }
}

var old_label;
var is_floating_recipient_bar_showing = false;
function replace_floating_recipient_bar(desired_label) {
    var new_label, other_label, header;
    if (desired_label !== old_label) {
        if (desired_label.children(".message_header_stream").length !== 0) {
            new_label = $("#current_label_stream");
            other_label = $("#current_label_huddle");
            header = desired_label.children(".message_header_stream.right_part");
        } else {
            new_label = $("#current_label_huddle");
            other_label = $("#current_label_stream");
            header = desired_label.children(".message_header_huddle.right_part");
        }
        new_label.find("td:last").replaceWith(header.clone());
        other_label.css('display', 'none');
        new_label.css('display', 'table-row');
        new_label.attr("zid", desired_label.attr("zid"));

        old_label = desired_label;
    }
    if (!is_floating_recipient_bar_showing) {
        $(".floating_recipient_bar").css('visibility', 'visible');
        is_floating_recipient_bar_showing = true;
    }
}

function hide_floating_recipient_bar() {
    if (is_floating_recipient_bar_showing) {
        $(".floating_recipient_bar").css('visibility', 'hidden');
        is_floating_recipient_bar_showing = false;
    }
}

function update_floating_recipient_bar() {
    var top_statusbar = $("#top_statusbar");
    var top_statusbar_top = top_statusbar.offset().top;
    var top_statusbar_bottom = top_statusbar_top + top_statusbar.outerHeight();

    // Find the last message where the top of the recipient
    // row is at least partially occluded by our box.
    // Start with the pointer's current location.
    var candidate = selected_message;
    if (candidate === undefined) {
        return;
    }
    while (true) {
        candidate = candidate.prev();
        if (candidate.length === 0) {
            // We're at the top of the page and no labels are above us.
            hide_floating_recipient_bar();
            return;
        }
        if (candidate.is(".focused_table .recipient_row")) {
            if (candidate.offset().top < top_statusbar_bottom) {
                break;
            }
        }
    }
    var current_label = candidate;

    // We now know what the floating stream/subject bar should say.
    // Do we show it?

    // Hide if the bottom of our floating stream/subject label is not
    // lower than the bottom of current_label (since that means we're
    // covering up a label that already exists).
    if (top_statusbar_bottom <=
        (current_label.offset().top + current_label.outerHeight())) {
        hide_floating_recipient_bar();
        return;
    }

    // Hide if our bottom is in our bookend (or one bookend-height
    // above it). This means we're not showing any useful part of the
    // message above us, so why bother showing the label?
    var current_bookend = current_label.nextUntil(".bookend_tr")
                                       .andSelf()
                                       .next(".bookend_tr:first");
    // (The last message currently doesn't have a bookend, which is why this might be 0).
    if (current_bookend.length > 0) {
        if (top_statusbar_bottom >
            (current_bookend.offset().top - current_bookend.outerHeight())) {
            hide_floating_recipient_bar();
            return;
        }
    }

    // If we're narrowed to a huddle or a subject, the floating
    // recipient bar would be identical to the narrowing header, so
    // don't display it.
    if (narrow.narrowing_type() === "huddle" || narrow.narrowing_type() === "subject") {
        hide_floating_recipient_bar();
        return;
    }

    replace_floating_recipient_bar(current_label);
}
function hack_for_floating_recipient_bar() {
    // So, as of this writing, Firefox respects visibility: collapse,
    // but WebKit does not (at least, my Chrome doesn't.)  Instead it
    // renders it basically as visibility: hidden, which leaves a
    // slight gap that our messages peek through as they scroll
    // by. This hack fixes this by programmatically measuring how big
    // the gap is, and then moving our table up to compensate.
    var gap = $("#floating_recipient_layout_row").outerHeight(true);
    var floating_recipient = $(".floating_recipient");
    var offset = floating_recipient.offset();
    offset.top = offset.top - gap;
    floating_recipient.offset(offset);
}

exports.show_api_key_box = function () {
    $("#get_api_key_box").show();
    $("#api_key_button_box").hide();
};

var current_userinfo_popover_elem;
function show_userinfo_popover(element, id) {
    select_message_by_id(id);
    var elt = $(element);
    if (elt.data('popover') === undefined) {
        var content, message = message_dict[id];
        if (elt.hasClass("message_sender") || elt.hasClass("profile_picture")) {
            elt.popover({placement: "bottom",
                         title: templates.userinfo_popover_title(message),
                         content: templates.userinfo_popover_content(message),
                         trigger: "manual"
                        });
        } else if (elt.hasClass("message_time")) {
            if (!narrow.active()) {
                // Only show the time-travel popover when narrowed
                return;
            }
            elt.popover({placement: "bottom",
                         title: templates.userinfo_popover_title(message),
                         content: templates.timeinfo_popover_content(message),
                         trigger: "manual"
                        });
        }
        elt.popover("show");
        current_userinfo_popover_elem = elt;
    }
}

exports.hide_userinfo_popover = function () {
    if (ui.userinfo_currently_popped()) {
        current_userinfo_popover_elem.popover("destroy");
        current_userinfo_popover_elem = undefined;
    }
};

exports.userinfo_currently_popped = function () {
    return current_userinfo_popover_elem !== undefined;
};

exports.safari_composebox_workaround = function () {
    // OK, so the situation here is basically a lot of work so that
    // Tab-Enter is a valid hotkey for sending a message in Safari.
    // By default, Safari uses Tab only to cycle through textboxes,
    // basically. Even if the tabindex is set on it, a button (like
    // our submit button) will not get focus.

    // HOWEVER, if you set the tabindex on a div, Safari/WebKit will
    // respect that, and will focus it.  So we make a div right
    // *after* the send button -- and that's the one that gets focus
    // when you press tab in Safari, in the composebox.  When that div
    // is selected, we instead shift focus to the Send button.

    // This behavior is configurable in Safari, but is not on by
    // default.  (It is on by default in Chrome.)

    // One unfortunate consequence of this behavior is that you can't
    // get anywhere else by pressing Tab when the "Send" button has
    // focus -- you're sent to the div, which immediately bounces you
    // back.  I think this is harmless enough, since you can always
    // close the composebox.
    $('#compose-send-button').focus();
};

function update_gravatars() {
    $.each($(".gravatar-profile"), function(index, profile) {
        $(this).attr('src', $(this).attr('src') + '?stamp=' + gravatar_stamp);
    });
    gravatar_stamp += 1;
}

function poll_for_gravatar_update(start_time, url) {
    var updated = false;

    $.ajax({
        type: "HEAD",
        url: url,
        async: false,
        cache: false,
        success: function (resp, statusText, xhr) {
            if (new Date(xhr.getResponseHeader('Last-Modified')) > start_time) {
                update_gravatars();
                updated = true;
            }
        }
    });

    // Give users 5 minutes to update their picture on gravatar.com,
    // during which we try to auto-update their image on our site. If
    // they take longer than that, we'll update when they press the
    // save button.
    if (!updated && (($.now() - start_time) < 1000 * 60 * 5)) {
        setTimeout(function() {
            poll_for_gravatar_update(start_time, url);
        }, 1500);
    }
}

exports.get_gravatar_stamp = function () {
    return gravatar_stamp;
};

exports.wait_for_gravatar = function () {
    poll_for_gravatar_update($.now(), $(".gravatar-profile").attr("src"));
};

$(function () {
    // NB: This just binds to current elements, and won't bind to elements
    // created after ready() is called.

    // Prepare the click handler for subbing to a new stream to which
    // you have composed a message.
    $('#create-it').click(function () {
        subs.subscribe_for_send(compose.stream_name(), $('#stream-dne'));
    });

    // Prepare the click handler for subbing to an existing stream.
    $('#sub-it').click(function () {
        subs.subscribe_for_send(compose.stream_name(), $('#stream-nosub'));
    });

    var throttled_scrollhandler = $.throttle(50, function(e) {
        if ($('#home').hasClass('active')) {
            keep_pointer_in_view();
            update_floating_recipient_bar();
        }
    });
    $(window).scroll(throttled_scrollhandler);

    var throttled_mousewheelhandler = $.throttle(50, function(e, delta) {
        // Most of the mouse wheel's work will be handled by the
        // scroll handler, but when we're at the top or bottom of the
        // page, the pointer may still need to move.
        move_pointer_at_page_top_and_bottom(delta);
    });
    $(window).mousewheel(throttled_mousewheelhandler);

    var throttled_resizehandler = $.throttle(50, resizehandler);
    $(window).resize(throttled_resizehandler);

    function clear_password_change() {
        // Clear the password boxes so that passwords don't linger in the DOM
        // for an XSS attacker to find.
        $('#old_password, #new_password, #confirm_password').val('');
    }

    $('#sidebar a[data-toggle="pill"]').on('show', function (e) {
        // Save the position of our old tab away, before we switch
        var old_tab = $(e.relatedTarget).attr('href');
        scroll_positions[old_tab] = viewport.scrollTop();
    });
    $('#sidebar a[data-toggle="pill"]').on('shown', function (e) {
        // Right after we show the new tab, restore its old scroll position
        var target_tab = $(e.target).attr('href');
        if (scroll_positions.hasOwnProperty(target_tab)) {
            viewport.scrollTop(scroll_positions[target_tab]);
        } else {
            viewport.scrollTop(0);
        }

        // Hide all our error messages when switching tabs
        $('.alert-error').hide();
        $('.alert-success').hide();
        $('.alert-info').hide();
        $('.alert').hide();

        $("#api_key_value").text("");
        $("#get_api_key_box").hide();
        $("#show_api_key_box").hide();
        $("#api_key_button_box").show();

        clear_password_change();

        // Set the URL bar title to show the sub-page you're currently on.
        var browser_url = target_tab;
        if (browser_url === "#home") {
            browser_url = "#";
        }
        window.history.pushState("object or string", "Title", browser_url);
    });

    $('#sidebar a[href="#subscriptions"]').click(subs.fetch);

    var settings_status = $('#settings-status');
    $("#settings-change-box form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var message = "Updated settings!";
            var result = $.parseJSON(xhr.responseText);

            if (result.full_name !== undefined) {
                $(".my_fullname").text(result.full_name);
            }
            update_gravatars();

            if (result.enable_desktop_notifications !== undefined) {
                desktop_notifications_enabled = result.enable_desktop_notifications;
            }

            settings_status.removeClass(status_classes)
                .addClass('alert-success')
                .text(message).stop(true).fadeTo(0,1);
            // TODO: In theory we should auto-reload or something if
            // you changed the email address or other fields that show
            // up on all screens
        },
        error: function (xhr, error_type, xhn) {
            var response = "Error changing settings";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            settings_status.removeClass(status_classes)
                .addClass('alert-error')
                .text(response).stop(true).fadeTo(0,1);
        },
        complete: function (xhr, statusText) {
            // Whether successful or not, clear the password boxes.
            // TODO: Clear these earlier, while the request is still pending.
            clear_password_change();
        }
    });

    $("#get_api_key_box").hide();
    $("#show_api_key_box").hide();
    $("#get_api_key_box form").ajaxForm({
        dataType: 'json', // This seems to be ignored. We still get back an xhr.
        success: function (resp, statusText, xhr, form) {
            var message = "Updated settings!";
            var result = $.parseJSON(xhr.responseText);
            $("#get_api_key_password").val("");
            $("#api_key_value").text(result.api_key);
            $("#show_api_key_box").show();
            $("#get_api_key_box").hide();
            settings_status.hide();
        },
        error: function (xhr, error_type, xhn) {
            var response = "Error getting API key";
            if (xhr.status.toString().charAt(0) === "4") {
                // Only display the error response for 4XX, where we've crafted
                // a nice response.
                response += ": " + $.parseJSON(xhr.responseText).msg;
            }
            settings_status.removeClass(status_classes)
                .addClass('alert-error')
                .text(response).stop(true).fadeTo(0,1);
            $("#show_api_key_box").hide();
            $("#get_api_key_box").show();
        }
    });

    // A little hackish, because it doesn't seem to totally get us
    // the exact right width for the top_statusbar and compose box,
    // but, close enough for now.
    resizehandler();
    hack_for_floating_recipient_bar();

    typeahead_helper.update_all_recipients(people_list);
    composebox_typeahead.initialize();
    search.initialize();
    notifications.initialize();

    $("body").bind('click', function() {
        ui.hide_userinfo_popover();
    });

    $("#main_div").on("click", ".messagebox", function (e) {
        if ($(e.target).is("a")) {
            // If this click came from a hyperlink, don't trigger the
            // reply action.  The simple way of doing this is simply
            // to call e.stopPropagation() from within the link's
            // click handler.
            //
            // Unfortunately, on Firefox, this breaks Ctrl-click and
            // Shift-click, because those are (apparently) implemented
            // by adding an event listener on link clicks, and
            // stopPropagation prevents them from being called.
            return;
        }
        if (!(clicking && mouse_moved)) {
            // Was a click (not a click-and-drag).
            var row = $(this).closest(".message_row");
            select_message_by_id(row.attr('zid'));
            respond_to_message();
        }
        mouse_moved = false;
        clicking = false;
    });

    $("#main_div").on("mousedown", ".messagebox", mousedown);
    $("#main_div").on("mousemove", ".messagebox", mousemove);
    $("#main_div").on("mouseover", ".messagebox", function (e) {
        var row = $(this).closest(".message_row");
        show_email(row);
    });

    $("#main_div").on("mouseout", ".messagebox", function (e) {
        hide_email();
    });

    $("#main_div").on("mouseover", ".user_info_hover", function (e) {
        var row = $(this).closest(".message_row");
        show_email(row);
        row.find(".sender_name").addClass("sender_hovered");
    });

    $("#main_div").on("mouseout", ".user_info_hover", function (e) {
        var row = $(this).closest(".message_row");
        hide_email();
        row.find(".sender_name").removeClass("sender_hovered");
    });

    $("#main_div").on("click", ".user_info_hover", function (e) {
        var row = $(this).closest(".message_row");
        e.stopPropagation();
        var last_popover_elem = current_userinfo_popover_elem;
        ui.hide_userinfo_popover();
        if (last_popover_elem === undefined
            || last_popover_elem.get()[0] !== this) {
            // Only show the popover if either no popover is
            // currently up or if the user has clicked on a different
            // user_info_hover element than the one that deployed the
            // last popover.  That is, we want it to be the case that
            // a user can dismiss a popover by clicking on the same
            // element that caused the popover
            show_userinfo_popover(this, row.attr('zid'));
        }
    });

    $("#home").on("click", ".narrows_by_recipient", function (e) {
        var row = $(this).closest(".recipient_row");
        narrow.target(row.attr('zid'));
        narrow.by_recipient();
    });

    $("#home").on("click", ".narrows_by_subject", function (e) {
        var row = $(this).closest(".recipient_row");
        narrow.target(row.attr('zid'));
        narrow.by_subject();
    });
});

return exports;
}());
