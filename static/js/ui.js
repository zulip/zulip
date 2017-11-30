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

exports.update_starred = function (message_id, starred) {
    // Update the message object pointed to by the various message
    // lists.
    var message = exports.find_message(message_id);

    // If it isn't cached in the browser, no need to do anything
    if (message === undefined) {
        return;
    }

    unread_ops.mark_message_as_read(message);

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

var create_stylesheet = function () {
    var stylesheet = document.createElement('style');
    stylesheet.type = "text/css";
    stylesheet.classList.add("night-mode-stylesheet");
    // disable the stylesheet by default in case the user isn't running night mode.
    stylesheet.disabled = true;

    return stylesheet;
};

// this transforms an object into CSS. The top level keys of the object are
// the CSS selectors and the second level keys are attributes which should have
// valid CSS values.
//
// EXAMPLE:
//
// {
//     h1: {                       // h1 {
//         color: "red",           //     color: red;
//     },                          // }
//     p: {                        // p {
//         "font-size": "1em",     //     font-size: 1em;
//         "line-spacing": 1.2,    //     line-spacing: 1.2;
//     },                          // }
// }
//
// All CSS selectors are supported, everything from `h1` to
// complex selectors like `.night:not(.test)::after`.
var object_to_css = function (object) {
    var css = "";

    // for each CSS selector.
    for (var selector in object) {
        // ensure the object properties are its own and not ones injected into
        // the Object.prototype.
        if (object.hasOwnProperty(selector)) {
            // create the `h1 {` line...
            css += selector + " {";
            // and for each of the properties of the selector...
            for (var attr in object[selector]) {
                if (object[selector].hasOwnProperty(attr)) {
                    // add the attribute and its value like `attr: value;`.
                    css += "\n\t" + attr + ": " + object[selector][attr] + ";";
                }
            }
            css += "\n}\n";
        }
    }

    // trim the excess newline.
    return css.trim();
};

exports.night_mode = (function () {
    // the object to be converted to CSS.
    // this should ONLY be used if there is no obvious way to perform this action
    // by prefixing the selector with `body.night-mode`.
    var css_skeleton = {
        "a:hover": {
            color: "#65c0ed",
        },
    };

    // create a stylesheet that can be appended to the <head>.
    var stylesheet = create_stylesheet();
    // convert to CSS.
    var css = object_to_css(css_skeleton);

    if (stylesheet.styleSheet) {
        stylesheet.styleSheet.cssText = css;
    } else {
        stylesheet.appendChild(document.createTextNode(css));
    }

    // append the stylesheet.
    (document.head || document.getElementsByTagName('head')[0]).appendChild(stylesheet);

    return {
        enable: function () {
            // we can also query for this in the DOM with the
            // `.night-mode-stylesheet` class.
            stylesheet.disabled = false;
            $("body").addClass("dark-mode");
        },
        disable: function () {
            stylesheet.disabled = true;
            $("body").removeClass("dark-mode");
        },
    };
}());

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
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = ui;
}
