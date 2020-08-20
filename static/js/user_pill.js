"use strict";

const people = require("./people");

// This will be used for pills for things like composing PMs
// or adding users to a stream/group.

exports.create_item_from_email = function (email, current_items) {
    // For normal Zulip use, we need to validate the email for our realm.
    const user = people.get_by_email(email);

    if (!user) {
        if (page_params.realm_is_zephyr_mirror_realm) {
            const existing_emails = current_items.map((item) => item.email);

            if (existing_emails.includes(email)) {
                return;
            }

            // For Zephyr we can't assume any emails are invalid,
            // so we just create a pill where the display value
            // is the email itself.
            return {
                display_value: email,
                email,
            };
        }

        // The email is not allowed, so return.
        return;
    }

    const existing_ids = current_items.map((item) => item.user_id);

    if (existing_ids.includes(user.user_id)) {
        return;
    }

    const avatar_url = people.small_avatar_url_for_person(user);

    // We must supply display_value for the widget to work.  Everything
    // else is for our own use in callbacks.
    const item = {
        display_value: user.full_name,
        user_id: user.user_id,
        email: user.email,
        img_src: avatar_url,
    };

    return item;
};

exports.get_email_from_item = function (item) {
    return item.email;
};

exports.append_person = function (opts) {
    const person = opts.person;
    const pill_widget = opts.pill_widget;
    const avatar_url = people.small_avatar_url_for_person(person);

    pill_widget.appendValidatedData({
        display_value: person.full_name,
        user_id: person.user_id,
        email: person.email,
        img_src: avatar_url,
    });
    pill_widget.clear_text();
};

exports.get_user_ids = function (pill_widget) {
    const items = pill_widget.items();
    let user_ids = items.map((item) => item.user_id);
    user_ids = user_ids.filter(Boolean); // be defensive about undefined users

    return user_ids;
};

exports.has_unconverted_data = function (pill_widget) {
    // This returns true if we either have text that hasn't been
    // turned into pills or email-only pills (for Zephyr).
    if (pill_widget.is_pending()) {
        return true;
    }

    const items = pill_widget.items();
    const has_unknown_items = items.some((item) => item.user_id === undefined);

    return has_unknown_items;
};

exports.typeahead_source = function (pill_widget) {
    const persons = people.get_realm_users();
    return user_pill.filter_taken_users(persons, pill_widget);
};

exports.filter_taken_users = function (items, pill_widget) {
    const taken_user_ids = exports.get_user_ids(pill_widget);
    items = items.filter((item) => !taken_user_ids.includes(item.user_id));
    return items;
};

exports.append_user = function (user, pills) {
    if (user) {
        exports.append_person({
            pill_widget: pills,
            person: user,
        });
    } else {
        blueslip.warn("Undefined user in function append_user");
    }
};

exports.create_pills = function (pill_container) {
    const pills = input_pill.create({
        container: pill_container,
        create_item_from_text: exports.create_item_from_email,
        get_text_from_item: exports.get_email_from_item,
    });
    return pills;
};

window.user_pill = exports;
