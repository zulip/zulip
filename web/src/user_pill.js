import * as blueslip from "./blueslip";
import * as input_pill from "./input_pill";
import {page_params} from "./page_params";
import * as people from "./people";
import * as user_status from "./user_status";

// This will be used for pills for things like composing
// direct messages or adding users to a stream/group.

export function create_item_from_email(email, current_items) {
    // For normal Zulip use, we need to validate the email for our realm.
    const user = people.get_by_email(email);

    if (!user) {
        if (page_params.realm_is_zephyr_mirror_realm) {
            const existing_emails = current_items.map((item) => item.email);

            if (existing_emails.includes(email)) {
                return undefined;
            }

            // For Zephyr we can't assume any emails are invalid,
            // so we just create a pill where the display value
            // is the email itself.
            return {
                type: "user",
                display_value: email,
                email,
            };
        }

        // The email is not allowed, so return.
        return undefined;
    }

    const existing_ids = current_items.map((item) => item.user_id);

    if (existing_ids.includes(user.user_id)) {
        return undefined;
    }

    const avatar_url = people.small_avatar_url_for_person(user);

    const status_emoji_info = user_status.get_status_emoji(user.user_id);

    // We must supply display_value for the widget to work.  Everything
    // else is for our own use in callbacks.
    const item = {
        type: "user",
        display_value: user.full_name,
        user_id: user.user_id,
        email: user.email,
        img_src: avatar_url,
        deactivated: false,
        status_emoji_info,
    };

    // We pass deactivated true for a deactivated user
    if (!people.is_person_active(user.user_id)) {
        item.deactivated = true;
        item.display_value = user.full_name + " (deactivated)";
    }

    return item;
}

export function get_email_from_item(item) {
    return item.email;
}

export function append_person(opts) {
    const person = opts.person;
    const pill_widget = opts.pill_widget;
    const avatar_url = people.small_avatar_url_for_person(person);
    const status_emoji_info = user_status.get_status_emoji(opts.person.user_id);

    const pill_data = {
        type: "user",
        display_value: person.full_name,
        user_id: person.user_id,
        email: person.email,
        img_src: avatar_url,
        status_emoji_info,
    };

    pill_widget.appendValidatedData(pill_data);
    pill_widget.clear_text();
}

export function get_user_ids(pill_widget) {
    const items = pill_widget.items();
    let user_ids = items.map((item) => item.user_id);
    user_ids = user_ids.filter(Boolean); // be defensive about undefined users

    return user_ids;
}

export function has_unconverted_data(pill_widget) {
    // This returns true if we either have text that hasn't been
    // turned into pills or email-only pills (for Zephyr).
    if (pill_widget.is_pending()) {
        return true;
    }

    const items = pill_widget.items();
    const has_unknown_items = items.some((item) => item.user_id === undefined);

    return has_unknown_items;
}

export function typeahead_source(pill_widget, exclude_bots) {
    const users = exclude_bots ? people.get_realm_active_human_users() : people.get_realm_users();
    return filter_taken_users(users, pill_widget);
}

export function filter_taken_users(items, pill_widget) {
    const taken_user_ids = get_user_ids(pill_widget);
    items = items.filter((item) => !taken_user_ids.includes(item.user_id));
    return items;
}

export function append_user(user, pills) {
    if (user) {
        append_person({
            pill_widget: pills,
            person: user,
        });
    } else {
        blueslip.warn("Undefined user in function append_user");
    }
}

export function create_pills($pill_container, pill_config) {
    const pills = input_pill.create({
        $container: $pill_container,
        pill_config,
        create_item_from_text: create_item_from_email,
        get_text_from_item: get_email_from_item,
    });
    return pills;
}
