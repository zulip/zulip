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

    // We must supply display_value for the widget to work.  Everything
    // else is for our own use in callbacks.
    var item = {
        display_value: user.full_name,
        user_id: user.user_id,
        email: user.email,
    };

    return item;
};

exports.get_email_from_item = function (item) {
  return item.email;
};

exports.append_person = function (opts) {
    var person = opts.person;
    var pill_widget = opts.pill_widget;

    pill_widget.appendValidatedData({
        display_value: person.full_name,
        user_id: person.user_id,
        email: person.email,
    });
    if (pill_widget.clear_text !== undefined) {
        pill_widget.clear_text();
    }
};

exports.get_user_ids = function (pill_widget) {
    var items = pill_widget.items();
    var user_ids = _.pluck(items, 'user_id');
    user_ids = _.filter(user_ids); // be defensive about undefined users

    return user_ids;
};

exports.typeahead_source = function (pill_widget) {
    var items = people.get_realm_persons();
    var taken_user_ids = exports.get_user_ids(pill_widget);
    items = _.filter(items, function (item) {
        return taken_user_ids.indexOf(item.user_id) === -1;
    });
    return items;
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = user_pill;
}
