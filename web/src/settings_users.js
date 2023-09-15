import $ from "jquery";

import render_settings_deactivation_user_modal from "../templates/confirm_dialog/confirm_deactivate_user.hbs";
import render_settings_reactivation_bot_modal from "../templates/confirm_dialog/confirm_reactivate_bot.hbs";
import render_settings_reactivation_user_modal from "../templates/confirm_dialog/confirm_reactivate_user.hbs";
import render_admin_human_form from "../templates/settings/admin_human_form.hbs";
import render_admin_user_list from "../templates/settings/admin_user_list.hbs";

import * as blueslip from "./blueslip";
import * as bot_data from "./bot_data";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import * as presence from "./presence";
import * as scroll_util from "./scroll_util";
import * as settings_account from "./settings_account";
import * as settings_bots from "./settings_bots";
import * as settings_config from "./settings_config";
import * as settings_panel_menu from "./settings_panel_menu";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as user_pill from "./user_pill";
import * as user_profile from "./user_profile";

const section = {
    active: {},
    deactivated: {},
    bots: {},
};

export function show_button_spinner($button) {
    const $spinner = $button.find(".modal__spinner");
    const dialog_submit_button_span_width = $button.find("span").width();
    const dialog_submit_button_span_height = $button.find("span").height();
    $button.prop("disabled", true);
    $button.find("span").hide();
    loading.make_indicator($spinner, {
        width: dialog_submit_button_span_width,
        height: dialog_submit_button_span_height,
    });
}

export function hide_button_spinner($button) {
    const $spinner = $button.find(".modal__spinner");
    $button.prop("disabled", false);
    $button.find("span").show();
    loading.destroy_indicator($spinner);
}

function compare_a_b(a, b) {
    if (a > b) {
        return 1;
    } else if (a === b) {
        return 0;
    }
    return -1;
}

export function sort_email(a, b) {
    const email_a = a.delivery_email;
    const email_b = b.delivery_email;

    if (email_a === null && email_b === null) {
        // If both the emails are hidden, we sort the list by name.
        return compare_a_b(a.full_name.toLowerCase(), b.full_name.toLowerCase());
    }

    if (email_a === null) {
        // User with hidden should be at last.
        return 1;
    }
    if (email_b === null) {
        // User with hidden should be at last.
        return -1;
    }
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

export function sort_user_id(a, b) {
    return compare_a_b(a.user_id, b.user_id);
}

function get_user_info_row(user_id) {
    return $(`tr.user_row[data-user-id='${CSS.escape(user_id)}']`);
}

export function allow_sorting_deactivated_users_list_by_email() {
    const deactivated_users = people.get_non_active_realm_users();
    const deactivated_humans_with_visible_email = deactivated_users.filter(
        (user) => !user.is_bot && user.delivery_email,
    );

    return deactivated_humans_with_visible_email.length !== 0;
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
    $button.empty().append($("<i>").addClass(["fa", "fa-user-plus"]).attr("aria-hidden", "true"));
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
    $button.empty().append($("<i>").addClass(["fa", "fa-user-times"]).attr("aria-hidden", "true"));
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
    blueslip.error("Error while listing users for user_id", {user_id, status});
}

function populate_users() {
    const active_user_ids = people.get_realm_active_human_user_ids();
    const deactivated_user_ids = people.get_non_active_human_ids();

    if (active_user_ids.length === 0 && deactivated_user_ids.length === 0) {
        failed_listing_users();
    }

    section.active.create_table(active_user_ids);
    section.deactivated.create_table(deactivated_user_ids);
}

function reset_scrollbar($sel) {
    return function () {
        scroll_util.reset_scrollbar($sel);
    };
}

function bot_owner_full_name(owner_id) {
    if (!owner_id) {
        return undefined;
    }

    const bot_owner = people.maybe_get_user_by_id(owner_id);
    if (!bot_owner) {
        return undefined;
    }

    return bot_owner.full_name;
}

function bot_info(bot_user_id) {
    const bot_user = people.maybe_get_user_by_id(bot_user_id);

    if (!bot_user) {
        return undefined;
    }

    const owner_id = bot_user.bot_owner_id;

    const info = {};

    info.is_bot = true;
    info.role = bot_user.role;
    info.is_active = people.is_person_active(bot_user.user_id);
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
    info.cannot_deactivate = bot_user.is_system_bot;
    info.cannot_edit = bot_user.is_system_bot;

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
    info.display_email = person.delivery_email;

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
    loading.make_indicator($("#admin_page_bots_loading_indicator"), {
        text: $t({defaultMessage: "Loading…"}),
    });
    const $bots_table = $("#admin_bots_table");
    $bots_table.hide();
    const bot_user_ids = people.get_bot_ids();

    bot_list_widget = ListWidget.create($bots_table, bot_user_ids, {
        name: "admin_bot_list",
        get_item: bot_info,
        modifier_html: render_admin_user_list,
        html_selector: (item) => $(`tr[data-user-id='${CSS.escape(item.user_id)}']`),
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
        init_sort: "full_name_alphabetic",
        sort_fields: {
            email: sort_bot_email,
            bot_owner: sort_bot_owner,
            role: sort_role,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name", "bot_type"]),
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
        modifier_html(item) {
            const info = human_info(item);
            return render_admin_user_list(info);
        },
        filter: {
            $element: $users_table.closest(".settings-section").find(".search"),
            filterer: people.filter_for_user_settings_search,
            onupdate: reset_scrollbar($users_table),
        },
        $parent_container: $("#admin-user-list").expectOne(),
        init_sort: "full_name_alphabetic",
        sort_fields: {
            email: sort_email,
            last_active: sort_last_active,
            role: sort_role,
            id: sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
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
        modifier_html(item) {
            const info = human_info(item);
            return render_admin_user_list(info);
        },
        filter: {
            $element: $deactivated_users_table.closest(".settings-section").find(".search"),
            filterer: people.filter_for_user_settings_search,
            onupdate: reset_scrollbar($deactivated_users_table),
        },
        $parent_container: $("#admin-deactivated-users-list").expectOne(),
        init_sort: "full_name_alphabetic",
        sort_fields: {
            email: sort_email,
            role: sort_role,
            id: sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
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

    bot_list_widget.render_item(bot_info(bot_user_id));
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

    // In order to properly redraw after a user may have been added,
    // we need to update the bot_list_widget with the new set of bot
    // user IDs to display.
    const bot_user_ids = people.get_bot_ids();
    bot_list_widget.replace_list_data(bot_user_ids);
    bot_list_widget.hard_redraw();
}

function start_data_load() {
    loading.make_indicator($("#admin_page_users_loading_indicator"), {
        text: $t({defaultMessage: "Loading…"}),
    });
    loading.make_indicator($("#admin_page_deactivated_users_loading_indicator"), {
        text: $t({defaultMessage: "Loading…"}),
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
            const realm_url = page_params.realm_uri;
            const realm_name = page_params.realm_name;
            const opts = {
                username: user.full_name,
                email: user.delivery_email,
                bots_owned_by_user,
                number_of_invites_by_user,
                admin_email: people.my_current_email(),
                realm_url,
                realm_name,
            };
            const html_body = render_settings_deactivation_user_modal(opts);

            function set_email_field_visibility() {
                const $send_email_checkbox = $("#dialog_widget_modal").find(".send_email");
                const $email_field = $("#dialog_widget_modal").find(".email_field");

                $email_field.hide();
                $send_email_checkbox.on("change", () => {
                    if ($send_email_checkbox.is(":checked")) {
                        $email_field.show();
                    } else {
                        $email_field.hide();
                    }
                });
            }

            dialog_widget.launch({
                html_heading: $t_html(
                    {defaultMessage: "Deactivate {name}?"},
                    {name: user.full_name},
                ),
                help_link: "/help/deactivate-or-reactivate-a-user#deactivating-a-user",
                html_body,
                html_submit_button: $t_html({defaultMessage: "Deactivate"}),
                id: "deactivate-user-modal",
                on_click: handle_confirm,
                post_render: set_email_field_visibility,
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
        popovers.hide_all();

        const $row = $(e.target).closest(".user_row");
        const user_id = $row.data("user-id");

        function handle_confirm() {
            const url = "/json/users/" + encodeURIComponent(user_id);
            let data = {};
            if ($(".send_email").is(":checked")) {
                data = {
                    deactivation_notification_comment: $(".email_field_textarea").val(),
                };
            }

            dialog_widget.submit_api_request(channel.del, url, data);
        }

        confirm_deactivation(user_id, handle_confirm, true);
    });
}

function handle_bot_deactivation($tbody) {
    $tbody.on("click", ".deactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();
        popovers.hide_all();

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

    let html_body;
    // check if bot or human
    if (user.is_bot) {
        opts.original_owner_deactivated =
            user.is_bot && user.bot_owner_id && !people.is_person_active(user.bot_owner_id);
        if (opts.original_owner_deactivated) {
            opts.owner_name = people.get_by_user_id(user.bot_owner_id).full_name;
        }
        html_body = render_settings_reactivation_bot_modal(opts);
    } else {
        html_body = render_settings_reactivation_user_modal(opts);
    }

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Reactivate {name}"}, {name: user.full_name}),
        help_link: "/help/deactivate-or-reactivate-a-user#reactivating-a-user",
        html_body,
        on_click: handle_confirm,
        loading_spinner,
    });
}

function handle_reactivation($tbody) {
    $tbody.on("click", ".reactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();
        popovers.hide_all();

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

export function show_edit_user_info_modal(user_id, $container) {
    const person = people.maybe_get_user_by_id(user_id);

    if (!person) {
        return;
    }

    const html_body = render_admin_human_form({
        user_id,
        email: person.delivery_email,
        full_name: person.full_name,
        user_role_values: settings_config.user_role_values,
        disable_role_dropdown: person.is_owner && !page_params.is_owner,
        owner_is_only_user_in_organization: people.get_active_human_count() === 1,
    });

    $container.append(html_body);
    // Set role dropdown and fields user pills
    $("#user-role-select").val(person.role);
    if (!page_params.is_owner) {
        $("#user-role-select")
            .find(`option[value="${CSS.escape(settings_config.user_role_values.owner.code)}"]`)
            .hide();
    }

    const custom_profile_field_form_selector = "#edit-user-form .custom-profile-field-form";
    $(custom_profile_field_form_selector).empty();
    settings_account.append_custom_profile_fields(custom_profile_field_form_selector, user_id);
    settings_account.initialize_custom_date_type_fields(custom_profile_field_form_selector);
    settings_account.initialize_custom_pronouns_type_fields(custom_profile_field_form_selector);
    const fields_user_pills = settings_account.initialize_custom_user_type_fields(
        custom_profile_field_form_selector,
        user_id,
        true,
        false,
    );

    // Handle deactivation
    $("#edit-user-form").on("click", ".deactivate_user_button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const user_id = $("#edit-user-form").data("user-id");
        function handle_confirm() {
            const url = "/json/users/" + encodeURIComponent(user_id);
            dialog_widget.submit_api_request(channel.del, url);
        }
        confirm_deactivation(user_id, handle_confirm, true);
    });

    $("#user-profile-modal").on("click", ".dialog_submit_button", () => {
        const role = Number.parseInt($("#user-role-select").val().trim(), 10);
        const $full_name = $("#edit-user-form").find("input[name='full_name']");
        const profile_data = get_human_profile_data(fields_user_pills);

        const url = "/json/users/" + encodeURIComponent(user_id);
        const data = {
            full_name: $full_name.val(),
            role: JSON.stringify(role),
            profile_data: JSON.stringify(profile_data),
        };

        const $submit_btn = $("#user-profile-modal .dialog_submit_button");
        const $cancel_btn = $("#user-profile-modal .dialog_exit_button");
        show_button_spinner($submit_btn);
        $cancel_btn.prop("disabled", true);

        channel.patch({
            url,
            data,
            success() {
                user_profile.hide_user_profile();
            },
            error(xhr) {
                ui_report.error(
                    $t_html({defaultMessage: "Failed"}),
                    xhr,
                    $("#edit-user-form-error"),
                );
                // Scrolling modal to top, to make error visible to user.
                $("#edit-user-form")
                    .closest(".simplebar-content-wrapper")
                    .animate({scrollTop: 0}, "fast");
                hide_button_spinner($submit_btn);
                $cancel_btn.prop("disabled", false);
            },
        });
    });
}

function handle_edit_form($tbody) {
    $tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();
        popovers.hide_all();

        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        if (people.is_my_user_id(user_id)) {
            browser_history.go_to_location("#settings/profile");
            return;
        }

        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user, "manage-profile-tab");
    });
}

section.active.handle_events = () => {
    const $tbody = $("#admin_users_table").expectOne();

    handle_deactivation($tbody);
    handle_reactivation($tbody);
    handle_edit_form($tbody);
};

section.deactivated.handle_events = () => {
    const $tbody = $("#admin_deactivated_users_table").expectOne();

    handle_deactivation($tbody);
    handle_reactivation($tbody);
    handle_edit_form($tbody);
};

section.bots.handle_events = () => {
    const $tbody = $("#admin_bots_table").expectOne();

    handle_bot_deactivation($tbody);
    handle_reactivation($tbody);
    handle_edit_form($tbody);
};

export function set_up_humans() {
    start_data_load();
    section.active.handle_events();
    section.deactivated.handle_events();
}

export function set_up_bots() {
    section.bots.handle_events();
    section.bots.create_table();

    $("#admin-bot-list .add-a-new-bot").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        settings_bots.add_a_new_bot();
    });
}
