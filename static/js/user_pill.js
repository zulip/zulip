var user_pill = (function () {

var exports = {};

// This will be used for pills for things like composing PMs
// or adding users to a stream/group.

exports.create_item_from_email = function (email, current_items) {
    // For normal Zulip use, we need to validate the email for our realm.
    var user = people.get_by_email(email);

    if (!user) {
        if (page_params.realm_is_zephyr_mirror_realm) {
            var existing_emails = _.pluck(current_items, 'email');

            if (existing_emails.indexOf(email) >= 0) {
                return;
            }

            // For Zephyr we can't assume any emails are invalid,
            // so we just create a pill where the display value
            // is the email itself.
            return {
                display_value: email,
                email: email,
            };
        }

        // The email is not allowed, so return.
        return;
    }

    var existing_ids = _.pluck(current_items, 'user_id');

    if (existing_ids.indexOf(user.user_id) >= 0) {
        return;
    }

    var avatar_url = people.small_avatar_url_for_person(user);

    // We must supply display_value for the widget to work.  Everything
    // else is for our own use in callbacks.
    var item = {
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
    var person = opts.person;
    var pill_widget = opts.pill_widget;
    var avatar_url = people.small_avatar_url_for_person(person);

    pill_widget.appendValidatedData({
        display_value: person.full_name,
        user_id: person.user_id,
        email: person.email,
        img_src: avatar_url,
    });
    pill_widget.clear_text();
};

exports.get_user_ids = function (pill_widget) {
    var items = pill_widget.items();
    var user_ids = _.pluck(items, 'user_id');
    user_ids = _.filter(user_ids); // be defensive about undefined users

    return user_ids;
};

exports.has_unconverted_data = function (pill_widget) {
    // This returns true if we either have text that hasn't been
    // turned into pills or email-only pills (for Zephyr).
    if (pill_widget.is_pending()) {
        return true;
    }

    var items = pill_widget.items();
    var has_unknown_items = _.any(items, function (item) {
        return item.user_id === undefined;
    });

    return has_unknown_items;
};

exports.typeahead_source = function (pill_widget) {
    var items = people.get_realm_persons();
    var taken_user_ids = exports.get_user_ids(pill_widget);
    items = _.filter(items, function (item) {
        return taken_user_ids.indexOf(item.user_id) === -1;
    });
    return items;
};

exports.append_user = function (user, pills) {
    if (user) {
        exports.append_person({
            pill_widget: pills,
            person: user,
        });
    } else {
        blueslip.warn('Undefined user in function append_user');
    }
};

exports.create_pills = function (pill_container) {
    var pills = input_pill.create({
        container: pill_container,
        create_item_from_text: exports.create_item_from_email,
        get_text_from_item: exports.get_email_from_item,
    });
    return pills;
};

exports.set_up_typeahead_on_pills = function (input, pills, update_func) {
    input.typeahead({
        items: 5,
        fixed: true,
        dropup: true,
        source: function () {
            return exports.typeahead_source(pills);
        },
        highlighter: function (item) {
            return typeahead_helper.render_person(item);
        },
        matcher: function (item) {
            var query = this.query.toLowerCase();
            query = query.replace(/\u00A0/g, String.fromCharCode(32));
            return item.email.toLowerCase().indexOf(query) !== -1
                    || item.full_name.toLowerCase().indexOf(query) !== -1;
        },
        sorter: function (matches) {
            return typeahead_helper.sort_recipientbox_typeahead(
                this.query, matches, "");
        },
        updater: function (user) {
            exports.append_user(user, pills);
            input.focus();
            update_func();
        },
        stopAdvance: true,
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = user_pill;
}
window.user_pill = user_pill;
