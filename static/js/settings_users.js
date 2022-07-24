import $ from "jquery";

import render_settings_deactivation_user_modal from "../templates/confirm_dialog/confirm_deactivate_user.hbs";
import render_settings_reactivation_user_modal from "../templates/confirm_dialog/confirm_reactivate_user.hbs";
import render_admin_human_form from "../templates/settings/admin_human_form.hbs";
import render_admin_user_list from "../templates/settings/admin_user_list.hbs";

import * as blueslip from "./blueslip";
import * as bot_data from "./bot_data";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
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
import * as timerender from "./timerender";
import * as ui from "./ui";
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

function sort_user_id(a, b) {
    return compare_a_b(a.user_id, b.user_id);
}

function get_user_info_row(user_id) {
    return $(`tr.user_row[data-user-id='${CSS.escape(user_id)}']`);
}

export function update_view_on_deactivate(user_id) {
    const $row = get_user_info_row(user_id);
    if ($row.length === 0) {
        return;
    }

    const $button = $row.find("button.deactivate");
    const $user_role = $row.find(".user_role");
    $button.prop("disabled", false);
    $row.find("button.open-user-form").hide();
    $row.find("i.deactivated-user-icon").show();
    $button.addClass("btn-warning reactivate");
    $button.removeClass("deactivate btn-danger");
    $button.empty().append($("<i>", {class: "fa fa-user-plus", ["aria-hidden"]: "true"}));
    $button.attr("title", "Reactivate");
    $row.addClass("deactivated_user");

    if ($user_role) {
        const user_id = $row.data("user-id");
        $user_role.text(
            `${$t({defaultMessage: "Deactivated"})} (${people.get_user_type(user_id)})`,
        );
    }
}

function update_view_on_reactivate($row) {
    const $button = $row.find("button.reactivate");
    const $user_role = $row.find(".user_role");
    $row.find("button.open-user-form").show();
    $row.find("i.deactivated-user-icon").hide();
    $button.addClass("btn-danger deactivate");
    $button.removeClass("btn-warning reactivate");
    $button.attr("title", "Deactivate");
    $button.empty().append($("<i>", {class: "fa fa-user-times", ["aria-hidden"]: "true"}));
    $row.removeClass("deactivated_user");

    if ($user_role) {
        const user_id = $row.data("user-id");
        $user_role.text(people.get_user_type(user_id));
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
    info.role = people.get_by_user_id(bot_user_id).role;
    info.is_active = bot_user.is_active;
    info.user_id = bot_user.user_id;
    info.full_name = bot_user.full_name;
    info.bot_owner_id = owner_id;
    info.user_role_text = people.get_user_type(bot_user_id);

    // Convert bot type id to string for viewing to the users.
    info.bot_type = settings_bots.type_id_to_string(bot_user.bot_type);

    info.bot_owner_full_name = bot_owner_full_name(owner_id);

    if (!info.bot_owner_full_name) {
        info.no_owner = true;
        info.bot_owner_full_name = $t({defaultMessage: "No owner"});
    }

    info.is_current_user = false;
    info.can_modify = page_params.is_admin;

    // It's always safe to show the real email addresses for bot users
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
            $element: $bots_table.closest(".settings-section").find(".search"),
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
        $parent_container: $("#admin-bot-list").expectOne(),
        init_sort: ["alphabetic", "full_name"],
        sort_fields: {
            email: sort_bot_email,
            bot_owner: sort_bot_owner,
            role: sort_role,
        },
        $simplebar_container: $("#admin-bot-list .progressive-table-wrapper"),
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
            $element: $users_table.closest(".settings-section").find(".search"),
            filterer: people.filter_for_user_settings_search,
            onupdate: reset_scrollbar($users_table),
        },
        $parent_container: $("#admin-user-list").expectOne(),
        init_sort: ["alphabetic", "full_name"],
        sort_fields: {
            email: sort_email,
            last_active: sort_last_active,
            role: sort_role,
            id: sort_user_id,
        },
        $simplebar_container: $("#admin-user-list .progressive-table-wrapper"),
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
            $element: $deactivated_users_table.closest(".settings-section").find(".search"),
            filterer: people.filter_for_user_settings_search,
            onupdate: reset_scrollbar($deactivated_users_table),
        },
        $parent_container: $("#admin-deactivated-users-list").expectOne(),
        init_sort: ["alphabetic", "full_name"],
        sort_fields: {
            email: sort_email,
            role: sort_role,
            id: sort_user_id,
        },
        $simplebar_container: $("#admin-deactivated-users-list .progressive-table-wrapper"),
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
    const $user_row = get_user_info_row(user_id);

    if ($user_row.length === 0) {
        return;
    }

    if (new_data.full_name !== undefined) {
        // Update the full name in the table
        $user_row.find(".user_name").text(new_data.full_name);
    }

    if (new_data.role !== undefined) {
        $user_row.find(".user_role").text(people.get_user_type(user_id));
    }
}

export function redraw_bots_list() {
    if (!bot_list_widget) {
        return;
    }

    bot_list_widget.hard_redraw();
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
        // Remove duplicate datepicker input element generated flatpickr library
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

export function confirm_deactivation(user_id, handle_confirm, loading_spinner) {
    // Knowing the number of invites requires making this request. If the request fails,
    // we won't have the accurate number of invites. So, we don't show the modal if the
    // request fails.
    channel.get({
        url: "/json/invites",
        idempotent: true,
        timeout: 10 * 1000,
        success(data) {
            let number_of_invites_by_user = 0;
            for (const invite of data.invites) {
                if (invite.invited_by_user_id === user_id) {
                    number_of_invites_by_user = number_of_invites_by_user + 1;
                }
            }

            const bots_owned_by_user = bot_data.get_all_bots_owned_by_user(user_id);
            const user = people.get_by_user_id(user_id);
            const opts = {
                username: user.full_name,
                email: settings_data.email_for_user_settings(user),
                bots_owned_by_user,
                number_of_invites_by_user,
            };
            const html_body = render_settings_deactivation_user_modal(opts);

            dialog_widget.launch({
                html_heading: $t_html(
                    {defaultMessage: "Deactivate {name}?"},
                    {name: user.full_name},
                ),
                help_link: "/help/deactivate-or-reactivate-a-user#deactivate-ban-a-user",
                html_body,
                html_submit_button: $t_html({defaultMessage: "Deactivate"}),
                id: "deactivate-user-modal",
                on_click: handle_confirm,
                loading_spinner,
            });
        },
    });
}

function handle_deactivation($tbody) {
    $tbody.on("click", ".deactivate", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active_modal` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        const $row = $(e.target).closest(".user_row");
        const user_id = $row.data("user-id");

        function handle_confirm() {
            const url = "/json/users/" + encodeURIComponent(user_id);
            dialog_widget.submit_api_request(channel.del, url);
        }

        confirm_deactivation(user_id, handle_confirm, true);
    });
}

function handle_bot_deactivation($tbody) {
    $tbody.on("click", ".deactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const $button_elem = $(e.target);
        const $row = $button_elem.closest(".user_row");
        const bot_id = Number.parseInt($row.attr("data-user-id"), 10);

        function handle_confirm() {
            const url = "/json/bots/" + encodeURIComponent(bot_id);
            dialog_widget.submit_api_request(channel.del, url);
        }

        settings_bots.confirm_bot_deactivation(bot_id, handle_confirm, true);
    });
}

export function confirm_reactivation(user_id, handle_confirm, loading_spinner) {
    const user = people.get_by_user_id(user_id);
    const opts = {
        username: user.full_name,
    };
    const html_body = render_settings_reactivation_user_modal(opts);

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Reactivate {name}"}, {name: user.full_name}),
        help_link: "/help/deactivate-or-reactivate-a-user#reactivate-a-user",
        html_body,
        on_click: handle_confirm,
        loading_spinner,
    });
}

function handle_reactivation($tbody) {
    $tbody.on("click", ".reactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();
        // Go up the tree until we find the user row, then grab the email element
        const $button_elem = $(e.target);
        const $row = $button_elem.closest(".user_row");
        const user_id = Number.parseInt($row.attr("data-user-id"), 10);

        function handle_confirm() {
            const $row = get_user_info_row(user_id);
            const url = "/json/users/" + encodeURIComponent(user_id) + "/reactivate";
            const opts = {
                success_continuation() {
                    update_view_on_reactivate($row);
                },
            };
            dialog_widget.submit_api_request(channel.post, url, {}, opts);
        }

        confirm_reactivation(user_id, handle_confirm, true);
    });
}

export function show_edit_user_info_modal(user_id, from_user_info_popover) {
    const person = people.get_by_user_id(user_id);

    if (!person) {
        return;
    }

    const user_email = settings_data.email_for_user_settings(person);

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
                .find(`option[value="${CSS.escape(settings_config.user_role_values.owner.code)}"]`)
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

        $("#edit-user-form").on("click", ".deactivate_user_button", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const user_id = $("#edit-user-form").data("user-id");
            function handle_confirm() {
                const url = "/json/users/" + encodeURIComponent(user_id);
                dialog_widget.submit_api_request(channel.del, url);
            }
            const open_deactivate_modal_callback = () =>
                confirm_deactivation(user_id, handle_confirm, true);
            dialog_widget.close_modal(open_deactivate_modal_callback);
        });
    }

    function submit_user_details() {
        const role = Number.parseInt($("#user-role-select").val().trim(), 10);
        const $full_name = $("#edit-user-form").find("input[name='full_name']");
        const profile_data = get_human_profile_data(fields_user_pills);

        const url = "/json/users/" + encodeURIComponent(user_id);
        const data = {
            full_name: $full_name.val(),
            role: JSON.stringify(role),
            profile_data: JSON.stringify(profile_data),
        };
        const opts = {
            error_continuation() {
                // Scrolling modal to top, to make error visible to user.
                $("#edit-user-form")
                    .closest(".simplebar-content-wrapper")
                    .animate({scrollTop: 0}, "fast");
            },
        };
        dialog_widget.submit_api_request(channel.patch, url, data, opts);
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Manage user"}),
        html_body,
        on_click: submit_user_details,
        post_render: set_role_dropdown_and_fields_user_pills,
        loading_spinner: from_user_info_popover,
    });
}

function handle_human_form($tbody) {
    $tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        show_edit_user_info_modal(user_id, false);
    });
}

function handle_bot_form($tbody) {
    $tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        settings_bots.show_edit_bot_info_modal(user_id, false);
    });
}

section.active.handle_events = () => {
    const $tbody = $("#admin_users_table").expectOne();

    handle_deactivation($tbody);
    handle_reactivation($tbody);
    handle_human_form($tbody);
};

section.deactivated.handle_events = () => {
    const $tbody = $("#admin_deactivated_users_table").expectOne();

    handle_deactivation($tbody);
    handle_reactivation($tbody);
    handle_human_form($tbody);
};

section.bots.handle_events = () => {
    const $tbody = $("#admin_bots_table").expectOne();

    handle_bot_deactivation($tbody);
    handle_reactivation($tbody);
    handle_bot_form($tbody);
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
