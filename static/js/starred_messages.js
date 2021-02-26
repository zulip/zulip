"use strict";

exports.starred_ids = new Set();

exports.initialize = function () {
    exports.starred_ids.clear();

    for (const id of page_params.starred_messages) {
        exports.starred_ids.add(id);
    }

    exports.rerender_ui();
};

exports.add = function (ids) {
    for (const id of ids) {
        exports.starred_ids.add(id);
    }

    exports.rerender_ui();
};

exports.remove = function (ids) {
    for (const id of ids) {
        exports.starred_ids.delete(id);
    }

    exports.rerender_ui();
};

exports.get_count = function () {
    return exports.starred_ids.size;
};

exports.get_starred_msg_ids = function () {
    return Array.from(exports.starred_ids);
};

exports.rerender_ui = function () {
    let count = exports.get_count();

    if (!page_params.starred_message_counts) {
        // This essentially hides the count
        count = 0;
    }

    top_left_corner.update_starred_count(count);
};

window.starred_messages = exports;
