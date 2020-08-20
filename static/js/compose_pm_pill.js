"use strict";

const people = require("./people");
const util = require("./util");

exports.initialize_pill = function () {
    const container = $("#private_message_recipient").parent();

    const pill = input_pill.create({
        container,
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
        person,
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
    const user_ids = exports.get_user_ids();
    const sorted_user_ids = util.sorted_ids(user_ids);
    const user_ids_string = sorted_user_ids.join(",");
    return user_ids_string;
};

exports.get_emails = function () {
    // return something like "alice@example.com,bob@example.com"
    const user_ids = exports.get_user_ids();
    const emails = user_ids.map((id) => people.get_by_user_id(id).email).join(",");
    return emails;
};

exports.filter_taken_users = function (persons) {
    return user_pill.filter_taken_users(persons, exports.widget);
};

window.compose_pm_pill = exports;
