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
        message_viewport.scrollTop(current_msg_table.outerHeight(true) -
                                   message_viewport.height() * 0.1);
        unread_ui.mark_current_list_as_read();
    }
};

exports.to_home = function () {
    message_viewport.last_movement_direction = -1;
    var next_row = rows.first_visible(current_msg_list.selected_row());
    if (next_row.length !== 0) {
        go_to_row(next_row);
    }
};

exports.to_end = function () {
    var next_id = current_msg_list.last().id;
    message_viewport.last_movement_direction = 1;
    current_msg_list.select_id(next_id, {then_scroll: true,
                                         from_scroll: true});
    unread_ui.mark_current_list_as_read();
};

exports.page_up = function () {
    if (message_viewport.at_top() && !current_msg_list.empty()) {
        current_msg_list.select_id(current_msg_list.first().id, {then_scroll: false});
    } else {
        ui.page_up_the_right_amount();
    }
};

exports.page_down = function () {
    if (message_viewport.at_bottom() && !current_msg_list.empty()) {
        current_msg_list.select_id(current_msg_list.last().id, {then_scroll: false});
        unread_ui.mark_current_list_as_read();
    } else {
        ui.page_down_the_right_amount();
    }
};

exports.cycle_stream = function (direction) {
    var currentStream;
    var nextStream;
    if (narrow.stream() !== undefined) {
        currentStream = stream_list.get_stream_li(narrow.stream());
    }
    switch (direction) {
        case 'forward':
            if (narrow.stream() === undefined) {
                nextStream = $("#stream_filters").children('.narrow-filter').first();
            } else {
                nextStream = currentStream.next('.narrow-filter');
                if (nextStream.length === 0) {
                    nextStream = $("#stream_filters").children('.narrow-filter').first();
                }
            }
            break;
        case 'backward':
            if (narrow.stream() === undefined) {
                nextStream = $("#stream_filters").children('.narrow-filter').last();
            } else {
                nextStream = currentStream.prev('.narrow-filter');
                if (nextStream.length === 0) {
                    nextStream = $("#stream_filters").children('.narrow-filter').last();
                }
            }
            break;
        default:
            blueslip.error("Invalid parameter to cycle_stream", {value: direction});
    }
    narrow.by('stream', nextStream.data('name'));
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
