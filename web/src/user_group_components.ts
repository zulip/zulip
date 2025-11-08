import $ from "jquery";

import {$t_html} from "./i18n.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import * as resize from "./resize.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";
import * as user_sort from "./user_sort.ts";
import * as util from "./util.ts";

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
        $("#groups_overlay .deactivated-user-group-icon-right").hide();
        resize.resize_settings_overlay($("#groups_overlay_container"));
    },
    settings(group: UserGroup) {
        $("#groups_overlay .nothing-selected, #user-group-creation").hide();
        $("#groups_overlay .settings").show();
        set_active_group_id(group.id);
        const group_name = user_groups.get_display_group_name(group.name);
        $("#groups_overlay .user-group-info-title").text(group_name).addClass("showing-info-title");
        if (group.deactivated) {
            $("#groups_overlay .deactivated-user-group-icon-right").show();
        } else {
            $("#groups_overlay .deactivated-user-group-icon-right").hide();
        }
        resize.resize_settings_overlay($("#groups_overlay_container"));
    },
    create_user_group(container_name = "configure_user_group_settings", group_name?: string) {
        $(".user_group_creation").hide();
        if (container_name === "configure_user_group_settings") {
            $("#groups_overlay .user-group-info-title").text(
                $t_html({defaultMessage: "Configure new group settings"}),
            );
        } else {
            $("#groups_overlay .user-group-info-title")
                .text($t_html({defaultMessage: "Add members to {group_name}"}, {group_name}))
                .addClass("showing-info-title");
        }
        update_footer_buttons(container_name);
        $(`.${CSS.escape(container_name)}`).show();
        $("#groups_overlay .nothing-selected, #groups_overlay .settings").hide();
        reset_active_group_id();
        $("#user-group-creation").show();
        $("#groups_overlay .deactivated-user-group-icon-right").hide();
        resize.resize_settings_overlay($("#groups_overlay_container"));
        resize.resize_settings_creation_overlay($("#groups_overlay_container"));
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

export function sort_group_member_email(a: User | UserGroup, b: User | UserGroup): number {
    if ("user_id" in a && "user_id" in b) {
        return user_sort.sort_email(a, b);
    }

    if ("user_id" in a) {
        return -1;
    }

    if ("user_id" in b) {
        return 1;
    }

    return util.compare_a_b(a.name.toLowerCase(), b.name.toLowerCase());
}

export function sort_group_member_name(a: User | UserGroup, b: User | UserGroup): number {
    let a_name;
    if ("user_id" in a) {
        a_name = a.full_name;
    } else {
        a_name = a.name;
    }

    let b_name;
    if ("user_id" in b) {
        b_name = b.full_name;
    } else {
        b_name = b.name;
    }

    return util.compare_a_b(a_name.toLowerCase(), b_name.toLowerCase());
}

export function build_group_member_matcher(query: string): (member: User | UserGroup) => boolean {
    query = query.trim();

    const termlets = query.toLowerCase().split(/\s+/);
    const termlet_matchers = termlets.map((termlet) => people.build_termlet_matcher(termlet));

    return function (member: User | UserGroup): boolean {
        if ("user_id" in member) {
            const email = member.email.toLowerCase();

            if (email.startsWith(query)) {
                return true;
            }

            return termlet_matchers.every((matcher) => matcher(member));
        }

        const group_name = user_groups.get_display_group_name(member.name).toLowerCase();
        if (group_name.startsWith(query)) {
            return true;
        }
        return false;
    };
}
