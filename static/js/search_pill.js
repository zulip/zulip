var search_pill = (function () {
var exports = {};

exports.create_item_from_search_string = function (search_string) {
    var operator = Filter.parse(search_string);
    var description = Filter.describe(operator);
    return {
        display_value: search_string,
        description: description,
    };
};

exports.get_search_string_from_item = function (item) {
    return item.display_value;
};

exports.create_pills = function (pill_container) {
    var pills = input_pill.create({
        container: pill_container,
        create_item_from_text: exports.create_item_from_search_string,
        get_text_from_item: exports.get_search_string_from_item,
    });
    return pills;
};

exports.append_search_string = function (search_string, pill_widget) {
    pill_widget.appendValue(search_string);
    if (pill_widget.clear_text !== undefined) {
        pill_widget.clear_text();
    }
};

exports.get_search_string_for_current_filter = function (pill_widget) {
    var items = pill_widget.items();
    var search_strings = _.pluck(items, 'display_value');
    return search_strings.join(' ');
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = search_pill;
}

window.search_pill = search_pill;
