var viewport = (function () {
var exports = {};

var jwindow;
var height;
var width;
var in_stoppable_autoscroll = false;

exports.at_top = function () {
    return (jwindow.scrollTop() <= 0);
};

exports.at_bottom = function () {
    // outerHeight(true): Include margin
    var bottom = jwindow.scrollTop() + jwindow.height();
    var window_size = $(document).height();

    // We only know within a pixel or two if we're
    // exactly at the bottom, due to browser quirkiness,
    // and we err on the side of saying that we are at
    // the bottom.
    return bottom + 2 >= window_size;
};

exports.set_message_position = function (message_top, message_height, viewport_info, ratio) {
    // message_top = offset of the top of a message that you are positioning
    // message_height = height of the message that you are positioning
    // viewport_info = result of calling ui.message_viewport_info
    // ratio = fraction indicating how far down the screen the msg should be

    var how_far_down_in_visible_page = viewport_info.visible_height * ratio;

    // special case: keep large messages fully on the screen
    if (how_far_down_in_visible_page + message_height > viewport_info.visible_height) {
        how_far_down_in_visible_page = viewport_info.visible_height - message_height;

        // Next handle truly gigantic messages.  We just say that the top of the
        // message goes to the top of the viewing area.  Realistically, gigantic
        // messages should either be condensed, socially frowned upon, or scrolled
        // with the mouse.
        if (how_far_down_in_visible_page < 0) {
            how_far_down_in_visible_page = 0;
        }
    }

    var hidden_top =
        viewport_info.visible_top
        - jwindow.scrollTop();

    var message_offset =
        how_far_down_in_visible_page
        + hidden_top;

    var new_scroll_top =
        message_top
        - message_offset;

    suppress_scroll_pointer_update = true; // Gets set to false in the scroll handler.
    jwindow.scrollTop(new_scroll_top);
};

exports.scrollTop = function viewport_scrollTop () {
    return jwindow.scrollTop.apply(jwindow, arguments);
};

exports.height = function viewport_height() {
    if (arguments.length !== 0) {
        height = undefined;
        return jwindow.height.apply(jwindow, arguments);
    }
    if (height === undefined) {
        height = $(window).height();
    }
    return height;
};

exports.width = function viewport_width() {
    if (arguments.length !== 0) {
        width = undefined;
        return jwindow.width.apply(jwindow, arguments);
    }
    if (width === undefined) {
        width = jwindow.width();
    }
    return width;
};


exports.stop_auto_scrolling = function() {
    if (in_stoppable_autoscroll) {
        $("html, body").stop();
    }
};

exports.system_initiated_animate_scroll = function (scroll_amount) {
    suppress_scroll_pointer_update = true; // Gets set to false in the scroll handler.
    var viewport_offset = exports.scrollTop();
    in_stoppable_autoscroll = true;
    $("html, body").animate({
        scrollTop: viewport_offset + scroll_amount,
        always: function () {
            in_stoppable_autoscroll = false;
        }
    });
};

exports.user_initiated_animate_scroll = function (scroll_amount) {
    suppress_scroll_pointer_update = true; // Gets set to false in the scroll handler.
    in_stoppable_autoscroll = false; // defensive

    var viewport_offset = exports.scrollTop();

    // We use $('html, body') because you can't animate window.scrollTop
    // on Chrome (http://bugs.jquery.com/ticket/10419).
    $("html, body").animate({
        scrollTop: viewport_offset + scroll_amount
    });
};

$(function () {
    jwindow = $(window);
    // This handler must be placed before all resize handlers in our application
    jwindow.resize(function () {
        height = undefined;
        width = undefined;
    });
});

return exports;
}());
