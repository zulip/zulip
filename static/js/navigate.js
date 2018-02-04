var navigate = (function () {

var exports = {};


function go_to_row(row) {
    current_msg_list.select_id(rows.id(row),
                               {then_scroll: true,
                                from_scroll: true});
}

exports.up = function () {
    message_viewport.last_movement_direction = -1;
    var next_row = rows.prev_visible(current_msg_list.selected_row());
    if (next_row.length !== 0) {
        go_to_row(next_row);
    }
};

exports.down = function (with_centering) {
    message_viewport.last_movement_direction = 1;
    var next_row = rows.next_visible(current_msg_list.selected_row());
    if (next_row.length !== 0) {
        go_to_row(next_row);
    }
    if (with_centering && (next_row.length === 0)) {
        // At the last message, scroll to the bottom so we have
        // lots of nice whitespace for new messages coming in.
        //
        // FIXME: this doesn't work for End because rows.last_visible()
        // always returns a message.
        var current_msg_table = rows.get_table(current_msg_list.table_name);
        message_viewport.scrollTop(current_msg_table.safeOuterHeight(true) -
                                   message_viewport.height() * 0.1);
        unread_ops.mark_current_list_as_read();
    }
};

exports.to_home = function () {
    message_viewport.last_movement_direction = -1;
    var first_id = current_msg_list.first().id;
    current_msg_list.select_id(first_id, {then_scroll: true,
                                          from_scroll: true});
};

exports.to_end = function () {
    var next_id = current_msg_list.last().id;
    message_viewport.last_movement_direction = 1;
    current_msg_list.select_id(next_id, {then_scroll: true,
                                         from_scroll: true});
    unread_ops.mark_current_list_as_read();
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

exports.page_up = function () {
    if (message_viewport.at_top() && !current_msg_list.empty()) {
        current_msg_list.select_id(current_msg_list.first().id, {then_scroll: false});
    } else {
        exports.page_up_the_right_amount();
    }
};

exports.page_down = function () {
    if (message_viewport.at_bottom() && !current_msg_list.empty()) {
        current_msg_list.select_id(current_msg_list.last().id, {then_scroll: false});
        unread_ops.mark_current_list_as_read();
    } else {
        exports.page_down_the_right_amount();
    }
};

exports.scroll_to_selected = function () {
    var selected_row = current_msg_list.selected_row();
    if (selected_row && (selected_row.length !== 0)) {
        message_viewport.recenter_view(selected_row);
    }
};


exports.maybe_scroll_to_selected = function () {
    // If we have been previously instructed to re-center to the
    // selected message, then do so
    if (pointer.recenter_pointer_on_display) {
        exports.scroll_to_selected();
        pointer.recenter_pointer_on_display = false;
    }
};




return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = navigate;
}
