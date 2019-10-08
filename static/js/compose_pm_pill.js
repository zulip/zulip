var compose_pm_pill = (function () {

var exports = {};

exports.initialize_pill = function () {
    var pill;
    var container = $("#private_message_recipient").parent();

    pill = input_pill.create({
        container: container,
        create_item_from_text: user_pill.create_item_from_email,
        get_text_from_item: user_pill.get_email_from_item,
    });

    return pill;
};

exports.initialize = function () {
    exports.widget = exports.initialize_pill();
};

exports.clear = function () {
    exports.widget.clear();
};

exports.set_from_typeahead = function (person) {
    // We expect person to be an object returned from people.js.
    user_pill.append_person({
        pill_widget: exports.widget,
        person: person,
    });
};

exports.set_from_emails = function (value) {
    // value is something like "alice@example.com,bob@example.com"
    exports.clear();
    exports.widget.appendValue(value);
};

exports.get_user_ids = function () {
    return user_pill.get_user_ids(exports.widget);
};

exports.has_unconverted_data = function () {
    return user_pill.has_unconverted_data(exports.widget);
};

exports.get_user_ids_string = function () {
    var user_ids = exports.get_user_ids();
    var sorted_user_ids = util.sorted_ids(user_ids);
    var user_ids_string = sorted_user_ids.join(',');
    return user_ids_string;
};

exports.get_emails = function () {
    // return something like "alice@example.com,bob@example.com"
    var user_ids = exports.get_user_ids();
    var emails = user_ids.map(function (id) {
        return people.get_person_from_user_id(id).email;
    }).join(",");
    return emails;
};

exports.get_typeahead_items = function () {
    return user_pill.typeahead_source(exports.widget);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = compose_pm_pill;
}
window.compose_pm_pill = compose_pm_pill;
