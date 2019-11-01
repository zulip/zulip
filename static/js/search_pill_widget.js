exports.initialize = function () {
    if (!page_params.search_pills_enabled) {
        return;
    }
    const container = $('#search_arrows');
    exports.widget = search_pill.create_pills(container);

    exports.widget.onPillRemove(function () {
        const base_query = search_pill.get_search_string_for_current_filter(exports.widget);
        const operators = Filter.parse(base_query);
        narrow.activate(operators, {trigger: 'search'});
    });
};

window.search_pill_widget = exports;
