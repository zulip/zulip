import * as blueslip from "./blueslip";
import type {InputPillConfig, InputPillContainer, InputPillItem} from "./input_pill";
import * as input_pill from "./input_pill";
import type {User} from "./people";
import * as people from "./people";
import {realm} from "./state_data";
import type {CombinedPillContainer} from "./typeahead_helper";
import * as user_status from "./user_status";

// This will be used for pills for things like composing
// direct messages or adding users to a stream/group.

export type UserPill = {
    type: "user";
    user_id?: number;
    email: string;
};

export type UserPillWidget = InputPillContainer<UserPill>;

export type UserPillData = User & {type: "user"};

export function create_item_from_email(
    email: string,
    current_items: InputPillItem<UserPill>[],
    pill_config?: InputPillConfig | undefined,
): InputPillItem<UserPill> | undefined {
    // For normal Zulip use, we need to validate the email for our realm.
    const user = people.get_by_email(email);

    if (!user) {
        if (realm.realm_is_zephyr_mirror_realm) {
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

    if (pill_config?.exclude_inaccessible_users && user.is_inaccessible_user) {
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
    const item: InputPillItem<UserPill> = {
        type: "user",
        display_value: user.full_name,
        user_id: user.user_id,
        email: user.email,
        img_src: avatar_url,
        deactivated: false,
        status_emoji_info,
        should_add_guest_user_indicator: people.should_add_guest_user_indicator(user.user_id),
    };

    // We pass deactivated true for a deactivated user
    //
    // We consider inaccessible users as active to avoid
    // falsely showing the user as deactivated as we do
    // not have any information about whether they are
    // active or not.
    if (!people.is_person_active(user.user_id) && !user.is_inaccessible_user) {
        item.deactivated = true;
    }

    return item;
}

export function get_email_from_item(item: InputPillItem<UserPill>): string {
    return item.email;
}

export function append_person(opts: {
    person: User;
    pill_widget: UserPillWidget | CombinedPillContainer;
}): void {
    const person = opts.person;
    const pill_widget = opts.pill_widget;
    const avatar_url = people.small_avatar_url_for_person(person);
    const status_emoji_info = user_status.get_status_emoji(opts.person.user_id);

    const pill_data: InputPillItem<UserPill> = {
        type: "user",
        display_value: person.full_name,
        user_id: person.user_id,
        email: person.email,
        img_src: avatar_url,
        status_emoji_info,
        should_add_guest_user_indicator: people.should_add_guest_user_indicator(person.user_id),
    };

    pill_widget.appendValidatedData(pill_data);
    pill_widget.clear_text();
}

export function get_user_ids(pill_widget: UserPillWidget | CombinedPillContainer): number[] {
    const items = pill_widget.items();
    return items.flatMap((item) => (item.type === "user" ? item.user_id ?? [] : [])); // be defensive about undefined users
}

export function has_unconverted_data(pill_widget: UserPillWidget): boolean {
    // This returns true if we either have text that hasn't been
    // turned into pills or email-only pills (for Zephyr).
    if (pill_widget.is_pending()) {
        return true;
    }

    const items = pill_widget.items();
    const has_unknown_items = items.some((item) => item.user_id === undefined);

    return has_unknown_items;
}

export function typeahead_source(
    pill_widget: CombinedPillContainer,
    exclude_bots?: boolean,
): UserPillData[] {
    const users = exclude_bots ? people.get_realm_active_human_users() : people.get_realm_users();
    return filter_taken_users(users, pill_widget).map((user) => ({
        ...user,
        type: "user",
    }));
}

export function filter_taken_users(
    items: User[],
    pill_widget: UserPillWidget | CombinedPillContainer,
): User[] {
    const taken_user_ids = get_user_ids(pill_widget);
    items = items.filter((item) => !taken_user_ids.includes(item.user_id));
    return items;
}

export function append_user(user: User, pills: CombinedPillContainer): void {
    if (user) {
        append_person({
            pill_widget: pills,
            person: user,
        });
    } else {
        blueslip.warn("Undefined user in function append_user");
    }
}

export function create_pills(
    $pill_container: JQuery,
    pill_config?: InputPillConfig | undefined,
): input_pill.InputPillContainer<UserPill> {
    const pills = input_pill.create({
        $container: $pill_container,
        pill_config,
        create_item_from_text: create_item_from_email,
        get_text_from_item: get_email_from_item,
    });
    return pills;
}
