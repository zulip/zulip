import $ from "jquery";
import assert from "minimalistic-assert";

import * as dropdown_widget from "./dropdown_widget";
import * as group_permission_settings from "./group_permission_settings";
import {$t_html} from "./i18n";
import * as settings_components from "./settings_components";
import * as user_groups from "./user_groups";
import type {UserGroup} from "./user_groups";

export let active_group_id: number | undefined;

type group_setting = "can_manage_group" | "can_mention_group";
export function setup_permissions_dropdown(
    setting_name: group_setting,
    group: UserGroup | undefined,
    for_group_creation: boolean,
): void {
    let widget_name: string;
    let default_id: number;
    if (for_group_creation) {
        widget_name = "new_group_" + setting_name;
        const group_setting_config = group_permission_settings.get_group_permission_setting_config(
            setting_name,
            "group",
        )!;
        const default_group_name = group_setting_config.default_group_name;
        default_id = user_groups.get_user_group_from_name(default_group_name)!.id;
    } else {
        assert(group !== undefined);
        widget_name = setting_name;
        default_id = group[setting_name];
    }

    const group_setting_widget = new dropdown_widget.DropdownWidget({
        widget_name,
        get_options: () =>
            user_groups.get_realm_user_groups_for_dropdown_list_widget(setting_name, "group"),
        item_click_callback(event, dropdown) {
            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
            group_setting_widget.render();
            if (!for_group_creation) {
                assert(group !== undefined);
                settings_components.save_discard_group_widget_status_handler(
                    $("#group_permission_settings"),
                    group,
                );
            }
        },
        $events_container: $("#groups_overlay .group-permissions"),
        default_id,
        unique_id_type: dropdown_widget.DataTypes.NUMBER,
        on_mount_callback(dropdown) {
            $(dropdown.popper).css("min-width", "300px");
            $(dropdown.popper).find(".simplebar-content").css("width", "max-content");
        },
    });
    if (for_group_creation) {
        if (setting_name === "can_mention_group") {
            settings_components.set_new_group_can_mention_group_widget(group_setting_widget);
        } else {
            settings_components.set_new_group_can_manage_group_widget(group_setting_widget);
        }
    } else {
        settings_components.set_dropdown_setting_widget(setting_name, group_setting_widget);
    }
    group_setting_widget.setup();
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
    create_user_group(container_name = "configure_user_group_settings", group_name?: string) {
        $(".user_group_creation").hide();
        if (container_name === "configure_user_group_settings") {
            $("#groups_overlay .user-group-info-title").text(
                $t_html({defaultMessage: "Configure new group settings"}),
            );
        } else {
            $("#groups_overlay .user-group-info-title").text(
                $t_html({defaultMessage: "Add members to {group_name}"}, {group_name}),
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
