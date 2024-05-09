import $ from "jquery";

import * as dropdown_widget from "./dropdown_widget";
import {$t_html} from "./i18n";
import * as settings_components from "./settings_components";
import * as user_groups from "./user_groups";
import type {UserGroup} from "./user_groups";

export let active_group_id: number | undefined;

export function setup_permissions_dropdown(group: UserGroup, for_group_creation: boolean): void {
    let widget_name: string;
    let default_id: number;
    if (for_group_creation) {
        widget_name = "new_group_can_mention_group";
        default_id = user_groups.get_user_group_from_name("role:everyone")!.id;
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
                settings_components.save_discard_group_widget_status_handler(
                    $("#group_permission_settings"),
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
        settings_components.set_dropdown_setting_widget(
            "can_mention_group",
            can_mention_group_widget,
        );
    }
    can_mention_group_widget.setup();
}

export function set_active_group_id(group_id: number): void {
    active_group_id = group_id;
}

export function reset_active_group_id(): void {
    active_group_id = undefined;
}

export const show_user_group_settings_pane = {
    nothing_selected() {
        $("#groups_overlay .settings, #user-group-creation").hide();
        reset_active_group_id();
        $("#groups_overlay .nothing-selected").show();
        $("#groups_overlay .user-group-info-title").text(
            $t_html({defaultMessage: "User group settings"}),
        );
    },
    settings(group: UserGroup) {
        $("#groups_overlay .nothing-selected, #user-group-creation").hide();
        $("#groups_overlay .settings").show();
        set_active_group_id(group.id);
        $("#groups_overlay .user-group-info-title").text(group.name);
    },
    create_user_group(container_name = "configure_user_group_settings") {
        $(".user_group_creation").hide();
        if (container_name === "configure_user_group_settings") {
            $("#groups_overlay .user-group-info-title").text(
                $t_html({defaultMessage: "Create user group: configure settings"}),
            );
        } else {
            $("#groups_overlay .user-group-info-title").text(
                $t_html({defaultMessage: "Create user group: add members"}),
            );
        }
        update_footer_buttons(container_name);
        $(`.${container_name}`).show();
        $("#groups_overlay .nothing-selected, #groups_overlay .settings").hide();
        reset_active_group_id();
        $("#user-group-creation").show();
    },
};

export function update_footer_buttons(container_name: string): void {
    if (container_name === "user_group_members_container") {
        // Hide user group creation containers and show add members container
        $("#groups_overlay .finalize_create_user_group").show();
        $("#groups_overlay #user_group_go_to_members").hide();
        $("#groups_overlay #user_group_go_to_configure_settings").show();
    } else {
        // Hide add members container and show user group creation containers
        $("#groups_overlay .finalize_create_user_group").hide();
        $("#groups_overlay #user_group_go_to_members").show();
        $("#groups_overlay #user_group_go_to_configure_settings").hide();
    }
}
