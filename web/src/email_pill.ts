import * as blueslip from "./blueslip";
import type {InputPillConfig, InputPillContainer, InputPillItem} from "./input_pill";
import * as input_pill from "./input_pill";
import type {User} from "./people";
import * as people from "./people";

type UserPill = {
    email: string;
};

export type UserPillWidget = InputPillContainer<UserPill>;

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function create_item_from_email(
    email: string,
    current_items: InputPillItem<UserPill>[],
): InputPillItem<UserPill> | undefined {
    if (!emailRegex.test(email)) {
        return undefined;
    }

    const existing_emails = current_items.map((item) => item.email);
    if (existing_emails.includes(email)) {
        return undefined;
    }

    return {
        type: "user",
        display_value: email,
        email,
    };
}

export function get_email_from_item(item: InputPillItem<UserPill>): string {
    return item.email;
}

export function append_person(opts: {person: User; pill_widget: UserPillWidget}): void {
    const person = opts.person;
    const pill_widget = opts.pill_widget;

    const pill_data = {
        type: "user",
        display_value: person.full_name,
        email: person.email,
        should_add_guest_user_indicator: people.should_add_guest_user_indicator(person.user_id),
    };

    pill_widget.appendValidatedData(pill_data);
    pill_widget.clear_text();
}

export function get_user_ids(pill_widget: UserPillWidget): string[] {
    const items = pill_widget.items();
    return items.flatMap((item) => item.email ?? []); // be defensive about undefined users
}

export function typeahead_source(pill_widget: UserPillWidget, exclude_bots?: boolean): User[] {
    const users = exclude_bots ? people.get_realm_active_human_users() : people.get_realm_users();
    return filter_taken_users(users, pill_widget);
}

export function filter_taken_users(items: User[], pill_widget: UserPillWidget): User[] {
    const taken_user_emails = get_user_ids(pill_widget);
    items = items.filter((item) => !taken_user_emails.includes(item.email));
    return items;
}

export function append_user(user: User, pills: UserPillWidget): void {
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
