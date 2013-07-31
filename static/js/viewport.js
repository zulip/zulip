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

// This differs from at_bottom in that it only requires the bottom message to
// be visible, but you may be able to scroll down further.
exports.bottom_message_visible = function () {
    var last_row = rows.last_visible();
    if (last_row.length) {
        var message_bottom = last_row[0].getBoundingClientRect().bottom;
        var bottom_of_feed = $("#compose")[0].getBoundingClientRect().top;
        return bottom_of_feed > message_bottom;
    } else {
        return false;
    }
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

function in_viewport_or_tall(el, top_of_feed, bottom_of_feed) {
    var rect = el.getBoundingClientRect();
    return ((rect.top > top_of_feed) && // Message top is in view and
            ((rect.bottom < bottom_of_feed) || // message is fully in view or
             ((rect.height > bottom_of_feed - top_of_feed) &&
              (rect.top < bottom_of_feed)))); // message is tall.
}

function add_to_visible_messages(candidates, visible_messages,
                                 top_of_feed, bottom_of_feed) {
    _.each(candidates, function (row) {
        var row_rect = row.getBoundingClientRect();
        // Mark very tall messages as read once we've gotten past them
        if (in_viewport_or_tall(row, top_of_feed, bottom_of_feed)) {
            visible_messages.push(current_msg_list.get(rows.id($(row))));
        } else {
            return false;
        }
    });
}

exports.visible_messages = function () {
    // Note that when using getBoundingClientRect() we are getting offsets
    // relative to the visible window, but when using jQuery's offset() we are
    // getting offsets relative to the full scrollable window. You can't try to
    // compare heights from these two methods.

    var selected = current_msg_list.selected_message();
    var top_of_feed = $("#tab_bar_underpadding")[0].getBoundingClientRect().bottom;
    var bottom_of_feed = $("#compose")[0].getBoundingClientRect().top;
    var height = bottom_of_feed - top_of_feed;

    // Being simplistic about this, the smallest message is 25 px high.
    var selected_row = rows.get(current_msg_list.selected_id(), current_msg_list.table_name);
    var num_neighbors = Math.floor(height / 25);

    // We do this explicitly without merges and without recalculating
    // the feed bounds to keep this computation as cheap as possible.
    var visible_messages = [];
    var messages_above_pointer = selected_row.prevAll("tr.message_row[zid]:lt(" + num_neighbors + ")");
    var messages_below_pointer = selected_row.nextAll("tr.message_row[zid]:lt(" + num_neighbors + ")");
    add_to_visible_messages(selected_row, visible_messages,
                            top_of_feed, bottom_of_feed);
    add_to_visible_messages(messages_above_pointer, visible_messages,
                            top_of_feed, bottom_of_feed);
    add_to_visible_messages(messages_below_pointer, visible_messages,
                            top_of_feed, bottom_of_feed);

    return visible_messages;
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

exports.stop_auto_scrolling = function () {
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
