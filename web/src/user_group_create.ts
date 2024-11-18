import $ from "jquery";
import assert from "minimalistic-assert";

import * as channel from "./channel.ts";
import {$t, $t_html} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as loading from "./loading.ts";
import * as settings_components from "./settings_components.ts";
import type {GroupSettingPillContainer} from "./typeahead_helper.ts";
import * as ui_report from "./ui_report.ts";
import * as user_group_components from "./user_group_components.ts";
import * as user_group_create_members from "./user_group_create_members.ts";
import * as user_group_create_members_data from "./user_group_create_members_data.ts";
import * as user_groups from "./user_groups.ts";

let created_group_name: string | undefined;

export function reset_name(): void {
    created_group_name = undefined;
}

export function set_name(group_name: string): void {
    created_group_name = group_name;
}

export function get_name(): string | undefined {
    return created_group_name;
}

let can_add_members_group_widget: GroupSettingPillContainer | undefined;
let can_join_group_widget: GroupSettingPillContainer | undefined;
let can_leave_group_widget: GroupSettingPillContainer | undefined;
let can_manage_group_widget: GroupSettingPillContainer | undefined;
let can_mention_group_widget: GroupSettingPillContainer | undefined;

class UserGroupMembershipError {
    report_no_members_to_user_group(): void {
        $("#user_group_membership_error").text(
            $t({defaultMessage: "You cannot create a user group with no members or subgroups."}),
        );
        $("#user_group_membership_error").show();
    }

    clear_errors(): void {
        $("#user_group_membership_error").hide();
    }
}
const user_group_membership_error = new UserGroupMembershipError();

class UserGroupNameError {
    report_already_exists(): void {
        $("#user_group_name_error").text(
            $t({defaultMessage: "A user group with this name already exists."}),
        );
        $("#user_group_name_error").show();
    }

    clear_errors(): void {
        $("#user_group_name_error").hide();
    }

    report_empty_user_group(): void {
        $("#user_group_name_error").text(
            $t({defaultMessage: "Choose a name for the new user group."}),
        );
        $("#user_group_name_error").show();
    }

    select(): void {
        $("#create_user_group_name").trigger("focus").trigger("select");
    }

    pre_validate(user_group_name: string): void {
        if (user_group_name && user_groups.get_user_group_from_name(user_group_name)) {
            this.report_already_exists();
            return;
        }

        this.clear_errors();
    }

    validate_for_submit(user_group_name: string): boolean {
        if (!user_group_name) {
            this.report_empty_user_group();
            this.select();
            return false;
        }

        if (user_groups.get_user_group_from_name(user_group_name)) {
            this.report_already_exists();
            this.select();
            return false;
        }

        return true;
    }
}
const user_group_name_error = new UserGroupNameError();

$("body").on("click", ".settings-sticky-footer #user_group_go_to_members", (e) => {
    e.preventDefault();
    e.stopPropagation();

    const group_name = $<HTMLInputElement>("input#create_user_group_name").val()!.trim();
    const is_user_group_name_valid = user_group_name_error.validate_for_submit(group_name);

    if (is_user_group_name_valid) {
        user_group_components.show_user_group_settings_pane.create_user_group(
            "user_group_members_container",
            group_name,
        );
    }
});

$("body").on("click", ".settings-sticky-footer #user_group_go_to_configure_settings", (e) => {
    e.preventDefault();
    e.stopPropagation();
    user_group_components.show_user_group_settings_pane.create_user_group(
        "configure_user_group_settings",
    );
});

function clear_error_display(): void {
    user_group_name_error.clear_errors();
    $(".user_group_create_info").hide();
    user_group_membership_error.clear_errors();
}

export function show_new_user_group_modal(): void {
    $("#user-group-creation").removeClass("hide");
    $(".right .settings").hide();

    user_group_create_members.build_widgets();

    clear_error_display();
}

function create_user_group(): void {
    const group_name = $<HTMLInputElement>("input#create_user_group_name").val()!.trim();
    const description = $<HTMLInputElement>("input#create_user_group_description").val()!.trim();
    set_name(group_name);

    // Even though we already check to make sure that while typing the user cannot enter
    // newline characters (by pressing the Enter key) it would still be possible to copy
    // and paste over a description with newline characters in it. Prevent that.
    if (description.includes("\n")) {
        ui_report.client_error(
            $t_html({defaultMessage: "The group description cannot contain newline characters."}),
            $(".user_group_create_info"),
        );
        return;
    }
    const user_ids = user_group_create_members.get_principals();
    const subgroup_ids = user_group_create_members.get_subgroups();

    assert(can_add_members_group_widget !== undefined);
    const can_add_members_group = settings_components.get_group_setting_widget_value(
        can_add_members_group_widget,
    );

    assert(can_manage_group_widget !== undefined);
    const can_manage_group =
        settings_components.get_group_setting_widget_value(can_manage_group_widget);

    assert(can_join_group_widget !== undefined);
    const can_join_group =
        settings_components.get_group_setting_widget_value(can_join_group_widget);

    assert(can_leave_group_widget !== undefined);
    const can_leave_group =
        settings_components.get_group_setting_widget_value(can_leave_group_widget);

    assert(can_mention_group_widget !== undefined);
    const can_mention_group =
        settings_components.get_group_setting_widget_value(can_mention_group_widget);

    const data = {
        name: group_name,
        description,
        members: JSON.stringify(user_ids),
        subgroups: JSON.stringify(subgroup_ids),
        can_add_members_group: JSON.stringify(can_add_members_group),
        can_join_group: JSON.stringify(can_join_group),
        can_leave_group: JSON.stringify(can_leave_group),
        can_mention_group: JSON.stringify(can_mention_group),
        can_manage_group: JSON.stringify(can_manage_group),
    };
    loading.make_indicator($("#user_group_creating_indicator"), {
        text: $t({defaultMessage: "Creating group..."}),
    });

    void channel.post({
        url: "/json/user_groups/create",
        data,
        success() {
            $("#create_user_group_name").val("");
            $("#create_user_group_description").val("");
            user_group_create_members.clear_member_list();
            loading.destroy_indicator($("#user_group_creating_indicator"));
            // TODO: The rest of the work should be done via the create event we will get for user group.
        },
        error(xhr) {
            ui_report.error(
                $t_html({defaultMessage: "Error creating user group."}),
                xhr,
                $(".user_group_create_info"),
            );
            reset_name();
            loading.destroy_indicator($("#user_group_creating_indicator"));
        },
    });
}

export function set_up_handlers(): void {
    const $people_to_add_holder = $("#people_to_add_in_group").expectOne();
    user_group_create_members.create_handlers($people_to_add_holder);

    const $container = $("#user-group-creation").expectOne();

    $container.on("click", ".finalize_create_user_group", (e) => {
        e.preventDefault();
        clear_error_display();

        const group_name = $<HTMLInputElement>("input#create_user_group_name").val()!.trim();
        const name_ok = user_group_name_error.validate_for_submit(group_name);

        if (!name_ok) {
            user_group_components.show_user_group_settings_pane.create_user_group(
                "configure_user_group_settings",
            );
            return;
        }

        const principals = user_group_create_members_data.get_principals();
        const subgroups = user_group_create_members_data.get_subgroups();
        if (principals.length === 0 && subgroups.length === 0) {
            user_group_membership_error.report_no_members_to_user_group();
            return;
        }

        create_user_group();
    });

    $container.on("input", "#create_user_group_name", () => {
        const user_group_name = $<HTMLInputElement>("input#create_user_group_name").val()!.trim();

        // This is an inexpensive check.
        user_group_name_error.pre_validate(user_group_name);
    });

    // Do not allow the user to enter newline characters while typing out the
    // group's description during it's creation.
    $container.on("keydown", "#create_user_group_description", (e) => {
        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
        }
    });

    // This will always be enabled when creating a user group.
    settings_components.enable_opening_typeahead_on_clicking_label($container);

    can_add_members_group_widget = settings_components.create_group_setting_widget({
        $pill_container: $("#id_new_group_can_add_members_group"),
        setting_name: "can_add_members_group",
    });

    can_manage_group_widget = settings_components.create_group_setting_widget({
        $pill_container: $("#id_new_group_can_manage_group"),
        setting_name: "can_manage_group",
    });

    can_join_group_widget = settings_components.create_group_setting_widget({
        $pill_container: $("#id_new_group_can_join_group"),
        setting_name: "can_join_group",
    });

    can_leave_group_widget = settings_components.create_group_setting_widget({
        $pill_container: $("#id_new_group_can_leave_group"),
        setting_name: "can_leave_group",
    });

    can_mention_group_widget = settings_components.create_group_setting_widget({
        $pill_container: $("#id_new_group_can_mention_group"),
        setting_name: "can_mention_group",
    });
}
