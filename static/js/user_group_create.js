import $ from "jquery";

import * as channel from "./channel";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as loading from "./loading";
import * as ui_report from "./ui_report";
import * as user_group_create_members from "./user_group_create_members";
import * as user_group_create_members_data from "./user_group_create_members_data";
import * as user_groups from "./user_groups";
import * as user_group_settings_ui from "./user_groups_settings_ui";

let created_group_name;

export function reset_name() {
    created_group_name = undefined;
}

export function set_name(group_name) {
    created_group_name = group_name;
}

export function get_name() {
    return created_group_name;
}

class UserGroupMembershipError {
    report_no_members_to_user_group() {
        $("#user_group_membership_error").text(
            $t({defaultMessage: "You cannot create a user group with no members!"}),
        );
        $("#user_group_membership_error").show();
    }

    clear_errors() {
        $("#user_group_membership_error").hide();
    }
}
const user_group_membership_error = new UserGroupMembershipError();

class UserGroupNameError {
    report_already_exists() {
        $("#user_group_name_error").text(
            $t({defaultMessage: "A user group with this name already exists"}),
        );
        $("#user_group_name_error").show();
    }

    clear_errors() {
        $("#user_group_name_error").hide();
    }

    report_empty_user_group() {
        $("#user_group_name_error").text($t({defaultMessage: "A user group needs to have a name"}));
        $("#user_group_name_error").show();
    }

    select() {
        $("#create_user_group_name").trigger("focus").trigger("select");
    }

    pre_validate(user_group_name) {
        if (user_group_name && user_groups.get_user_group_from_name(user_group_name)) {
            this.report_already_exists();
            return;
        }

        this.clear_errors();
    }

    validate_for_submit(user_group_name) {
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

export function create_user_group_clicked() {
    // this changes the tab switcher (settings/preview) which isn't necessary
    // to a add new stream title.
    user_group_settings_ui.show_user_group_settings_pane.create_user_group();
    $(".group-row.active").removeClass("active");

    show_new_user_group_modal();
    $("#create_user_group_name").trigger("focus");
}

function clear_error_display() {
    user_group_name_error.clear_errors();
    $(".user_group_create_info").hide();
    user_group_membership_error.clear_errors();
}

export function show_new_user_group_modal() {
    $("#user-group-creation").removeClass("hide");
    $(".right .settings").hide();

    user_group_create_members.build_widgets();

    clear_error_display();
}

function create_user_group() {
    const data = {};
    const group_name = $("#create_user_group_name").val().trim();
    const description = $("#create_user_group_description").val().trim();
    set_name(group_name);

    // Even though we already check to make sure that while typing the user cannot enter
    // newline characters (by pressing the Enter key) it would still be possible to copy
    // and paste over a description with newline characters in it. Prevent that.
    if (description.includes("\n")) {
        ui_report.client_error(
            $t_html({defaultMessage: "The group description cannot contain newline characters."}),
            $(".user_group_create_info"),
        );
        return undefined;
    }
    data.name = group_name;
    data.description = description;

    const user_ids = user_group_create_members.get_principals();
    data.members = JSON.stringify(user_ids);

    loading.make_indicator($("#user_group_creating_indicator"), {
        text: $t({defaultMessage: "Creating group..."}),
    });

    return channel.post({
        url: "/json/user_groups/create",
        data,
        success() {
            $("#create_user_group_name").val("");
            $("#create_user_group_description").val("");
            user_group_create_members.clear_member_list();
            ui_report.success(
                $t_html({defaultMessage: "User group successfully created!"}),
                $(".user_group_create_info"),
            );
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

export function set_up_handlers() {
    const $people_to_add_holder = $("#people_to_add_in_group").expectOne();
    user_group_create_members.create_handlers($people_to_add_holder);

    const $container = $("#user-group-creation").expectOne();

    $container.on("click", ".finalize_create_user_group", (e) => {
        e.preventDefault();
        clear_error_display();

        const group_name = $("#create_user_group_name").val().trim();
        const name_ok = user_group_name_error.validate_for_submit(group_name);

        if (!name_ok) {
            return;
        }

        const principals = user_group_create_members_data.get_principals();
        if (principals.length === 0) {
            user_group_membership_error.report_no_members_to_user_group();
            return;
        }

        create_user_group();
    });

    $container.on("input", "#create_user_group_name", () => {
        const user_group_name = $("#create_user_group_name").val().trim();

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
}
