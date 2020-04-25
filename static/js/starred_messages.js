exports.ids = new Set();

exports.initialize = function () {
    exports.ids.clear();

    for (const id of page_params.starred_messages) {
        exports.ids.add(id);
    }

    exports.rerender_ui();
};

exports.add = function (ids) {
    for (const id of ids) {
        exports.ids.add(id);
    }

    exports.rerender_ui();
};

exports.remove = function (ids) {
    for (const id of ids) {
        exports.ids.delete(id);
    }

    exports.rerender_ui();
};

exports.count = function () {
    return exports.ids.size;
};

exports.get_starred_msg_ids = function () {
    return Array.from(exports.ids);
};

exports.get_topic_starred_msg_ids = function (topic_name, stream_id) {
    return Array.from(exports.ids).filter(function (id) {
        const message = message_store.get(id);
        return message.stream_id === stream_id &&
        message.topic.toLowerCase() === topic_name.toLowerCase();
    });
};

exports.rerender_ui = function () {
    let count = exports.count();

    if (!page_params.starred_message_counts) {
        // This essentially hides the count
        count = 0;
    }

    top_left_corner.update_starred_count(count);
};

window.starred_messages = exports;
