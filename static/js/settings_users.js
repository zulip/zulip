"use strict";

const render_admin_bot_form = require("../templates/admin_bot_form.hbs");
const render_admin_human_form = require("../templates/admin_human_form.hbs");
const render_admin_user_list = require("../templates/admin_user_list.hbs");

const people = require("./people");
const settings_config = require("./settings_config");
const settings_data = require("./settings_data");

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
    function role(user) {
        if (user.is_admin) {
            return 0;
        }
        if (user.is_guest) {
            return 2;
        }
        return 1; // member
    }
    return compare_a_b(role(a), role(b));
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
    return $("tr.user_row[data-user-id='" + user_id + "']");
}

function set_user_role_dropdown(person) {
    let role_value = settings_config.user_role_values.member.code;
    if (person.is_owner) {
        role_value = settings_config.user_role_values.owner.code;
    } else if (person.is_admin) {
        role_value = settings_config.user_role_values.admin.code;
    } else if (person.is_guest) {
        role_value = settings_config.user_role_values.guest.code;
    }
    $("#user-role-select").val(role_value);
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
                .replace("%state", i18n.t("Deactivated"))
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
            blueslip.fatal("Invalid admin settings page");
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
        return;
    }

    const bot_owner = people.get_by_user_id(owner_id);
    if (!bot_owner) {
        return;
    }

    return bot_owner.full_name;
}

function bot_info(bot_user_id) {
    const bot_user = bot_data.get(bot_user_id);

    if (!bot_user) {
        return;
    }

    const owner_id = bot_user.owner_id;

    const info = {};

    info.is_bot = true;
    info.is_admin = false;
    info.is_guest = false;
    info.is_active = bot_user.is_active;
    info.user_id = bot_user.user_id;
    info.full_name = bot_user.full_name;
    info.bot_owner_id = owner_id;

    // Convert bot type id to string for viewing to the users.
    info.bot_type = settings_bots.type_id_to_string(bot_user.bot_type);

    info.bot_owner_full_name = bot_owner_full_name(owner_id);

    if (!info.bot_owner_full_name) {
        info.no_owner = true;
        info.bot_owner_full_name = i18n.t("No owner");
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
        return i18n.t("Unknown");
    }
    return timerender.render_now(last_active_date).time_str;
}

function human_info(person) {
    const info = {};

    info.is_bot = false;
    info.is_admin = person.is_admin;
    info.is_guest = person.is_guest;
    info.is_owner = person.is_owner;
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

    bot_list_widget = list_render.create($bots_table, bot_user_ids, {
        name: "admin_bot_list",
        get_item: bot_info,
        modifier: render_admin_user_list,
        html_selector: (item) => `tr[data-user-id='${item}']`,
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
    list_render.create($users_table, active_users, {
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
    list_render.create($deactivated_users_table, deactivated_users, {
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

exports.update_bot_data = function (bot_user_id) {
    if (!bot_list_widget) {
        return;
    }

    bot_list_widget.render_item(bot_user_id);
};

exports.update_user_data = function (user_id, new_data) {
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
};

function start_data_load() {
    loading.make_indicator($("#admin_page_users_loading_indicator"), {text: "Loading..."});
    loading.make_indicator($("#admin_page_deactivated_users_loading_indicator"), {
        text: "Loading...",
    });
    $("#admin_deactivated_users_table").hide();
    $("#admin_users_table").hide();

    populate_users();
}

function open_human_form(person) {
    const user_id = person.user_id;

    const html = render_admin_human_form({
        user_id,
        email: person.email,
        full_name: person.full_name,
        user_role_values: settings_config.user_role_values,
        disable_role_dropdown: person.is_owner && !page_params.is_owner,
    });
    const div = $(html);
    const modal_container = $("#user-info-form-modal-container");
    modal_container.empty().append(div);
    overlays.open_modal("#admin-human-form");
    set_user_role_dropdown(person);
    if (!page_params.is_owner) {
        $("#user-role-select")
            .find("option[value=" + settings_config.user_role_values.owner.code + "]")
            .hide();
    }

    const element = "#admin-human-form .custom-profile-field-form";
    $(element).html("");
    settings_account.append_custom_profile_fields(element, user_id);
    settings_account.initialize_custom_date_type_fields(element);
    const pills = settings_account.initialize_custom_user_type_fields(
        element,
        user_id,
        true,
        false,
    );

    return {
        modal: div,
        fields_user_pills: pills,
    };
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
    $("#admin-human-form .custom_user_field_value").each(function () {
        // Remove duplicate datepicker input element generated flatpicker library
        if (!$(this).hasClass("form-control")) {
            new_profile_data.push({
                id: parseInt($(this).closest(".custom_user_field").attr("data-field-id"), 10),
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

function open_bot_form(person) {
    const html = render_admin_bot_form({
        user_id: person.user_id,
        email: person.email,
        full_name: person.full_name,
    });
    const div = $(html);
    const modal_container = $("#user-info-form-modal-container");
    modal_container.empty().append(div);
    overlays.open_modal("#admin-bot-form");

    // NOTE: building `owner_dropdown` is quite expensive!
    const owner_id = bot_data.get(person.user_id).owner_id;

    const user_ids = people.get_active_human_ids();
    const users_list = user_ids.map((user_id) => ({
        name: people.get_full_name(user_id),
        value: user_id.toString(),
    }));
    const opts = {
        widget_name: "edit_bot_owner",
        data: users_list,
        default_text: i18n.t("No owner"),
        value: owner_id,
    };
    const owner_widget = dropdown_list_widget(opts);

    return {
        modal: div,
        owner_widget,
    };
}

function confirm_deactivation(row, user_id, status_field) {
    const modal_elem = $("#deactivation_user_modal").expectOne();

    function set_fields() {
        const user = people.get_by_user_id(user_id);
        modal_elem.find(".email").text(user.email);
        modal_elem.find(".user_name").text(user.full_name);
    }

    function handle_confirm() {
        const row = get_user_info_row(user_id);

        modal_elem.modal("hide");
        const row_deactivate_button = row.find("button.deactivate");
        row_deactivate_button.prop("disabled", true).text(i18n.t("Working…"));
        const opts = {
            success_continuation() {
                update_view_on_deactivate(row);
            },
            error_continuation() {
                row_deactivate_button.text(i18n.t("Deactivate"));
            },
        };
        const url = "/json/users/" + encodeURIComponent(user_id);
        settings_ui.do_settings_change(channel.del, url, {}, status_field, opts);
    }

    modal_elem.modal("hide");
    modal_elem.off("click", ".do_deactivate_button");
    set_fields();
    modal_elem.on("click", ".do_deactivate_button", handle_confirm);
    modal_elem.modal("show");
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
        const bot_id = parseInt(row.attr("data-user-id"), 10);
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
        const user_id = parseInt(row.attr("data-user-id"), 10);
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

function handle_bot_owner_profile(tbody) {
    tbody.on("click", ".user_row .view_user_profile", (e) => {
        const owner_id = parseInt($(e.target).attr("data-owner-id"), 10);
        const owner = people.get_by_user_id(owner_id);
        popovers.show_user_profile(owner);
        e.stopPropagation();
        e.preventDefault();
    });
}

function handle_human_form(tbody, status_field) {
    tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const user_id = parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const person = people.get_by_user_id(user_id);

        if (!person) {
            return;
        }

        const ret = open_human_form(person);
        const modal = ret.modal;
        const fields_user_pills = ret.fields_user_pills;

        modal.find(".submit_human_change").on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();

            const role = parseInt(modal.find("#user-role-select").val().trim(), 10);
            const full_name = modal.find("input[name='full_name']");
            const profile_data = get_human_profile_data(fields_user_pills);

            const url = "/json/users/" + encodeURIComponent(user_id);
            const data = {
                full_name: JSON.stringify(full_name.val()),
                role: JSON.stringify(role),
                profile_data: JSON.stringify(profile_data),
            };

            settings_ui.do_settings_change(channel.patch, url, data, status_field);
            overlays.close_modal("#admin-human-form");
        });
    });
}

function handle_bot_form(tbody, status_field) {
    tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const user_id = parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const bot = people.get_by_user_id(user_id);

        if (!bot) {
            return;
        }

        const {modal, owner_widget} = open_bot_form(bot);

        modal.find(".submit_bot_change").on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();

            const full_name = modal.find("input[name='full_name']");

            const url = "/json/bots/" + encodeURIComponent(user_id);
            const data = {
                full_name: full_name.val(),
            };

            const human_user_id = owner_widget.value();
            if (human_user_id) {
                data.bot_owner_id = human_user_id;
            }

            settings_ui.do_settings_change(channel.patch, url, data, status_field);
            overlays.close_modal("#admin-bot-form");
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

    handle_bot_owner_profile(tbody);
    handle_bot_deactivation(tbody, status_field);
    handle_reactivation(tbody, status_field);
    handle_bot_form(tbody, status_field);
};

exports.set_up_humans = function () {
    start_data_load();
    section.active.handle_events();
    section.deactivated.handle_events();
};

exports.set_up_bots = function () {
    section.bots.handle_events();
    section.bots.create_table();
};

window.settings_users = exports;
