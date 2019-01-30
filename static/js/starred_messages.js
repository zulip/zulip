var starred_messages = (function () {

var exports = {};

exports.ids = new Dict();

exports.initialize = function () {
    exports.ids = new Dict();
    _.each(page_params.starred_messages, function (id) {
        exports.ids.set(id, true);
    });
    exports.rerender_ui();
};

exports.add = function (ids) {
    _.each(ids, function (id) {
        exports.ids.set(id, true);
    });
    exports.rerender_ui();
};

exports.remove = function (ids) {
    _.each(ids, function (id) {
        if (exports.ids.has(id)) {
            exports.ids.del(id);
        }
    });
    exports.rerender_ui();
};

exports.count = function () {
    return exports.ids.num_items();
};

exports.rerender_ui = function () {
    var count = exports.count();

    if (!page_params.starred_message_counts) {
        // This essentially hides the count
        count = 0;
    }

    top_left_corner.update_starred_count(count);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = starred_messages;
}

window.starred_messages = starred_messages;
