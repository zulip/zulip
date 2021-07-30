import $ from "jquery";

import render_settings_deactivation_user_modal from "../templates/confirm_dialog/confirm_deactivate_user.hbs";
import render_admin_bot_form from "../templates/settings/admin_bot_form.hbs";
import render_admin_human_form from "../templates/settings/admin_human_form.hbs";
import render_admin_user_list from "../templates/settings/admin_user_list.hbs";

import * as blueslip from "./blueslip";
import * as bot_data from "./bot_data";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import {DropdownListWidget} from "./dropdown_list_widget";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as people from "./people";
import * as presence from "./presence";
import * as settings_account from "./settings_account";
import * as settings_bots from "./settings_bots";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_ui from "./settings_ui";
import * as timerender from "./timerender";
import * as ui from "./ui";
import * as ui_report from "./ui_report";
import * as user_pill from "./user_pill";

const section = {
    active: {},
    deactivated: {},
    bots: {},
};

function compare_a_b(a, b) {
    if (a > b) {
        return 1;
    } else if (a === b) {
        return 0;
    }
    return -1;
}

function sort_email(a, b) {
    const email_a = settings_data.email_for_user_settings(a) || "";
    const email_b = settings_data.email_for_user_settings(b) || "";
    return compare_a_b(email_a.toLowerCase(), email_b.toLowerCase());
}

function sort_bot_email(a, b) {
    function email(bot) {
        return (bot.display_email || "").toLowerCase();
    }

    return compare_a_b(email(a), email(b));
}

function sort_role(a, b) {
    return compare_a_b(a.role, b.role);
}

function sort_bot_owner(a, b) {
    function owner_name(bot) {
        return (bot.bot_owner_full_name || "").toLowerCase();
    }

    return compare_a_b(owner_name(a), owner_name(b));
}

function sort_last_active(a, b) {
    return compare_a_b(
        presence.last_active_date(a.user_id) || 0,
        presence.last_active_date(b.user_id) || 0,
    );
}

function get_user_info_row(user_id) {
    return $(`tr.user_row[data-user-id='${CSS.escape(user_id)}']`);
}

function update_view_on_deactivate(row) {
    const button = row.find("button.deactivate");
    const user_role = row.find(".user_role");
    button.prop("disabled", false);
    row.find("button.open-user-form").hide();
    row.find("i.deactivated-user-icon").show();
    button.addClass("btn-warning reactivate");
    button.removeClass("deactivate btn-danger");
    button.html("<i class='fa fa-user-plus' aria-hidden='true'></i>");
    button.attr("title", "Reactivate");
    row.addClass("deactivated_user");

    if (user_role) {
        const user_id = row.data("user-id");
        user_role.text(
            "%state (%role)"
                .replace("%state", $t({defaultMessage: "Deactivated"}))
                .replace("%role", people.get_user_type(user_id)),
        );
    }
}

function update_view_on_reactivate(row) {
    const button = row.find("button.reactivate");
    const user_role = row.find(".user_role");
    row.find("button.open-user-form").show();
    row.find("i.deactivated-user-icon").hide();
    button.addClass("btn-danger deactivate");
    button.removeClass("btn-warning reactivate");
    button.attr("title", "Deactivate");
    button.html('<i class="fa fa-user-times" aria-hidden="true"></i>');
    row.removeClass("deactivated_user");

    if (user_role) {
        const user_id = row.data("user-id");
        user_role.text(people.get_user_type(user_id));
    }
}

function get_status_field() {
    const current_tab = settings_panel_menu.org_settings.current_tab();
    switch (current_tab) {
        case "deactivated-users-admin":
            return $("#deactivated-user-field-status").expectOne();
        case "user-list-admin":
            return $("#user-field-status").expectOne();
        case "bot-list-admin":
            return $("#bot-field-status").expectOne();
        default:
            throw new Error("Invalid admin settings page");
    }
}

function failed_listing_users() {
    loading.destroy_indicator($("#subs_page_loading_indicator"));
    const status = get_status_field();
    const user_id = people.my_current_user_id();
    blueslip.error("Error while listing users for user_id " + user_id, status);
}

function populate_users() {
    const active_user_ids = people.get_active_human_ids();
    const deactivated_user_ids = people.get_non_active_human_ids();

    if (active_user_ids.length === 0 && deactivated_user_ids.length === 0) {
        failed_listing_users();
    }

    section.active.create_table(active_user_ids);
    section.deactivated.create_table(deactivated_user_ids);
}

function reset_scrollbar($sel) {
    return function () {
        ui.reset_scrollbar($sel);
    };
}

function bot_owner_full_name(owner_id) {
    if (!owner_id) {
        return undefined;
    }

    const bot_owner = people.get_by_user_id(owner_id);
    if (!bot_owner) {
        return undefined;
    }

    return bot_owner.full_name;
}

function bot_info(bot_user_id) {
    const bot_user = bot_data.get(bot_user_id);

    if (!bot_user) {
        return undefined;
    }

    const owner_id = bot_user.owner_id;

    const info = {};

    info.is_bot = true;
    info.is_active = bot_user.is_active;
    info.user_id = bot_user.user_id;
    info.full_name = bot_user.full_name;
    info.bot_owner_id = owner_id;

    // Convert bot type id to string for viewing to the users.
    info.bot_type = settings_bots.type_id_to_string(bot_user.bot_type);

    info.bot_owner_full_name = bot_owner_full_name(owner_id);

    if (!info.bot_owner_full_name) {
        info.no_owner = true;
        info.bot_owner_full_name = $t({defaultMessage: "No owner"});
    }

    info.is_current_user = false;
    info.can_modify = page_params.is_admin;

    // It's always safe to show the fake email addresses for bot users
    info.display_email = bot_user.email;

    return info;
}

function get_last_active(user) {
    const last_active_date = presence.last_active_date(user.user_id);

    if (!last_active_date) {
        return $t({defaultMessage: "Unknown"});
    }
    return timerender.render_now(last_active_date).time_str;
}

function human_info(person) {
    const info = {};

    info.is_bot = false;
    info.user_role_text = people.get_user_type(person.user_id);
    info.is_active = people.is_person_active(person.user_id);
    info.user_id = person.user_id;
    info.full_name = person.full_name;
    info.bot_owner_id = person.bot_owner_id;

    info.can_modify = page_params.is_admin;
    info.is_current_user = people.is_my_user_id(person.user_id);
    info.cannot_deactivate = info.is_current_user || (person.is_owner && !page_params.is_owner);
    info.display_email = settings_data.email_for_user_settings(person);

    if (info.is_active) {
        // TODO: We might just want to show this
        // for deactivated users, too, even though
        // it might usually just be undefined.
        info.last_active_date = get_last_active(person);
    }

    return info;
}

let bot_list_widget;

section.bots.create_table = () => {
    loading.make_indicator($("#admin_page_bots_loading_indicator"), {text: "Loading..."});
    const $bots_table = $("#admin_bots_table");
    $bots_table.hide();
    const bot_user_ids = bot_data.all_user_ids();

    bot_list_widget = ListWidget.create($bots_table, bot_user_ids, {
        name: "admin_bot_list",
        get_item: bot_info,
        modifier: render_admin_user_list,
        html_selector: (item) => `tr[data-user-id='${CSS.escape(item)}']`,
        filter: {
            element: $bots_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                if (!item) {
                    return false;
                }
                return (
                    item.full_name.toLowerCase().includes(value) ||
                    item.display_email.toLowerCase().includes(value)
                );
            },
            onupdate: reset_scrollbar($bots_table),
        },
        parent_container: $("#admin-bot-list").expectOne(),
        init_sort: ["alphabetic", "full_name"],
        sort_fields: {
            email: sort_bot_email,
            bot_owner: sort_bot_owner,
        },
        simplebar_container: $("#admin-bot-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_bots_loading_indicator"));
    $bots_table.show();
};

section.active.create_table = (active_users) => {
    const $users_table = $("#admin_users_table");
    ListWidget.create($users_table, active_users, {
        name: "users_table_list",
        get_item: people.get_by_user_id,
        modifier(item) {
            const info = human_info(item);
            return render_admin_user_list(info);
        },
        filter: {
            element: $users_table.closest(".settings-section").find(".search"),
            filterer: people.filter_for_user_settings_search,
            onupdate: reset_scrollbar($users_table),
        },
        parent_container: $("#admin-user-list").expectOne(),
        init_sort: ["alphabetic", "full_name"],
        sort_fields: {
            email: sort_email,
            last_active: sort_last_active,
            role: sort_role,
        },
        simplebar_container: $("#admin-user-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_users_loading_indicator"));
    $("#admin_users_table").show();
};

section.deactivated.create_table = (deactivated_users) => {
    const $deactivated_users_table = $("#admin_deactivated_users_table");
    ListWidget.create($deactivated_users_table, deactivated_users, {
        name: "deactivated_users_table_list",
        get_item: people.get_by_user_id,
        modifier(item) {
            const info = human_info(item);
            return render_admin_user_list(info);
        },
        filter: {
            element: $deactivated_users_table.closest(".settings-section").find(".search"),
            filterer: people.filter_for_user_settings_search,
            onupdate: reset_scrollbar($deactivated_users_table),
        },
        parent_container: $("#admin-deactivated-users-list").expectOne(),
        init_sort: ["alphabetic", "full_name"],
        sort_fields: {
            email: sort_email,
            role: sort_role,
        },
        simplebar_container: $("#admin-deactivated-users-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_deactivated_users_loading_indicator"));
    $("#admin_deactivated_users_table").show();
};

export function update_bot_data(bot_user_id) {
    if (!bot_list_widget) {
        return;
    }

    bot_list_widget.render_item(bot_user_id);
}

export function update_user_data(user_id, new_data) {
    const user_row = get_user_info_row(user_id);

    if (user_row.length === 0) {
        return;
    }

    if (new_data.full_name !== undefined) {
        // Update the full name in the table
        user_row.find(".user_name").text(new_data.full_name);
    }

    if (new_data.is_active !== undefined) {
        if (new_data.is_active === false) {
            // Deactivate the user/bot in the table
            update_view_on_deactivate(user_row);
        } else {
            // Reactivate the user/bot in the table
            update_view_on_reactivate(user_row);
        }
    }

    if (new_data.role !== undefined) {
        user_row.find(".user_role").text(people.get_user_type(user_id));
    }
}

function start_data_load() {
    loading.make_indicator($("#admin_page_users_loading_indicator"), {text: "Loading..."});
    loading.make_indicator($("#admin_page_deactivated_users_loading_indicator"), {
        text: "Loading...",
    });
    $("#admin_deactivated_users_table").hide();
    $("#admin_users_table").hide();

    populate_users();
}

function get_human_profile_data(fields_user_pills) {
    /*
        This formats custom profile field data to send to the server.
        See render_admin_human_form and open_human_form
        to see how the form is built.

        TODO: Ideally, this logic would be cleaned up or deduplicated with
        the settings_account.js logic.
    */
    const new_profile_data = [];
    $("#edit-user-form .custom_user_field_value").each(function () {
        // Remove duplicate datepicker input element generated flatpicker library
        if (!$(this).hasClass("form-control")) {
            new_profile_data.push({
                id: Number.parseInt(
                    $(this).closest(".custom_user_field").attr("data-field-id"),
                    10,
                ),
                value: $(this).val(),
            });
        }
    });
    // Append user type field values also
    for (const [field_id, field_pills] of fields_user_pills) {
        if (field_pills) {
            const user_ids = user_pill.get_user_ids(field_pills);
            new_profile_data.push({
                id: field_id,
                value: user_ids,
            });
        }
    }

    return new_profile_data;
}

function confirm_deactivation(row, user_id, status_field) {
    const user = people.get_by_user_id(user_id);
    const opts = {
        username: user.full_name,
        email: user.email,
    };
    const html_body = render_settings_deactivation_user_modal(opts);

    function handle_confirm() {
        const row = get_user_info_row(user_id);
        const row_deactivate_button = row.find("button.deactivate");
        row_deactivate_button.prop("disabled", true).text($t({defaultMessage: "Working…"}));
        const opts = {
            success_continuation() {
                update_view_on_deactivate(row);
            },
            error_continuation() {
                row_deactivate_button.text($t({defaultMessage: "Deactivate"}));
            },
        };
        const url = "/json/users/" + encodeURIComponent(user_id);
        settings_ui.do_settings_change(channel.del, url, {}, status_field, opts);
    }

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Deactivate {email}"}, {email: user.email}),
        html_body,
        on_click: handle_confirm,
    });
}

function handle_deactivation(tbody, status_field) {
    tbody.on("click", ".deactivate", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        const row = $(e.target).closest(".user_row");
        const user_id = row.data("user-id");
        confirm_deactivation(row, user_id, status_field);
    });
}

function handle_bot_deactivation(tbody, status_field) {
    tbody.on("click", ".deactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const button_elem = $(e.target);
        const row = button_elem.closest(".user_row");
        const bot_id = Number.parseInt(row.attr("data-user-id"), 10);
        const url = "/json/bots/" + encodeURIComponent(bot_id);

        const opts = {
            success_continuation() {
                update_view_on_deactivate(row);
            },
            error_continuation(xhr) {
                ui_report.generic_row_button_error(xhr, button_elem);
            },
        };
        settings_ui.do_settings_change(channel.del, url, {}, status_field, opts);
    });
}

function handle_reactivation(tbody, status_field) {
    tbody.on("click", ".reactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();
        // Go up the tree until we find the user row, then grab the email element
        const button_elem = $(e.target);
        const row = button_elem.closest(".user_row");
        const user_id = Number.parseInt(row.attr("data-user-id"), 10);
        const url = "/json/users/" + encodeURIComponent(user_id) + "/reactivate";
        const data = {};

        const opts = {
            success_continuation() {
                update_view_on_reactivate(row);
            },
            error_continuation(xhr) {
                ui_report.generic_row_button_error(xhr, button_elem);
            },
        };

        settings_ui.do_settings_change(channel.post, url, data, status_field, opts);
    });
}

function handle_human_form(tbody, status_field) {
    tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const person = people.get_by_user_id(user_id);

        if (!person) {
            return;
        }

        let user_email = settings_data.email_for_user_settings(person);
        if (!user_email) {
            // When email_address_visibility is "Nobody", we still
            // want to show the fake email address in the edit form.
            //
            // We may in the future want to just hide the form field
            // for this situation, once we display user IDs.
            user_email = person.email;
        }

        const html_body = render_admin_human_form({
            user_id,
            email: user_email,
            full_name: person.full_name,
            user_role_values: settings_config.user_role_values,
            disable_role_dropdown: person.is_owner && !page_params.is_owner,
        });

        let fields_user_pills;

        function set_role_dropdown_and_fields_user_pills() {
            $("#user-role-select").val(person.role);
            if (!page_params.is_owner) {
                $("#user-role-select")
                    .find(
                        `option[value="${CSS.escape(
                            settings_config.user_role_values.owner.code,
                        )}"]`,
                    )
                    .hide();
            }

            const element = "#edit-user-form .custom-profile-field-form";
            $(element).html("");
            settings_account.append_custom_profile_fields(element, user_id);
            settings_account.initialize_custom_date_type_fields(element);
            fields_user_pills = settings_account.initialize_custom_user_type_fields(
                element,
                user_id,
                true,
                false,
            );
        }

        function submit_user_details() {
            const role = Number.parseInt($("#user-role-select").val().trim(), 10);
            const full_name = $("#edit-user-form").find("input[name='full_name']");
            const profile_data = get_human_profile_data(fields_user_pills);

            const url = "/json/users/" + encodeURIComponent(user_id);
            const data = {
                full_name: full_name.val(),
                role: JSON.stringify(role),
                profile_data: JSON.stringify(profile_data),
            };

            settings_ui.do_settings_change(channel.patch, url, data, status_field);
            dialog_widget.close_modal();
        }

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Change user info and roles"}),
            html_body,
            on_click: submit_user_details,
            post_render: set_role_dropdown_and_fields_user_pills,
        });
    });
}

function handle_bot_form(tbody, status_field) {
    tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const bot = people.get_by_user_id(user_id);

        if (!bot) {
            return;
        }

        const html_body = render_admin_bot_form({
            user_id,
            email: bot.email,
            full_name: bot.full_name,
        });

        let owner_widget;

        function submit_bot_details() {
            const full_name = $("#dialog_widget_modal").find("input[name='full_name']");

            const url = "/json/bots/" + encodeURIComponent(user_id);
            const data = {
                full_name: full_name.val(),
            };

            if (owner_widget === undefined) {
                blueslip.error("get_bot_owner_widget not called");
            }
            const human_user_id = owner_widget.value();
            if (human_user_id) {
                data.bot_owner_id = human_user_id;
            }

            settings_ui.do_settings_change(channel.patch, url, data, status_field);
            dialog_widget.close_modal();
        }

        function get_bot_owner_widget() {
            const owner_id = bot_data.get(user_id).owner_id;

            const user_ids = people.get_active_human_ids();
            const users_list = user_ids.map((user_id) => ({
                name: people.get_full_name(user_id),
                value: user_id.toString(),
            }));

            const opts = {
                widget_name: "edit_bot_owner",
                data: users_list,
                default_text: $t({defaultMessage: "No owner"}),
                value: owner_id,
            };
            // Note: Rendering this is quite expensive in
            // organizations with 10Ks of users.
            owner_widget = new DropdownListWidget(opts);
        }

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Change bot info and owner"}),
            html_body,
            on_click: submit_bot_details,
            post_render: get_bot_owner_widget,
        });
    });
}

section.active.handle_events = () => {
    const tbody = $("#admin_users_table").expectOne();
    const status_field = $("#user-field-status").expectOne();

    handle_deactivation(tbody, status_field);
    handle_reactivation(tbody, status_field);
    handle_human_form(tbody, status_field);
};

section.deactivated.handle_events = () => {
    const tbody = $("#admin_deactivated_users_table").expectOne();
    const status_field = $("#deactivated-user-field-status").expectOne();

    handle_deactivation(tbody, status_field);
    handle_reactivation(tbody, status_field);
    handle_human_form(tbody, status_field);
};

section.bots.handle_events = () => {
    const tbody = $("#admin_bots_table").expectOne();
    const status_field = $("#bot-field-status").expectOne();

    handle_bot_deactivation(tbody, status_field);
    handle_reactivation(tbody, status_field);
    handle_bot_form(tbody, status_field);
};

export function set_up_humans() {
    start_data_load();
    section.active.handle_events();
    section.deactivated.handle_events();
}

export function set_up_bots() {
    section.bots.handle_events();
    section.bots.create_table();
}
