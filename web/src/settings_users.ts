import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_settings_user_list_row from "../templates/settings/settings_user_list_row.hbs";

import {compute_active_status, post_presence_response_schema} from "./activity.ts";
import * as browser_history from "./browser_history.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t} from "./i18n.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import * as presence from "./presence.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_bots from "./settings_bots.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as setting_invites from "./settings_invites.ts";
import {current_user} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import * as user_deactivation_ui from "./user_deactivation_ui.ts";
import * as user_profile from "./user_profile.ts";
import * as user_sort from "./user_sort.ts";
import * as util from "./util.ts";

export const active_user_list_dropdown_widget_name = "active_user_list_select_user_role";
export const deactivated_user_list_dropdown_widget_name = "deactivated_user_list_select_user_role";

let should_redraw_active_users_list = false;
let should_redraw_deactivated_users_list = false;
let presence_data_fetched = false;
let active_users_role_dropdown: dropdown_widget.DropdownWidget | undefined;
let deactivated_users_role_dropdown: dropdown_widget.DropdownWidget | undefined;

type UserSettingsSection = {
    dropdown_widget_name: string;
    filters: {
        text_search: string;
        role_code: number;
    };
    handle_events: () => void;
    create_table: (active_users: number[]) => void;
    list_widget: ListWidgetType<number, User> | undefined;
};

const active_section: UserSettingsSection = {
    dropdown_widget_name: active_user_list_dropdown_widget_name,
    filters: {
        text_search: "",
        // 0 role_code signifies All roles for our filter.
        role_code: 0,
    },
    handle_events: active_handle_events,
    create_table: active_create_table,
    list_widget: undefined,
};

const deactivated_section: UserSettingsSection = {
    dropdown_widget_name: deactivated_user_list_dropdown_widget_name,
    filters: {
        text_search: "",
        // 0 role_code signifies All roles for our filter.
        role_code: 0,
    },
    handle_events: deactivated_handle_events,
    create_table: deactivated_create_table,
    list_widget: undefined,
};

const bots_section = {
    handle_events: bots_handle_events,
    create_table: bots_create_table,
};

function sort_bot_email(a: BotInfo, b: BotInfo): number {
    function email(bot: BotInfo): string {
        return (bot.display_email ?? "").toLowerCase();
    }

    return util.compare_a_b(email(a), email(b));
}

function sort_bot_owner(a: BotInfo, b: BotInfo): number {
    function owner_name(bot: BotInfo): string {
        return (bot.bot_owner_full_name || "").toLowerCase();
    }

    return util.compare_a_b(owner_name(a), owner_name(b));
}

function sort_last_active(a: User, b: User): number {
    return util.compare_a_b(
        presence.last_active_date(a.user_id) ?? 0,
        presence.last_active_date(b.user_id) ?? 0,
    );
}

function get_user_info_row(user_id: number): JQuery {
    return $(`tr.user_row[data-user-id='${CSS.escape(user_id.toString())}']`);
}

export function allow_sorting_deactivated_users_list_by_email(): boolean {
    const deactivated_users = people.get_non_active_realm_users();
    const deactivated_humans_with_visible_email = deactivated_users.filter(
        (user) => !user.is_bot && user.delivery_email,
    );

    return deactivated_humans_with_visible_email.length > 0;
}

export function update_view_on_deactivate(user_id: number, is_bot: boolean): void {
    const $row = get_user_info_row(user_id);
    if ($row.length === 0) {
        return;
    }

    const $button = $row.find("button.deactivate");
    $button.prop("disabled", false);
    $row.find("i.deactivated-user-icon").show();
    $button.addClass("icon-button-success reactivate");
    $button.removeClass("icon-button-danger deactivate");
    if (is_bot) {
        $button.closest("span").addClass("reactivate-bot-tooltip");
        $button.closest("span").removeClass("deactivate-bot-tooltip");
    } else {
        $button.closest("span").addClass("reactivate-user-tooltip");
        $button.closest("span").removeClass("deactivate-user-tooltip");
    }
    $button
        .empty()
        .append(
            $("<i>").addClass(["zulip-icon", "zulip-icon-user-plus"]).attr("aria-hidden", "true"),
        );
    $row.removeClass("active-user");
    $row.addClass("deactivated_user");

    if (!is_bot) {
        should_redraw_active_users_list = true;
        should_redraw_deactivated_users_list = true;
        if (active_users_role_dropdown) {
            active_users_role_dropdown.render(active_section.filters.role_code);
        }
        if (deactivated_users_role_dropdown) {
            deactivated_users_role_dropdown.render(deactivated_section.filters.role_code);
        }
    }
}

export function update_view_on_reactivate(user_id: number, is_bot: boolean): void {
    const $row = get_user_info_row(user_id);
    if ($row.length === 0) {
        return;
    }

    const $button = $row.find("button.reactivate");
    $row.find("i.deactivated-user-icon").hide();
    $button.addClass("icon-button-danger deactivate");
    $button.removeClass("icon-button-success reactivate");
    if (is_bot) {
        $button.closest("span").addClass("deactivate-bot-tooltip");
        $button.closest("span").removeClass("reactivate-bot-tooltip");
    } else {
        $button.closest("span").addClass("deactivate-user-tooltip");
        $button.closest("span").removeClass("reactivate-user-tooltip");
    }
    $button
        .empty()
        .append($("<i>").addClass(["zulip-icon", "zulip-icon-user-x"]).attr("aria-hidden", "true"));
    $row.removeClass("deactivated_user");
    $row.addClass("active-user");

    if (!is_bot) {
        should_redraw_active_users_list = true;
        should_redraw_deactivated_users_list = true;
        if (active_users_role_dropdown) {
            active_users_role_dropdown.render(active_section.filters.role_code);
        }
        if (deactivated_users_role_dropdown) {
            deactivated_users_role_dropdown.render(deactivated_section.filters.role_code);
        }
    }
}

function add_value_to_filters(
    section: UserSettingsSection,
    key: "role_code" | "text_search",
    value: number | string,
): void {
    if (key === "role_code") {
        assert(typeof value === "number");
        section.filters[key] = value;
    } else {
        assert(typeof value === "string");
        section.filters[key] = value;
    }
    // This hard_redraw will rerun the relevant predicate function
    // and in turn apply the new filters.
    assert(section.list_widget !== undefined);
    section.list_widget.hard_redraw();
}

function are_filters_active(
    filters: UserSettingsSection["filters"],
    $search_input: JQuery,
): boolean {
    const search_value = String($search_input.val()).trim();
    const selected_role = filters.role_code;
    return Boolean(search_value) || selected_role !== 0;
}

function role_selected_handler(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
    widget: dropdown_widget.DropdownWidget,
): void {
    event.preventDefault();
    event.stopPropagation();

    const role_code = Number($(event.currentTarget).attr("data-unique-id"));
    if (widget.widget_name === active_section.dropdown_widget_name) {
        add_value_to_filters(active_section, "role_code", role_code);
    } else if (widget.widget_name === deactivated_section.dropdown_widget_name) {
        add_value_to_filters(deactivated_section, "role_code", role_code);
    }

    dropdown.hide();
    widget.render();
}

function count_users_by_role(user_ids: number[]): Record<number, number> {
    const role_counts: Record<number, number> = {};

    for (const user_id of user_ids) {
        const user = people.get_by_user_id(user_id);
        const role_code = user.role;

        role_counts[role_code] = (role_counts[role_code] ?? 0) + 1;
    }

    return role_counts;
}

function get_roles_with_counts(user_ids: number[]): dropdown_widget.Option[] {
    const role_counts = count_users_by_role(user_ids);
    return [
        {
            unique_id: 0,
            name: $t({defaultMessage: "All roles ({count})"}, {count: user_ids.length}),
        },
        ...Object.values(settings_config.user_role_values)
            .map((user_role_value) => ({
                unique_id: user_role_value.code,
                name: $t(
                    // This translation is a noop except for RTL languages
                    {defaultMessage: "{description} ({count})"},
                    {
                        description: user_role_value.description,
                        count: role_counts[user_role_value.code] ?? 0,
                    },
                ),
            }))
            .reverse(),
    ];
}

function get_roles_count_for_active_users(): dropdown_widget.Option[] {
    const active_user_ids = people.get_realm_active_human_user_ids();
    return get_roles_with_counts(active_user_ids);
}

function get_roles_count_for_deactivated_users(): dropdown_widget.Option[] {
    const deactivated_user_ids = people.get_non_active_human_ids();
    return get_roles_with_counts(deactivated_user_ids);
}

function create_role_filter_dropdown(
    $events_container: JQuery,
    section: UserSettingsSection,
    get_role_options: () => dropdown_widget.Option[],
): dropdown_widget.DropdownWidget {
    return new dropdown_widget.DropdownWidget({
        widget_name: section.dropdown_widget_name,
        unique_id_type: "number",
        get_options: get_role_options,
        $events_container,
        item_click_callback: role_selected_handler,
        default_id: section.filters.role_code,
        tippy_props: {
            offset: [0, 0],
        },
    });
}

function initialize_user_sections(active_user_ids: number[], deactivated_user_ids: number[]): void {
    active_section.create_table(active_user_ids);
    deactivated_section.create_table(deactivated_user_ids);
    active_users_role_dropdown = create_role_filter_dropdown(
        $("#admin-user-list"),
        active_section,
        get_roles_count_for_active_users,
    );
    deactivated_users_role_dropdown = create_role_filter_dropdown(
        $("#admin-deactivated-users-list"),
        deactivated_section,
        get_roles_count_for_deactivated_users,
    );
    active_users_role_dropdown.setup();
    deactivated_users_role_dropdown.setup();
}

function populate_users(): void {
    const active_user_ids = people.get_realm_active_human_user_ids();
    const deactivated_user_ids = people.get_non_active_human_ids();

    if (!presence_data_fetched) {
        fetch_presence_user_setting({
            render_table() {
                const active_user_ids = people.get_realm_active_human_user_ids();
                const deactivated_user_ids = people.get_non_active_human_ids();
                presence_data_fetched = true;
                initialize_user_sections(active_user_ids, deactivated_user_ids);
            },
        });
    }
    initialize_user_sections(active_user_ids, deactivated_user_ids);
}

function reset_scrollbar($sel: JQuery): () => void {
    return function () {
        scroll_util.reset_scrollbar($sel);
    };
}

function bot_owner_full_name(owner_id: number | null): string | undefined {
    if (!owner_id) {
        return undefined;
    }

    const bot_owner = people.maybe_get_user_by_id(owner_id);
    if (!bot_owner) {
        return undefined;
    }

    return bot_owner.full_name;
}

type BotInfo = {
    is_bot: boolean;
    role: number;
    is_active: boolean;
    user_id: number;
    full_name: string;
    user_role_text: string | undefined;
    img_src: string;
    bot_type: string | undefined;
    bot_owner_full_name: string;
    no_owner: boolean;
    is_current_user: boolean;
    can_modify: boolean;
    cannot_deactivate: boolean;
    cannot_edit: boolean;
    display_email: string;
} & (
    | {
          bot_owner_id: number;
          is_bot_owner_active: boolean;
          owner_img_src: string;
      }
    | {
          bot_owner_id: null;
      }
);

function bot_info(bot_user_id: number): BotInfo {
    const bot_user = people.get_by_user_id(bot_user_id);
    assert(bot_user.is_bot);

    const owner_id = bot_user.bot_owner_id;
    const owner_full_name = bot_owner_full_name(owner_id);

    return {
        is_bot: true,
        role: bot_user.role,
        is_active: people.is_person_active(bot_user.user_id),
        user_id: bot_user.user_id,
        full_name: bot_user.full_name,
        user_role_text: people.get_user_type(bot_user_id),
        img_src: people.small_avatar_url_for_person(bot_user),
        // Convert bot type id to string for viewing to the users.
        bot_type: settings_data.bot_type_id_to_string(bot_user.bot_type),
        bot_owner_full_name: owner_full_name ?? $t({defaultMessage: "No owner"}),
        no_owner: !owner_full_name,
        is_current_user: false,
        can_modify: current_user.is_admin,
        cannot_deactivate: bot_user.is_system_bot ?? false,
        cannot_edit: bot_user.is_system_bot ?? false,
        // It's always safe to show the real email addresses for bot users
        display_email: bot_user.email,
        ...(owner_id
            ? {
                  bot_owner_id: owner_id,
                  is_bot_owner_active: people.is_person_active(owner_id),
                  owner_img_src: people.small_avatar_url_for_person(
                      people.get_by_user_id(owner_id),
                  ),
              }
            : {
                  bot_owner_id: null,
              }),
    };
}

function get_last_active(user: User): string {
    const last_active_date = presence.last_active_date(user.user_id);
    if (!last_active_date && presence_data_fetched) {
        return timerender.render_now(new Date(user.date_joined)).time_str;
    }
    if (!last_active_date) {
        setTimeout(() => {
            loading.make_indicator(
                $(
                    `.user_row[data-user-id='${CSS.escape(user.user_id.toString())}'] .loading-placeholder`,
                ),
            );
        }, 0);
        return "";
    }
    return timerender.render_now(last_active_date).time_str;
}

function human_info(person: User): {
    is_bot: false;
    user_role_text: string | undefined;
    is_active: boolean;
    user_id: number;
    full_name: string;
    bot_owner_id: number | null;
    can_modify: boolean;
    is_current_user: boolean;
    cannot_deactivate: boolean;
    display_email: string | null;
    img_src: string;
    last_active_date: string;
} {
    return {
        is_bot: false,
        user_role_text: people.get_user_type(person.user_id),
        is_active: people.is_person_active(person.user_id),
        user_id: person.user_id,
        full_name: person.full_name,
        bot_owner_id: person.is_bot ? person.bot_owner_id : null,
        can_modify: current_user.is_admin,
        is_current_user: people.is_my_user_id(person.user_id),
        cannot_deactivate:
            person.is_owner && (!current_user.is_owner || people.is_current_user_only_owner()),
        display_email: person.delivery_email,
        img_src: people.small_avatar_url_for_person(person),
        // TODO: This is not shown in deactivated users table and it is
        // controlled by `display_last_active_column` We might just want
        // to show this for deactivated users, too, even though it might
        // usually just be undefined.
        last_active_date: get_last_active(person),
    };
}

function set_text_search_value($table: JQuery, value: string): void {
    $table.closest(".user-settings-section").find(".search").val(value);
}

let bot_list_widget: ListWidgetType<number, BotInfo>;

function bots_create_table(): void {
    loading.make_indicator($("#admin_page_bots_loading_indicator"), {
        text: $t({defaultMessage: "Loading…"}),
    });
    const $bots_table = $("#admin_bots_table");
    $bots_table.hide();
    const bot_user_ids = people.get_bot_ids();

    bot_list_widget = ListWidget.create($bots_table, bot_user_ids, {
        name: "admin_bot_list",
        get_item: bot_info,
        modifier_html: render_settings_user_list_row,
        html_selector: (item) => $(`tr[data-user-id='${CSS.escape(item.user_id.toString())}']`),
        filter: {
            $element: $bots_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
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
}

function active_create_table(active_users: number[]): void {
    const $users_table = $("#admin_users_table");
    active_section.list_widget = ListWidget.create($users_table, active_users, {
        name: "users_table_list",
        get_item: people.get_by_user_id,
        modifier_html(item) {
            return render_settings_user_list_row({
                ...human_info(item),
                display_last_active_column: true,
            });
        },
        filter: {
            predicate(person) {
                return people.predicate_for_user_settings_filters(person, active_section.filters);
            },
            is_active() {
                const $search_input = $("#admin-active-users-list .search");
                return are_filters_active(active_section.filters, $search_input);
            },
            onupdate: reset_scrollbar($users_table),
        },
        $parent_container: $("#admin-active-users-list").expectOne(),
        init_sort: "full_name_alphabetic",
        sort_fields: {
            email: user_sort.sort_email,
            last_active: sort_last_active,
            role: user_sort.sort_role,
            id: user_sort.sort_user_id,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name"]),
        },
        $simplebar_container: $("#admin-active-users-list .progressive-table-wrapper"),
    });
    loading.destroy_indicator($("#admin_page_users_loading_indicator"));
    set_text_search_value($users_table, active_section.filters.text_search);
    $("#admin_users_table").show();
}

function handle_clear_button_for_users($tbody: JQuery): void {
    const $container = $tbody.closest(".user-settings-section");
    $container.on("click", ".clear-filter", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const $filter = $container.find(".search");
        set_text_search_value($tbody, "");
        $filter.trigger("input");
    });
}

function deactivated_create_table(deactivated_users: number[]): void {
    const $deactivated_users_table = $("#admin_deactivated_users_table");
    deactivated_section.list_widget = ListWidget.create(
        $deactivated_users_table,
        deactivated_users,
        {
            name: "deactivated_users_table_list",
            get_item: people.get_by_user_id,
            modifier_html(item) {
                return render_settings_user_list_row({
                    ...human_info(item),
                    display_last_active_column: false,
                });
            },
            filter: {
                predicate(person) {
                    return people.predicate_for_user_settings_filters(
                        person,
                        deactivated_section.filters,
                    );
                },
                is_active() {
                    const $search_input = $("#admin-deactivated-users-list .search");
                    return are_filters_active(deactivated_section.filters, $search_input);
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
    set_text_search_value($deactivated_users_table, deactivated_section.filters.text_search);
    $("#admin_deactivated_users_table").show();
}

export function update_bot_data(bot_user_id: number): void {
    if (!bot_list_widget) {
        return;
    }

    bot_list_widget.render_item(bot_info(bot_user_id));
}

export function update_user_data(
    user_id: number,
    new_data: {full_name?: string; role?: number},
): void {
    const $user_row = get_user_info_row(user_id);

    if ($user_row.length === 0) {
        return;
    }

    if (new_data.full_name !== undefined) {
        // Update the full name in the table
        $user_row.find(".pill-container .view_user_profile .pill-value").text(new_data.full_name);
    }

    if (new_data.role !== undefined) {
        const user_type = people.get_user_type(user_id);
        if (user_type) {
            $user_row.find(".user_role").text(user_type);
        }
    }
}

export function redraw_bots_list(): void {
    if (!bot_list_widget) {
        return;
    }

    // In order to properly redraw after a user may have been added,
    // we need to update the bot_list_widget with the new set of bot
    // user IDs to display.
    const bot_user_ids = people.get_bot_ids();
    bot_list_widget.replace_list_data(bot_user_ids);
}

function redraw_users_list(user_section: UserSettingsSection, user_list: number[]): void {
    if (!user_section.list_widget) {
        return;
    }

    user_section.list_widget.replace_list_data(user_list);
}

export function redraw_deactivated_users_list(): void {
    if (!should_redraw_deactivated_users_list) {
        return;
    }
    const deactivated_user_ids = people.get_non_active_human_ids();
    redraw_users_list(deactivated_section, deactivated_user_ids);
    should_redraw_deactivated_users_list = false;
}

export function redraw_active_users_list(): void {
    if (!should_redraw_active_users_list) {
        return;
    }
    const active_user_ids = people.get_realm_active_human_user_ids();
    redraw_users_list(active_section, active_user_ids);
    should_redraw_active_users_list = false;
}

function start_data_load(): void {
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

function handle_deactivation($tbody: JQuery): void {
    $tbody.on("click", ".deactivate", (e) => {
        // This click event must not get propagated to parent container otherwise the modal
        // will not show up because of a call to `close_active` in `settings.ts`.
        e.preventDefault();
        e.stopPropagation();

        const $row = $(e.target).closest(".user_row");
        const user_id = Number($row.attr("data-user-id"));

        let url = "/json/users/" + encodeURIComponent(user_id);
        if (user_id === current_user.user_id) {
            url = "/json/users/me";
        }

        function handle_confirm(): void {
            let data = {};
            if ($(".send_email").is(":checked")) {
                data = {
                    deactivation_notification_comment: $(".email_field_textarea").val(),
                };
            }

            if (user_id === current_user.user_id) {
                dialog_widget.submit_api_request(channel.del, url, data, {
                    success_continuation() {
                        window.location.href = "/login/";
                    },
                });
            } else {
                dialog_widget.submit_api_request(channel.del, url, data);
            }
        }

        user_deactivation_ui.confirm_deactivation(user_id, handle_confirm, true);
    });
}

function handle_bot_deactivation($tbody: JQuery): void {
    $tbody.on("click", ".deactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const $button_elem = $(e.target);
        const $row = $button_elem.closest(".user_row");
        const bot_id = Number.parseInt($row.attr("data-user-id")!, 10);

        function handle_confirm(): void {
            const url = "/json/bots/" + encodeURIComponent(bot_id);
            dialog_widget.submit_api_request(channel.del, url, {});
        }

        user_deactivation_ui.confirm_bot_deactivation(bot_id, handle_confirm, true);
    });
}

function handle_reactivation($tbody: JQuery): void {
    $tbody.on("click", ".reactivate", (e) => {
        e.preventDefault();
        e.stopPropagation();

        // Go up the tree until we find the user row, then grab the email element
        const $button_elem = $(e.target);
        const $row = $button_elem.closest(".user_row");
        const user_id = Number.parseInt($row.attr("data-user-id")!, 10);

        function handle_confirm(): void {
            const url = "/json/users/" + encodeURIComponent(user_id) + "/reactivate";
            dialog_widget.submit_api_request(channel.post, url, {});
        }

        user_deactivation_ui.confirm_reactivation(user_id, handle_confirm, true);
    });
}

function handle_edit_form($tbody: JQuery): void {
    $tbody.on("click", ".open-user-form", function (this: HTMLElement, e) {
        e.stopPropagation();
        e.preventDefault();

        const user_id = Number.parseInt($(this).closest("tr").attr("data-user-id")!, 10);
        if (people.is_my_user_id(user_id)) {
            browser_history.go_to_location("#settings/profile");
            return;
        }

        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user, "manage-profile-tab");
    });
}

function handle_filter_change($tbody: JQuery, section: UserSettingsSection): void {
    // This duplicates the built-in search filter live-update logic in
    // ListWidget for the input.list_widget_filter event type, but we
    // can't use that, because we're also filtering on Role with our
    // custom predicate.
    $tbody
        .closest(".user-settings-section")
        .find<HTMLInputElement>(".search")
        .on("input.list_widget_filter", function (this: HTMLInputElement) {
            add_value_to_filters(section, "text_search", this.value.toLocaleLowerCase());
        });
}

function active_handle_events(): void {
    const $tbody = $("#admin_users_table").expectOne();

    handle_filter_change($tbody, active_section);
    handle_deactivation($tbody);
    handle_reactivation($tbody);
    handle_edit_form($tbody);
    handle_clear_button_for_users($tbody);
}

function deactivated_handle_events(): void {
    const $tbody = $("#admin_deactivated_users_table").expectOne();

    handle_filter_change($tbody, deactivated_section);
    handle_deactivation($tbody);
    handle_reactivation($tbody);
    handle_edit_form($tbody);
    handle_clear_button_for_users($tbody);
}

function bots_handle_events(): void {
    const $tbody = $("#admin_bots_table").expectOne();

    handle_bot_deactivation($tbody);
    handle_reactivation($tbody);
    handle_edit_form($tbody);
}

export function set_up_humans(): void {
    start_data_load();
    active_section.handle_events();
    deactivated_section.handle_events();
    setting_invites.set_up();
}

export function set_up_bots(): void {
    bots_section.handle_events();
    bots_section.create_table();

    $("#admin-bot-list .add-a-new-bot").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        settings_bots.add_a_new_bot();
    });
}

type FetchPresenceUserSettingParams = {
    render_table: () => void;
};

export function fetch_presence_user_setting({render_table}: FetchPresenceUserSettingParams): void {
    if (page_params.is_spectator) {
        render_table();
        return;
    }

    channel.post({
        url: "/json/users/me/presence",
        data: {
            status: compute_active_status(),
            ping_only: false,
            last_update_id: -1,
            history_limit_days: 365 * 1000,
        },
        success(response) {
            const data = post_presence_response_schema.parse(response);

            if (data.presences) {
                assert(
                    data.presences !== undefined,
                    "Presences should be present if not a ping only presence request",
                );
                assert(
                    data.server_timestamp !== undefined,
                    "Server timestamp should be present if not a ping only presence request",
                );
                assert(
                    data.presence_last_update_id !== undefined,
                    "Presence last update id should be present if not a ping only presence request",
                );

                // the next regular default presence check in with the server should naturally pick up from here.
                presence.set_info(
                    data.presences,
                    data.server_timestamp,
                    data.presence_last_update_id,
                );
            }
            render_table();
        },
    });
}
