let actively_scrolling = false;

let loading_older_messages_indicator_showing = false;
let loading_newer_messages_indicator_showing = false;
exports.show_loading_older = function () {
    if (!loading_older_messages_indicator_showing) {
        loading.make_indicator($('#loading_older_messages_indicator'),
                               {abs_positioned: true});
        loading_older_messages_indicator_showing = true;
        floating_recipient_bar.hide();
    }
};

exports.hide_loading_older = function () {
    if (loading_older_messages_indicator_showing) {
        loading.destroy_indicator($("#loading_older_messages_indicator"));
        loading_older_messages_indicator_showing = false;
    }
};

exports.show_loading_newer = function () {
    if (!loading_newer_messages_indicator_showing) {
        $(".bottom-messages-logo").show();
        loading.make_indicator($('#loading_newer_messages_indicator'),
                               {abs_positioned: true});
        loading_newer_messages_indicator_showing = true;
        floating_recipient_bar.hide();
    }
};

exports.hide_loading_newer = function () {
    if (loading_newer_messages_indicator_showing) {
        $(".bottom-messages-logo").hide();
        loading.destroy_indicator($("#loading_newer_messages_indicator"));
        loading_newer_messages_indicator_showing = false;
    }
};

exports.hide_indicators = function () {
    exports.hide_loading_older();
    exports.hide_loading_newer();
};

exports.actively_scrolling = function () {
    return actively_scrolling;
};

exports.scroll_finished = function () {
    actively_scrolling = false;

    if (!$('#home').hasClass('active')) {
        return;
    }

    if (!pointer.suppress_scroll_pointer_update) {
        message_viewport.keep_pointer_in_view();
    } else {
        pointer.set_suppress_scroll_pointer_update(false);
    }

    floating_recipient_bar.update();

    if (message_viewport.at_top()) {
        message_fetch.maybe_load_older_messages({
            msg_list: current_msg_list,
            show_loading: exports.show_loading_older,
            hide_loading: exports.hide_loading_older,
        });
    }

    if (message_viewport.at_bottom()) {
        message_fetch.maybe_load_newer_messages({
            msg_list: current_msg_list,
            show_loading: exports.show_loading_newer,
            hide_loading: exports.hide_loading_newer,
        });
    }

    // When the window scrolls, it may cause some messages to
    // enter the screen and become read.  Calling
    // unread_ops.process_visible will update necessary
    // data structures and DOM elements.
    setTimeout(unread_ops.process_visible, 0);
};

let scroll_timer;
function scroll_finish() {
    actively_scrolling = true;
    clearTimeout(scroll_timer);
    scroll_timer = setTimeout(exports.scroll_finished, 100);
}

exports.initialize = function () {
    message_viewport.message_pane.scroll(_.throttle(function () {
        unread_ops.process_visible();
        scroll_finish();
    }, 50));
};


window.message_scroll = exports;
