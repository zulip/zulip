var viewport = (function () {
var exports = {};

var jwindow;
var dimensions = {};
var in_stoppable_autoscroll = false;

exports.at_top = function () {
    return (exports.scrollTop() <= 0);
};

exports.message_viewport_info = function () {
    // Return a structure that tells us details of the viewport
    // accounting for fixed elements like the top navbar.
    //
    // The message_header is NOT considered to be part of the visible
    // message pane, which should make sense for callers, who will
    // generally be concerned about whether actual message content is
    // visible.

    var res = {};

    var element_just_above_us = $("#tab_bar_underpadding");

    res.visible_top =
        element_just_above_us.offset().top
        + element_just_above_us.height()
        + $(".message_header").height();

    var element_just_below_us = $("#compose");

    res.visible_height =
        element_just_below_us.offset().top
        - res.visible_top;

    return res;
};

exports.at_bottom = function () {
    // outerHeight(true): Include margin
    var bottom = exports.scrollTop() + exports.height();
    var window_size = $(document).height();

    // We only know within a pixel or two if we're
    // exactly at the bottom, due to browser quirkiness,
    // and we err on the side of saying that we are at
    // the bottom.
    return bottom + 2 >= window_size;
};

exports.is_below_visible_bottom = function (offset) {
    return offset > exports.scrollTop() + exports.height() - $("#compose").height();
};

exports.set_message_position = function (message_top, message_height, viewport_info, ratio) {
    // message_top = offset of the top of a message that you are positioning
    // message_height = height of the message that you are positioning
    // viewport_info = result of calling viewport.message_viewport_info
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
        - exports.scrollTop();

    var message_offset =
        how_far_down_in_visible_page
        + hidden_top;

    var new_scroll_top =
        message_top
        - message_offset;

    suppress_scroll_pointer_update = true; // Gets set to false in the scroll handler.
    exports.scrollTop(new_scroll_top);
};

exports.message_is_visible = function (vp, message) {
    if (! notifications.window_has_focus()) {
        return false;
    }

    var top = vp.visible_top;
    var height = vp.visible_height;

    var row = rows.get(message.id, current_msg_list.table_name);
    var row_offset = row.offset();
    var row_height = row.height();
    // Very tall messages are visible once we've gotten past them
    return (row_height > height && row_offset.top > top) || within_viewport(row_offset, row_height);
};

exports.scrollTop = function viewport_scrollTop () {
    return jwindow.scrollTop.apply(jwindow, arguments);
};

function make_dimen_wrapper(dimen_name, dimen_func) {
    return function viewport_dimension_wrapper() {
        if (arguments.length !== 0) {
            delete dimensions[dimen_name];
            return dimen_func.apply(jwindow, arguments);
        }
        if (! dimensions.hasOwnProperty(dimen_name)) {
            dimensions[dimen_name] = dimen_func.call(jwindow);
        }
        return dimensions[dimen_name];
    };
}

exports.height = make_dimen_wrapper('height', $(window).height);
exports.width  = make_dimen_wrapper('width',  $(window).width);

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
        dimensions = {};
    });
});

return exports;
}());
