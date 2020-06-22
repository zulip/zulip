exports.get_display_value = function (term, search_string) {
    const operator = term[0].operator;
    const operand = term[0].operand;
    let person = '';

    switch (operator) {
    case 'stream':
        return '# ' + operand;
    case 'topic':
        return '> ' + operand;
    case 'search':
        return 'search: ' + operand;
    case 'sender':
    case 'from':
    case 'pm-with':
    case 'group-pm-with':
        person = people.get_by_email(operand).full_name;
        return operator + ": " + person;
    default:
        return search_string;
    }
};

exports.create_item_from_search_string = function (search_string) {
    const operator = Filter.parse(search_string);
    const description = Filter.describe(operator);

    return {
        display_value: exports.get_display_value(operator, search_string),
        stored_value: search_string,
        description: description,
    };
};

exports.get_search_string_from_item = function (item) {
    return item.display_value;
};

exports.create_pills = function (pill_container) {
    const pills = input_pill.create({
        container: pill_container,
        create_item_from_text: exports.create_item_from_search_string,
        get_text_from_item: exports.get_search_string_from_item,
    });
    return pills;
};

exports.append_search_string = function (search_string, pill_widget) {
    const operators = Filter.parse(search_string);
    for (const operator of operators) {
        const input = Filter.unparse([operator]);
        pill_widget.appendValue(input);
    }
    if (pill_widget.clear_text !== undefined) {
        pill_widget.clear_text();
    }
};

exports.get_search_string_for_current_filter = function (pill_widget) {
    const items = pill_widget.items();
    const search_strings = items.map(item => item.stored_value);
    return search_strings.join(' ');
};

window.search_pill = exports;
