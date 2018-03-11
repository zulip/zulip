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
    exports.my_pill = exports.initialize_pill();
};

exports.clear = function () {
    exports.my_pill.clear();
};

exports.set_from_typeahead = function (person) {
    // We expect person to be an object returned from people.js.
    user_pill.append_person({
        pill_widget: exports.my_pill,
        person: person,
    });
};

exports.set_from_emails = function (value) {
    // value is something like "alice@example.com,bob@example.com"
    exports.clear();
    exports.my_pill.appendValue(value);
};

exports.get_user_ids = function () {
    return user_pill.get_user_ids(exports.my_pill);
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
    return user_pill.typeahead_source(exports.my_pill);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = compose_pm_pill;
}
