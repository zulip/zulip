var ui = (function () {

var exports = {};

var actively_scrolling = false;

exports.actively_scrolling = function () {
    return actively_scrolling;
};

// What, if anything, obscures the home tab?

exports.replace_emoji_with_text = function (element) {
    element.find(".emoji").replaceWith(function () {
        if ($(this).is("img")) {
            return $(this).attr("alt");
        }
        return $(this).text();
    });
};

exports.set_up_scrollbar = function (element) {
    element.perfectScrollbar({
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 0.68,
    });
};

exports.update_scrollbar = function (element) {
    element.scrollTop = 0;
    element.perfectScrollbar('update');
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

exports.show_error_for_unsupported_platform = function () {
    // Check if the user is using old desktop app
    if (window.bridge !== undefined) {
        // We don't internationalize this string because it is long,
        // and few users will have both the old desktop app and an
        // internationalized version of Zulip anyway.
        var error = "Hello! You're using the unsupported old Zulip desktop app," +
            " which is no longer developed. We recommend switching to the new, " +
            "modern desktop app, which you can download at " +
            "<a href='https://zulipchat.com/apps'>zulipchat.com/apps</a>.";

        ui_report.generic_embed_error(error);
    }
};

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

exports.update_starred = function (message) {
    var starred = message.starred;

    // Avoid a full re-render, but update the star in each message
    // table in which it is visible.
    update_message_in_all_views(message.id, function update_row(row) {
        var elt = row.find(".star");
        if (starred) {
            elt.addClass("icon-vector-star").removeClass("icon-vector-star-empty").removeClass("empty-star");
        } else {
            elt.removeClass("icon-vector-star").addClass("icon-vector-star-empty").addClass("empty-star");
        }
        var title_state = starred ? i18n.t("Unstar") : i18n.t("Star");
        elt.attr("title", i18n.t("__starred_status__ this message", {starred_status: title_state}));
    });
};

exports.show_message_failed = function (message_id, failed_msg) {
    // Failed to send message, so display inline retry/cancel
    update_message_in_all_views(message_id, function update_row(row) {
        var failed_div = row.find('.message_failed');
        failed_div.toggleClass('notvisible', false);
        failed_div.find('.failed_text').attr('title', failed_msg);
    });
};

exports.remove_message = function (message_id) {
    _.each([message_list.all, home_msg_list, message_list.narrowed], function (list) {
        if (list === undefined) {
            return;
        }
        var row = list.get_row(message_id);
        if (row !== undefined) {
            list.remove_and_rerender([{id: message_id}]);
        }
    });
};

exports.show_failed_message_success = function (message_id) {
    // Previously failed message succeeded
    update_message_in_all_views(message_id, function update_row(row) {
        row.find('.message_failed').toggleClass('notvisible', true);
    });
};

function adjust_mac_shortcuts() {
    var keys_map = [
        ['Backspace', 'Delete'],
        ['Enter', 'Return'],
        ['Home', 'Fn + Left'],
        ['End', 'Fn + Right'],
        ['PgUp', 'Fn + Up'],
        ['PgDn', 'Fn + Down'],
    ];

    $(".hotkeys_table").each(function () {
        var html = $(this).html();
        keys_map.forEach(function (pair) {
            html = html.replace(new RegExp(pair[0]), pair[1]);
        });
        $(this).html(html);
    });
}

function _setup_info_overlay() {
    var info_overlay_toggle = components.toggle({
        name: "info-overlay-toggle",
        selected: 0,
        values: [
            { label: i18n.t("Keyboard shortcuts"), key: "keyboard-shortcuts" },
            { label: i18n.t("Message formatting"), key: "markdown-help" },
            { label: i18n.t("Search operators"), key: "search-operators" },
        ],
        callback: function (name, key) {
            $(".overlay-modal").hide();
            $("#" + key).show();
            $("#" + key).find(".modal-body").focus();
        },
    }).get();

    $(".informational-overlays .overlay-tabs")
        .append($(info_overlay_toggle).addClass("large"));

    if (/Mac/i.test(navigator.userAgent)) {
        adjust_mac_shortcuts();
    }
}

exports.show_info_overlay = function (target) {
    var overlay = $(".informational-overlays");

    if (!overlay.hasClass("show")) {
        overlays.open_overlay({
            name:  'informationalOverlays',
            overlay: overlay,
            on_close: function () {
                hashchange.changehash("");
            },
        });
    }

    if (target) {
        components.toggle.lookup("info-overlay-toggle").goto(target);
    }
};

exports.maybe_show_keyboard_shortcuts = function () {
    if (overlays.is_active()) {
        return;
    }
    if (popovers.any_active()) {
        return;
    }
    ui.show_info_overlay("keyboard-shortcuts");
};

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

function scroll_finished() {
    actively_scrolling = false;

    if ($('#home').hasClass('active')) {
        if (!pointer.suppress_scroll_pointer_update) {
            message_viewport.keep_pointer_in_view();
        } else {
            pointer.suppress_scroll_pointer_update = false;
        }
        floating_recipient_bar.update();
        if (message_viewport.scrollTop() === 0) {
            message_fetch.load_more_messages(current_msg_list);
        }

        // When the window scrolls, it may cause some messages to
        // enter the screen and become read.  Calling
        // unread_ops.process_visible will update necessary
        // data structures and DOM elements.
        setTimeout(unread_ops.process_visible, 0);
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
        unread_ops.process_visible();
        scroll_finish();
    }));

    $('#compose-textarea').blur(function () {
        saved_compose_cursor = $(this).caret();
    });

    // on the end of the modified-message fade in, remove the fade-in-message class.
    var animationEnd = "webkitAnimationEnd oanimationend msAnimationEnd animationend";
    $("body").on(animationEnd, ".fade-in-message", function () {
        $(this).removeClass("fade-in-message");
    });
});

exports.restore_compose_cursor = function () {
    $('#compose-textarea')
        .focus()
        .caret(saved_compose_cursor);
};

exports.show_sidebar_organization_information = function () {
  $("#organization_name").text(page_params.realm_name);
  $("#user_name").text(page_params.full_name);
};

$(function () {
    if (window.bridge !== undefined) {
        // Disable "spellchecking" in our desktop app. The "spellchecking"
        // in our Mac app is actually autocorrect, and frustrates our
        // users.
        $("#compose-textarea").attr('spellcheck', 'false');
        // Modify the zephyr mirroring error message in our desktop
        // app, since it doesn't work from the desktop version.
        $("#webathena_login_menu").hide();
        $("#normal-zephyr-mirror-error-text").addClass("notdisplayed");
        $("#desktop-zephyr-mirror-error-text").removeClass("notdisplayed");
    }
});

exports.initialize = function () {
    i18n.ensure_i18n(_setup_info_overlay);
    exports.show_error_for_unsupported_platform();
    exports.show_sidebar_organization_information();

    if (page_params.night_mode) {
        night_mode.enable();
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = ui;
}
