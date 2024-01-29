import $ from "jquery";

import * as dropdown_widget from "./dropdown_widget";
import * as group_permission_settings from "./group_permission_settings";
import * as people from "./people";
import * as settings_components from "./settings_components";
import * as user_groups from "./user_groups";

function setup_dropdown_for_setting(setting_name, for_group_creation, group, default_group_name) {
    let widget_name;
    let default_id;
    if (for_group_creation) {
        widget_name = "new_group_" + setting_name;
        if (default_group_name === "creating_user") {
            default_id = group_permission_settings.get_user_system_group_name_from_user_id(
                people.my_current_user_id(),
            );
        } else {
            default_id = user_groups.get_user_group_from_name(default_group_name).id;
        }
    } else {
        widget_name = setting_name;
        default_id = group[setting_name];
    }

    let unique_id_type = dropdown_widget.DATA_TYPES.NUMBER;
    if (for_group_creation && setting_name === "can_manage_group") {
        unique_id_type = dropdown_widget.DATA_TYPES.NUMBER_OR_STRING;
    }

    const setting_widget = new dropdown_widget.DropdownWidget({
        widget_name,
        get_options: () =>
            group_permission_settings.get_realm_user_groups_for_dropdown_list_widget(
                setting_name,
                "group",
                group,
            ),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            setting_widget.render();
            if (!for_group_creation) {
                settings_components.save_discard_widget_status_handler(
                    $("#group_permission_settings"),
                    false,
                    undefined,
                    group,
                );
            }
        },
        $events_container: $("#groups_overlay .group-permissions"),
        tippy_props: {
            placement: "bottom-start",
        },
        default_id,
        unique_id_type,
        on_mount_callback(dropdown) {
            $(dropdown.popper).css("min-width", "300px");
        },
    });

    return setting_widget;
}

export function setup_permissions_dropdown(group, for_group_creation) {
    const can_mention_group_widget = setup_dropdown_for_setting(
        "can_mention_group",
        for_group_creation,
        group,
        "role:everyone",
    );
    const can_manage_group_widget = setup_dropdown_for_setting(
        "can_manage_group",
        for_group_creation,
        group,
        "creating_user",
    );

    if (for_group_creation) {
        settings_components.set_new_group_can_mention_group_widget(can_mention_group_widget);
        settings_components.set_new_group_can_manage_group_widget(can_manage_group_widget);
    } else {
        settings_components.set_can_mention_group_widget(can_mention_group_widget);
        settings_components.set_can_manage_group_widget(can_manage_group_widget);
    }
    can_mention_group_widget.setup();
    can_manage_group_widget.setup();
}
