import assert from "minimalistic-assert";

import * as add_subscribers_pill from "./add_subscribers_pill.ts";
import * as input_pill from "./input_pill.ts";
import * as keydown_util from "./keydown_util.ts";
import type {User} from "./people.ts";
import * as stream_pill from "./stream_pill.ts";
import type {CombinedPill, CombinedPillContainer} from "./typeahead_helper.ts";
import * as user_group_components from "./user_group_components.ts";
import * as user_group_create_members_data from "./user_group_create_members_data.ts";
import * as user_group_pill from "./user_group_pill.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_pill from "./user_pill.ts";

function get_pill_user_ids(pill_widget: CombinedPillContainer): number[] {
    const user_ids = user_pill.get_user_ids(pill_widget);
    const stream_user_ids = stream_pill.get_user_ids(pill_widget);
    return [...user_ids, ...stream_user_ids];
}

function get_pill_group_ids(pill_widget: CombinedPillContainer): number[] {
    const group_user_ids = user_group_pill.get_group_ids(pill_widget);
    return group_user_ids;
}

export function create_item_from_text(
    text: string,
    current_items: CombinedPill[],
): CombinedPill | undefined {
    const funcs = [
        stream_pill.create_item_from_stream_name,
        user_group_pill.create_item_from_group_name,
        user_pill.create_item_from_email,
    ];

    const stream_item = stream_pill.create_item_from_stream_name(text, current_items);
    if (stream_item) {
        return stream_item;
    }

    const group_item = user_group_pill.create_item_from_group_name(text, current_items);
    if (group_item) {
        const subgroup = user_groups.get_user_group_from_id(group_item.group_id);
        const current_group_id = user_group_components.active_group_id;
        assert(current_group_id !== undefined);
        const current_group = user_groups.get_user_group_from_id(current_group_id);
        if (user_groups.check_group_can_be_subgroup(subgroup, current_group)) {
            return group_item;
        }

        return undefined;
    }
    for (const func of funcs) {
        const item = func(text, current_items);
        if (item) {
            return item;
        }
    }
    return undefined;
}

export function create({
    $pill_container,
    get_potential_members,
    get_potential_groups,
}: {
    $pill_container: JQuery;
    get_potential_members: () => User[];
    get_potential_groups: () => UserGroup[];
}): CombinedPillContainer {
    const pill_widget = input_pill.create<CombinedPill>({
        $container: $pill_container,
        create_item_from_text,
        get_text_from_item: add_subscribers_pill.get_text_from_item,
        get_display_value_from_item: add_subscribers_pill.get_display_value_from_item,
        generate_pill_html: add_subscribers_pill.generate_pill_html,
        show_outline_on_invalid_input: true,
    });
    function get_users(): User[] {
        const potential_members = get_potential_members();
        return user_pill.filter_taken_users(potential_members, pill_widget);
    }

    function get_user_groups(): UserGroup[] {
        const potential_groups = get_potential_groups();
        return user_group_pill.filter_taken_groups(potential_groups, pill_widget);
    }

    add_subscribers_pill.set_up_pill_typeahead({
        pill_widget,
        $pill_container,
        get_users,
        get_user_groups,
    });

    add_subscribers_pill.set_up_handlers_for_add_button_state(pill_widget, $pill_container);

    return pill_widget;
}

export function create_without_add_button({
    $pill_container,
    onPillCreateAction,
    onPillRemoveAction,
}: {
    $pill_container: JQuery;
    onPillCreateAction: (pill_user_ids: number[], pill_subgroup_ids: number[]) => void;
    onPillRemoveAction: (pill_user_ids: number[], pill_subgroup_ids: number[]) => void;
}): CombinedPillContainer {
    const pill_widget = input_pill.create<CombinedPill>({
        $container: $pill_container,
        create_item_from_text: add_subscribers_pill.create_item_from_text,
        get_text_from_item: add_subscribers_pill.get_text_from_item,
        get_display_value_from_item: add_subscribers_pill.get_display_value_from_item,
        generate_pill_html: add_subscribers_pill.generate_pill_html,
        show_outline_on_invalid_input: true,
    });
    function get_users(): User[] {
        const potential_members = user_group_create_members_data.get_potential_members();
        return user_pill.filter_taken_users(potential_members, pill_widget);
    }

    function get_user_groups(): UserGroup[] {
        const potential_subgroups = user_group_create_members_data.get_potential_subgroups();
        return user_group_pill.filter_taken_groups(potential_subgroups, pill_widget);
    }

    pill_widget.onPillCreate(() => {
        onPillCreateAction(get_pill_user_ids(pill_widget), get_pill_group_ids(pill_widget));
    });
    pill_widget.onPillRemove(() => {
        onPillRemoveAction(get_pill_user_ids(pill_widget), get_pill_group_ids(pill_widget));
    });

    add_subscribers_pill.set_up_pill_typeahead({
        pill_widget,
        $pill_container,
        get_users,
        get_user_groups,
    });

    return pill_widget;
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
    action: ({
        pill_user_ids,
        pill_group_ids,
    }: {
        pill_user_ids: number[];
        pill_group_ids: number[];
    }) => void;
}): void {
    /*
        This is similar to add_subscribers_pill.set_up_handlers
        with only difference that selecting a user group does
        not add all its members to list, but instead just adds
        the group itself.
    */
    function callback(): void {
        const pill_widget = get_pill_widget();
        const pill_user_ids = get_pill_user_ids(pill_widget);
        const pill_group_ids = get_pill_group_ids(pill_widget);
        action({pill_user_ids, pill_group_ids});
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
