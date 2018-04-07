var ui = (function () {

var exports = {};

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
    var perfectScrollbar = new PerfectScrollbar(element[0], {
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 0.68,
        scrollingThreshold: 50,
        minScrollbarLength: 40,
    });
    element[0].perfectScrollbar = perfectScrollbar;
};

exports.update_scrollbar = function (element) {
    element.scrollTop = 0;
    if (element[0].perfectScrollbar !== undefined) {
        element[0].perfectScrollbar.update();
    }
};

exports.destroy_scrollbar = function (element) {
    element[0].perfectScrollbar.destroy();
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

var shown_deprecation_notices = [];
exports.maybe_show_deprecation_notice = function (key) {
    var message;
    if (key === 'C') {
        message = i18n.t('We\'ve replaced the "C" hotkey with "x" to make this common shortcut easier to trigger.');
    } else {
        blueslip.error("Unexpected deprecation notice for hotkey:", key);
        return;
    }

    // Here we handle the tracking for showing deprecation notices,
    // whether or not local storage is available.
    if (localstorage.supported()) {
        var notices_from_storage = JSON.parse(localStorage.getItem('shown_deprecation_notices'));
        if (notices_from_storage !== null) {
            shown_deprecation_notices = notices_from_storage;
        } else {
            shown_deprecation_notices = [];
        }
    }

    if (shown_deprecation_notices.indexOf(key) === -1) {
        $('#deprecation-notice-modal').modal('show');
        $('#deprecation-notice-message').text(message);
        shown_deprecation_notices.push(key);
        if (localstorage.supported()) {
            localStorage.setItem('shown_deprecation_notices', JSON.stringify(shown_deprecation_notices));
        }
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

// Save the compose content cursor position and restore when we
// shift-tab back in (see hotkey.js).
var saved_compose_cursor = 0;

$(function () {
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
    exports.show_error_for_unsupported_platform();

    if (page_params.night_mode) {
        night_mode.enable();
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = ui;
}
