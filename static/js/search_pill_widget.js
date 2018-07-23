var search_pill_widget = (function () {

var exports = {};

exports.initialize = function () {
    if (!page_params.search_pills_enabled) {
        return;
    }
    var container = $('#search_arrows');
    exports.widget = search_pill.create_pills(container);

    exports.widget.onPillRemove(function () {
        var base_query = search_pill.get_search_string_for_current_filter(exports.widget);
        var operators = Filter.parse(base_query);
        narrow.activate(operators, {trigger: 'search'});
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = search_pill_widget;
}

window.search_pill_widget = search_pill_widget;
