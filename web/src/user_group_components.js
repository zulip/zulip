import $ from "jquery";

import * as dropdown_widget from "./dropdown_widget";
import * as settings_components from "./settings_components";
import * as user_groups from "./user_groups";

export function setup_permissions_dropdown(group, for_group_creation) {
    let widget_name;
    let default_id;
    if (for_group_creation) {
        widget_name = "new_group_can_mention_group";
        default_id = user_groups.get_user_group_from_name("role:everyone").id;
    } else {
        widget_name = "can_mention_group";
        default_id = group.can_mention_group;
    }

    const can_mention_group_widget = new dropdown_widget.DropdownWidget({
        widget_name,
        get_options: () =>
            user_groups.get_realm_user_groups_for_dropdown_list_widget(
                "can_mention_group",
                "group",
            ),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            can_mention_group_widget.render();
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
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        on_mount_callback(dropdown) {
            $(dropdown.popper).css("min-width", "300px");
        },
    });
    if (for_group_creation) {
        settings_components.set_new_group_can_mention_group_widget(can_mention_group_widget);
    } else {
        settings_components.set_can_mention_group_widget(can_mention_group_widget);
    }
    can_mention_group_widget.setup();
}
