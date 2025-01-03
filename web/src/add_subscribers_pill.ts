import assert from "minimalistic-assert";

import render_input_pill from "../templates/input_pill.hbs";

import * as blueslip from "./blueslip.ts";
import * as input_pill from "./input_pill.ts";
import * as keydown_util from "./keydown_util.ts";
import type {User} from "./people.ts";
import * as pill_typeahead from "./pill_typeahead.ts";
import * as stream_pill from "./stream_pill.ts";
import type {CombinedPill, CombinedPillContainer} from "./typeahead_helper.ts";
import * as user_group_pill from "./user_group_pill.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_pill from "./user_pill.ts";

export function create_item_from_text(
    text: string,
    current_items: CombinedPill[],
): CombinedPill | undefined {
    const funcs = [
        stream_pill.create_item_from_stream_name,
        user_group_pill.create_item_from_group_name,
        user_pill.create_item_from_email,
    ];
    for (const func of funcs) {
        const item = func(text, current_items);
        if (item) {
            return item;
        }
    }
    return undefined;
}

export function get_text_from_item(item: CombinedPill): string {
    let text: string;
    switch (item.type) {
        case "stream":
            text = stream_pill.get_stream_name_from_item(item);
            break;
        case "user_group":
            text = user_group_pill.get_group_name_from_item(item);
            break;
        case "user":
            text = user_pill.get_email_from_item(item);
            break;
    }
    return text;
}

export function set_up_pill_typeahead({
    pill_widget,
    $pill_container,
    get_users,
    get_user_groups,
}: {
    pill_widget: CombinedPillContainer;
    $pill_container: JQuery;
    get_users: () => User[];
    get_user_groups?: () => UserGroup[];
}): void {
    const opts: {
        user_source: () => User[];
        stream: boolean;
        user_group: boolean;
        user: boolean;
        user_group_source?: () => UserGroup[];
    } = {
        user_source: get_users,
        stream: true,
        user_group: true,
        user: true,
    };
    if (get_user_groups !== undefined) {
        opts.user_group_source = get_user_groups;
    }
    pill_typeahead.set_up_combined($pill_container.find(".input"), pill_widget, opts);
}

export function get_display_value_from_item(item: CombinedPill): string {
    if (item.type === "user_group") {
        return user_group_pill.display_pill(user_groups.get_user_group_from_id(item.group_id));
    } else if (item.type === "stream") {
        return stream_pill.get_display_value_from_item(item);
    }
    assert(item.type === "user");
    return user_pill.get_display_value_from_item(item);
}

export function generate_pill_html(item: CombinedPill): string {
    if (item.type === "user_group") {
        return render_input_pill({
            display_value: get_display_value_from_item(item),
            group_id: item.group_id,
        });
    } else if (item.type === "user") {
        return user_pill.generate_pill_html(item);
    }
    assert(item.type === "stream");
    return stream_pill.generate_pill_html(item);
}

export function set_up_handlers_for_add_button_state(
    pill_widget: CombinedPillContainer,
    $pill_container: JQuery,
): void {
    const $pill_widget_input = $pill_container.find(".input");
    const $pill_widget_button = $pill_container.parent().find(".add-users-button");

    // Disable the add button first time the pill container is created.
    $pill_widget_button.prop("disabled", true);

    // If all the pills are removed, disable the add button.
    pill_widget.onPillRemove(() =>
        $pill_widget_button.prop("disabled", pill_widget.items().length === 0),
    );
    // Disable the add button when there is no pending text that can be converted
    // into a pill and the number of existing pills is zero.
    $pill_widget_input.on("input", () =>
        $pill_widget_button.prop(
            "disabled",
            !pill_widget.is_pending() && pill_widget.items().length === 0,
        ),
    );
}

export function create({
    $pill_container,
    get_potential_subscribers,
}: {
    $pill_container: JQuery;
    get_potential_subscribers: () => User[];
}): CombinedPillContainer {
    const pill_widget = input_pill.create<CombinedPill>({
        $container: $pill_container,
        create_item_from_text,
        get_text_from_item,
        get_display_value_from_item,
        generate_pill_html,
        show_outline_on_invalid_input: true,
    });
    function get_users(): User[] {
        const potential_subscribers = get_potential_subscribers();
        return user_pill.filter_taken_users(potential_subscribers, pill_widget);
    }

    set_up_pill_typeahead({pill_widget, $pill_container, get_users});

    set_up_handlers_for_add_button_state(pill_widget, $pill_container);

    return pill_widget;
}

export function create_without_add_button({
    $pill_container,
    get_potential_subscribers,
    onPillCreateAction,
    onPillRemoveAction,
}: {
    $pill_container: JQuery;
    get_potential_subscribers: () => User[];
    onPillCreateAction: (pill_user_ids: number[]) => void;
    onPillRemoveAction: (pill_user_ids: number[]) => void;
}): CombinedPillContainer {
    const pill_widget = input_pill.create<CombinedPill>({
        $container: $pill_container,
        create_item_from_text,
        get_text_from_item,
        get_display_value_from_item,
        generate_pill_html,
        show_outline_on_invalid_input: true,
    });
    function get_users(): User[] {
        const potential_subscribers = get_potential_subscribers();
        return user_pill.filter_taken_users(potential_subscribers, pill_widget);
    }

    pill_widget.onPillCreate(() => {
        onPillCreateAction(get_pill_user_ids(pill_widget));
    });
    pill_widget.onPillRemove(() => {
        onPillRemoveAction(get_pill_user_ids(pill_widget));
    });

    set_up_pill_typeahead({pill_widget, $pill_container, get_users});

    return pill_widget;
}

export function append_user_group_from_name(
    user_group_name: string,
    pill_widget: CombinedPillContainer,
): void {
    const user_group = user_groups.get_user_group_from_name(user_group_name);
    if (user_group === undefined) {
        // This shouldn't happen, but we'll give a warning for now if it
        // does.
        blueslip.error("User group with the given name does not exist.");
        return;
    }

    user_group_pill.append_user_group(user_group, pill_widget);
}

function get_pill_user_ids(pill_widget: CombinedPillContainer): number[] {
    const user_ids = user_pill.get_user_ids(pill_widget);
    const stream_user_ids = stream_pill.get_user_ids(pill_widget);
    const group_user_ids = user_group_pill.get_user_ids(pill_widget);
    return [...user_ids, ...stream_user_ids, ...group_user_ids];
}

export function set_up_handlers({
    get_pill_widget,
    $parent_container,
    pill_selector,
    button_selector,
    action,
}: {
    get_pill_widget: () => CombinedPillContainer;
    $parent_container: JQuery;
    pill_selector: string;
    button_selector: string;
    action: ({pill_user_ids}: {pill_user_ids: number[]}) => void;
}): void {
    /*
        This function handles events for any UI that looks like
        this:

            [pill-enabled input box for subscribers] [Add button]

        In an ideal world the above two widgets would be enclosed in
        a <form>...</form> section and we would have a single submit
        handler, but our current implementation of input pills has
        some magic that prevents the pills from playing nice with
        the vanilla HTML form/submit mechanism.

        So, instead, we provide this helper function to manage
        the two events needed to make it look like the widgets
        are inside an actual HTML <form> tag.

        This abstraction also automatically retrieves the user_ids
        from the input pill and sends them back to the `action`
        function passed in.

        The subscriber input-pill widgets lets you provide
        user_ids by creating pills for either:

            * single user
            * user group
            * stream (i.e. subscribed users for the stream)
    */
    function callback(): void {
        const pill_widget = get_pill_widget();
        const pill_user_ids = get_pill_user_ids(pill_widget);
        action({pill_user_ids});
    }

    $parent_container.on("keyup", pill_selector, (e) => {
        const pill_widget = get_pill_widget();
        if (!pill_widget.is_pending() && keydown_util.is_enter_event(e)) {
            e.preventDefault();
            callback();
        }
    });

    $parent_container.on("click", button_selector, (e) => {
        const pill_widget = get_pill_widget();
        if (!pill_widget.is_pending()) {
            e.preventDefault();
            callback();
        } else {
            // We are not appending any value here, but instead this is
            // a proxy to invoke the error state for a pill widget
            // that would usually get triggered on pressing enter.
            pill_widget.appendValue(pill_widget.getCurrentText()!);
        }
    });
}
