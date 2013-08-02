var navigate = (function () {

var exports = {};


function go_to_row(row) {
    current_msg_list.select_id(rows.id(row),
                               {then_scroll: true,
                                from_scroll: true});
}

exports.up = function () {
    last_viewport_movement_direction = -1;
    var next_row = rows.prev_visible(current_msg_list.selected_row());
    if (next_row.length !== 0) {
        go_to_row(next_row);
    }
};

exports.down = function () {
    last_viewport_movement_direction = 1;
    var next_row = rows.next_visible(current_msg_list.selected_row());
    if (next_row.length !== 0) {
        go_to_row(next_row);
    }
};

exports.to_home = function () {
    last_viewport_movement_direction = -1;
    var next_row = rows.first_visible(current_msg_list.selected_row());
    if (next_row.length !== 0) {
        go_to_row(next_row);
    }
};

exports.to_end = function () {
    var next_id = current_msg_list.last().id;
    last_viewport_movement_direction = 1;
    current_msg_list.select_id(next_id, {then_scroll: true,
                                         from_scroll: true});
    mark_current_list_as_read();
};

exports.page_up = function () {
    if (viewport.at_top() && !current_msg_list.empty()) {
        current_msg_list.select_id(current_msg_list.first().id, {then_scroll: false});
    }
    else {
        ui.page_up_the_right_amount();
    }
};

exports.page_down = function () {
    if (viewport.at_bottom() && !current_msg_list.empty()) {
        current_msg_list.select_id(current_msg_list.last().id, {then_scroll: false});
        mark_current_list_as_read();
    }
    else {
        ui.page_down_the_right_amount();
    }
};

return exports;
}());
