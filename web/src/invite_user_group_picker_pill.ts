import * as input_pill from "./input_pill";
import {set_up_user_group} from "./pill_typeahead";
import type {CombinedPill} from "./typeahead_helper";
import * as user_group_pill from "./user_group_pill";
import type {UserGroupPill} from "./user_group_pill";

type SetUpPillTypeaheadConfig = {
    pill_widget: user_group_pill.UserGroupPillWidget;
    $pill_container: JQuery;
};

function create_item_from_group_name(
    user_group_name: string,
    current_items: CombinedPill[],
): UserGroupPill | undefined {
    return user_group_pill.create_item_from_group_name(user_group_name, current_items);
}

function set_up_pill_typeahead({pill_widget, $pill_container}: SetUpPillTypeaheadConfig): void {
    const opts = {
        help_on_empty_strings: true,
        hide_on_empty_after_backspace: true,
    };
    set_up_user_group($pill_container.find(".input"), pill_widget, opts);
}

export function create($user_group_pill_container: JQuery): user_group_pill.UserGroupPillWidget {
    const pill_widget = input_pill.create({
        $container: $user_group_pill_container,
        create_item_from_text: create_item_from_group_name,
        get_text_from_item: user_group_pill.get_group_name_from_item,
        generate_pill_html: user_group_pill.generate_pill_html,
        get_display_value_from_item: user_group_pill.get_display_value_from_item,
    });

    set_up_pill_typeahead({pill_widget, $pill_container: $user_group_pill_container});
    return pill_widget;
}
