import render_input_pill from "../templates/input_pill.hbs";

import {set_up_handlers_for_add_button_state} from "./add_subscribers_pill.ts";
import * as input_pill from "./input_pill.ts";
import {set_up_user_group} from "./pill_typeahead.ts";
import * as settings_data from "./settings_data.ts";
import * as user_group_pill from "./user_group_pill.ts";
import type {UserGroupPill} from "./user_group_pill.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";

type SetUpPillTypeaheadConfig = {
    pill_widget: user_group_pill.UserGroupPillWidget;
    $pill_container: JQuery;
};

function create_item_from_group_name(
    group_name: string,
    current_items: UserGroupPill[],
    pill_config?: input_pill.InputPillConfig,
): UserGroupPill | undefined {
    group_name = group_name.trim();
    const group = user_groups.get_user_group_from_name(group_name);
    if (!group) {
        return undefined;
    }

    if (!settings_data.can_add_members_to_user_group(group.id)) {
        return undefined;
    }

    if (current_items.some((item) => item.type === "user_group" && item.group_id === group.id)) {
        return undefined;
    }

    // Check if the user is already a direct member of the user group.
    const user_id = pill_config?.user_id;
    if (user_id !== undefined && user_groups.is_direct_member_of(user_id, group.id)) {
        return undefined;
    }

    return {
        type: "user_group",
        group_id: group.id,
        group_name: group.name,
    };
}

export function get_user_groups_allowed_to_add_members(): UserGroup[] {
    const all_user_groups = user_groups.get_realm_user_groups();
    return all_user_groups.filter((group) => settings_data.can_add_members_to_user_group(group.id));
}

function set_up_pill_typeahead(
    {pill_widget, $pill_container}: SetUpPillTypeaheadConfig,
    user_id?: number,
): void {
    const user_group_source: () => UserGroup[] = () => {
        let groups_with_permission = get_user_groups_allowed_to_add_members();
        if (user_id !== undefined) {
            groups_with_permission = groups_with_permission.filter(
                (group) => !user_groups.is_direct_member_of(user_id, group.id),
            );
        }
        return user_group_pill.filter_taken_groups(groups_with_permission, pill_widget);
    };
    set_up_user_group($pill_container.find(".input"), pill_widget, {user_group_source});
}

function get_display_value_from_item(item: UserGroupPill): string {
    return user_groups.get_display_group_name(item.group_name);
}

function generate_pill_html(item: UserGroupPill): string {
    return render_input_pill({
        group_id: item.group_id,
        display_value: user_groups.get_display_group_name(item.group_name),
    });
}

export function create(
    $user_group_pill_container: JQuery,
    user_id?: number,
): user_group_pill.UserGroupPillWidget {
    const pill_config = user_id ? {user_id} : undefined;

    const pill_widget = input_pill.create({
        $container: $user_group_pill_container,
        pill_config,
        create_item_from_text: create_item_from_group_name,
        get_text_from_item: user_group_pill.get_group_name_from_item,
        generate_pill_html,
        get_display_value_from_item,
    });

    set_up_pill_typeahead({pill_widget, $pill_container: $user_group_pill_container}, user_id);
    if (user_id) {
        set_up_handlers_for_add_button_state(pill_widget, $user_group_pill_container);
    }
    return pill_widget;
}
