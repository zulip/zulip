import $ from "jquery";

import {$t_html} from "./i18n";
import type {UserGroup} from "./user_groups";

export let active_group_id: number | undefined;

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
        $(`.${CSS.escape(container_name)}`).show();
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
