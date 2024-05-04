import $ from "jquery";

import render_admin_user_list from "../templates/settings/admin_user_list.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import * as dropdown_widget from "./dropdown_widget";
import {$t} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as people from "./people";
import * as presence from "./presence";
import * as scroll_util from "./scroll_util";
import * as settings_bots from "./settings_bots";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import {current_user} from "./state_data";
import * as timerender from "./timerender";
import * as user_deactivation_ui from "./user_deactivation_ui";
import * as user_profile from "./user_profile";
import * as user_sort from "./user_sort";

export const active_user_list_dropdown_widget_name = "active_user_list_select_user_role";
export const deactivated_user_list_dropdown_widget_name = "deactivated_user_list_select_user_role";

const section = {
    active: {
        dropdown_widget_name: active_user_list_dropdown_widget_name,
        filters: {
            text_search: "",
            // 0 role_code signifies All roles for our filter.
            role_code: 0,
        },
    },
    deactivated: {
        dropdown_widget_name: deactivated_user_list_dropdown_widget_name,
        filters: {
            text_search: "",
            // 0 role_code signifies All roles for our filter.
            role_code: 0,
        },
    },
    bots: {},
};

function sort_bot_email(a, b) {
    function email(bot) {
        return (bot.display_email || "").toLowerCase();
    }

    return user_sort.compare_a_b(email(a), email(b));
}

function sort_bot_owner(a, b) {
    function owner_name(bot) {
        return (bot.bot_owner_full_name || "").toLowerCase();
    }

    return user_sort.compare_a_b(owner_name(a), owner_name(b));
}

function sort_last_active(a, b) {
    return user_sort.compare_a_b(
        presence.last_active_date(a.user_id) || 0,
        presence.last_active_date(b.user_id) || 0,
    );
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
    $button.prop("disabled", false);
    $row.find("i.deactivated-user-icon").show();
    $button.addClass("btn-warning reactivate");
    $button.removeClass("deactivate btn-danger");
    $button.empty().append($("<i>").addClass(["fa", "fa-user-plus"]).attr("aria-hidden", "true"));
    $row.removeClass("reactivated_user");
    $row.addClass("deactivated_user");
}

function update_view_on_reactivate($row) {
    const $button = $row.find("button.reactivate");
    $row.find("i.deactivated-user-icon").hide();
    $button.addClass("btn-danger deactivate");
    $button.removeClass("btn-warning reactivate");
    $button.empty().append($("<i>").addClass(["fa", "fa-user-times"]).attr("aria-hidden", "true"));
    $row.removeClass("deactivated_user");
    $row.addClass("reactivated_user");
}

function failed_listing_users() {
    loading.destroy_indicator($("#subs_page_loading_indicator"));
    const user_id = people.my_current_user_id();
    blueslip.error("Error while listing users for user_id", {user_id});
}

function add_value_to_filters(section, key, value) {
    section.filters[key] = value;
    // This hard_redraw will rerun the relevant predicate function
    // and in turn apply the new filters.
    section.list_widget.hard_redraw();
}

function role_selected_handler(event, dropdown, widget) {
    event.preventDefault();
    event.stopPropagation();

    const role_code = Number($(event.currentTarget).attr("data-unique-id"));
    if (widget.widget_name === section.active.dropdown_widget_name) {
        add_value_to_filters(section.active, "role_code", role_code);
    } else if (widget.widget_name === section.deactivated.dropdown_widget_name) {
        add_value_to_filters(section.deactivated, "role_code", role_code);
    }

    dropdown.hide();
    widget.render();
}

function get_roles() {
    return [
        {unique_id: "0", name: $t({defaultMessage: "All roles"})},
        ...Object.values(settings_config.user_role_values)
            .map((user_role_value) => ({
                unique_id: user_role_value.code.toString(),
                name: user_role_value.description,
            }))
            .reverse(),
    ];
}

function create_role_filter_dropdown($events_container, widget_name) {
    new dropdown_widget.DropdownWidget({
        widget_name,
        get_options: get_roles,
        $events_container,
        item_click_callback: role_selected_handler,
        default_id: "0",
        tippy_props: {
            placement: "bottom-start",
            offset: [0, 0],
        },
    }).setup();
}

function populate_users() {
    const active_user_ids = people.get_realm_active_human_user_ids();
    const deactivated_user_ids = people.get_non_active_human_ids();

    if (active_user_ids.length === 0 && deactivated_user_ids.length === 0) {
        failed_listing_users();
    }

    section.active.create_table(active_user_ids);
    section.deactivated.create_table(deactivated_user_ids);
    create_role_filter_dropdown($("#admin-user-list"), section.active.dropdown_widget_name);
    create_role_filter_dropdown(
        $("#admin-deactivated-users-list"),
        section.deactivated.dropdown_widget_name,
    );
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
    info.bot_type = settings_data.bot_type_id_to_string(bot_user.bot_type);

    info.bot_owner_full_name = bot_owner_full_name(owner_id);

    if (!info.bot_owner_full_name) {
        info.no_owner = true;
        info.bot_owner_full_name = $t({defaultMessage: "No owner"});
    }

    info.is_current_user = false;
    info.can_modify = current_user.is_admin;
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

    info.can_modify = current_user.is_admin;
    info.is_current_user = people.is_my_user_id(person.user_id);
    info.cannot_deactivate = info.is_current_user || (person.is_owner && !current_user.is_owner);
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
            role: user_sort.sort_role,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name", "bot_type"]),
        },
        $simplebar_container: $("#admin-bot-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_bots_loading_indicator"));
    $bots_table.show();
};

section.active.create_table = (active_users) => {
    const $users_table = $("#admin_users_table");
    section.active.list_widget = ListWidget.create($users_table, active_users, {
        name: "users_table_list",
        get_item: people.get_by_user_id,
        modifier_html(item) {
            const info = human_info(item);
            return render_admin_user_list(info);
        },
        filter: {
            predicate(person) {
                return people.predicate_for_user_settings_filters(person, section.active.filters);
            },
            onupdate: reset_scrollbar($users_table),
        },
        $parent_container: $("#admin-user-list").expectOne(),
        init_sort: "full_name_alphabetic",
        sort_fields: {
            email: user_sort.sort_email,
            last_active: sort_last_active,
            role: user_sort.sort_role,
            id: user_sort.sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
        },
        $simplebar_container: $("#admin-user-list .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_users_loading_indicator"));
    $("#admin_users_table").show();
};

section.deactivated.create_table = (deactivated_users) => {
    const $deactivated_users_table = $("#admin_deactivated_users_table");
    section.deactivated.list_widget = ListWidget.create(
        $deactivated_users_table,
        deactivated_users,
        {
            name: "deactivated_users_table_list",
            get_item: people.get_by_user_id,
            modifier_html(item) {
                const info = human_info(item);
                return render_admin_user_list(info);
            },
            filter: {
                predicate(person) {
                    return people.predicate_for_user_settings_filters(
                        person,
                        section.deactivated.filters,
                    );
                },
                onupdate: reset_scrollbar($deactivated_users_table),
            },
            $parent_container: $("#admin-deactivated-users-list").expectOne(),
            init_sort: "full_name_alphabetic",
            sort_fields: {
                email: user_sort.sort_email,
                role: user_sort.sort_role,
                id: user_sort.sort_user_id,
                ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
            },
            $simplebar_container: $("#admin-deactivated-users-list .progressive-table-wrapper"),
        },
    );

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
        $user_row.find(".user_name .view_user_profile").text(new_data.full_name);
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

function handle_deactivation($tbody) {
    $tbody.on("click", ".deactivate", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active` in `settings.js`.
        e.preventDefault();
        e.stopPropagation();

        const $row = $(e.target).closest(".user_row");
        const user_id = Number($row.attr("data-user-id"));

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

        user_deactivation_ui.confirm_deactivation(user_id, handle_confirm, true);
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
            dialog_widget.submit_api_request(channel.del, url, {});
        }

        user_deactivation_ui.confirm_bot_deactivation(bot_id, handle_confirm, true);
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

        user_deactivation_ui.confirm_reactivation(user_id, handle_confirm, true);
    });
}

function handle_edit_form($tbody) {
    $tbody.on("click", ".open-user-form", (e) => {
        e.stopPropagation();
        e.preventDefault();

        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        if (people.is_my_user_id(user_id)) {
            browser_history.go_to_location("#settings/profile");
            return;
        }

        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user, "manage-profile-tab");
    });
}

function handle_filter_change($tbody, section) {
    // This duplicates the built-in search filter live-update logic in
    // ListWidget for the input.list_widget_filter event type, but we
    // can't use that, because we're also filtering on Role with our
    // custom predicate.
    $tbody
        .closest(".settings-section")
        .find(".search")
        .on("input.list_widget_filter", function () {
            add_value_to_filters(section, "text_search", this.value.toLocaleLowerCase());
        });
}

section.active.handle_events = () => {
    const $tbody = $("#admin_users_table").expectOne();

    handle_filter_change($tbody, section.active);
    handle_deactivation($tbody);
    handle_reactivation($tbody);
    handle_edit_form($tbody);
};

section.deactivated.handle_events = () => {
    const $tbody = $("#admin_deactivated_users_table").expectOne();

    handle_filter_change($tbody, section.deactivated);
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
