import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_add_new_bot_form from "../templates/settings/add_new_bot_form.hbs";
import render_bot_settings_tip from "../templates/settings/bot_settings_tip.hbs";
import render_settings_user_list_row from "../templates/settings/settings_user_list_row.hbs";

import * as avatar from "./avatar.ts";
import * as bot_data from "./bot_data.ts";
import type {Bot} from "./bot_data.ts";
import * as bot_helper from "./bot_helper.ts";
import * as channel from "./channel.ts";
import {csrf_token} from "./csrf.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as integration_url_modal from "./integration_url_modal.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_users from "./settings_users.ts";
import {current_user, realm} from "./state_data.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import type {UploadWidget} from "./upload_widget.ts";
import * as user_deactivation_ui from "./user_deactivation_ui.ts";
import * as user_sort from "./user_sort.ts";
import * as util from "./util.ts";

const GENERIC_BOT_TYPE = 1;
const INCOMING_WEBHOOK_BOT_TYPE = 2;
const OUTGOING_WEBHOOK_BOT_TYPE = "3";
const OUTGOING_WEBHOOK_BOT_TYPE_INT = 3;
const EMBEDDED_BOT_TYPE = "4";

export const all_bots_list_dropdown_widget_name = "all_bots_list_select_bot_status";
export const your_bots_list_dropdown_widget_name = "your_bots_list_select_bot_status";

type BotType = {
    type_id: number;
    name: string;
};

type BotInfo = {
    is_bot: boolean;
    role: number;
    status_code: number;
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
    show_download_zuliprc_button: boolean;
    show_generate_integration_url_button: boolean;
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

type BotSettingsSection = {
    dropdown_widget_name: string;
    filters: {
        text_search: string;
        status_code: number;
    };
    handle_events: () => void;
    create_table: () => void;
    list_widget: ListWidgetType<number, BotInfo> | undefined;
};

const all_bots_section: BotSettingsSection = {
    dropdown_widget_name: all_bots_list_dropdown_widget_name,
    filters: {
        text_search: "",
        // 0 status_code signifies Active status for our filter.
        status_code: 0,
    },
    handle_events: all_bots_handle_events,
    create_table: create_all_bots_table,
    list_widget: undefined,
};

const your_bots_section: BotSettingsSection = {
    dropdown_widget_name: your_bots_list_dropdown_widget_name,
    filters: {
        text_search: "",
        status_code: 0,
    },
    handle_events: your_bots_handle_events,
    create_table: create_your_bots_table,
    list_widget: undefined,
};

function sort_bot_email(a: BotInfo, b: BotInfo): number {
    function email(bot: BotInfo): string {
        return (bot.display_email ?? "").toLowerCase();
    }

    return util.compare_a_b(email(a), email(b));
}

function sort_bot_owner(a: BotInfo, b: BotInfo): number {
    // Always show bots without owner at bottom
    if (a.no_owner && b.no_owner) {
        return 0;
    }
    if (a.no_owner) {
        return 1;
    }
    if (b.no_owner) {
        return -1;
    }

    return util.compare_a_b(
        a.bot_owner_full_name.toLowerCase(),
        b.bot_owner_full_name.toLocaleLowerCase(),
    );
}

export function generate_botserverrc_content(
    email: string,
    api_key: string,
    token: string,
): string {
    return (
        "[]" +
        "\nemail=" +
        email +
        "\nkey=" +
        api_key +
        "\nsite=" +
        realm.realm_url +
        "\ntoken=" +
        token +
        "\n"
    );
}

export function can_create_new_bots(): boolean {
    return settings_data.user_has_permission_for_group_setting(
        realm.realm_can_create_bots_group,
        "can_create_bots_group",
        "realm",
    );
}

export function can_create_incoming_webhooks(): boolean {
    // User who have the permission to create any bot can also
    // create incoming webhooks.
    return (
        can_create_new_bots() ||
        settings_data.user_has_permission_for_group_setting(
            realm.realm_can_create_write_only_bots_group,
            "can_create_write_only_bots_group",
            "realm",
        )
    );
}

export function update_bot_settings_tip($tip_container: JQuery): void {
    if (can_create_new_bots()) {
        $tip_container.hide();
        return;
    }

    const rendered_tip = render_bot_settings_tip({
        can_create_any_bots: can_create_new_bots(),
        can_create_incoming_webhooks: can_create_incoming_webhooks(),
    });
    $tip_container.show();
    $tip_container.html(rendered_tip);
}

function update_add_bot_button(): void {
    if (can_create_incoming_webhooks()) {
        $("#admin-bot-list .add-a-new-bot").show();
        $(".org-settings-list li[data-section='bots'] .locked").hide();
    } else {
        $("#admin-bot-list .add-a-new-bot").hide();
        $(".org-settings-list li[data-section='bots'] .locked").show();
    }
}

export function update_bot_permissions_ui(): void {
    update_bot_settings_tip($("#admin-bot-settings-tip"));
    update_add_bot_button();
}

export function get_allowed_bot_types(): BotType[] {
    const allowed_bot_types: BotType[] = [];
    const bot_types = settings_config.bot_type_values;
    if (can_create_new_bots()) {
        allowed_bot_types.push(
            bot_types.default_bot,
            bot_types.incoming_webhook_bot,
            bot_types.outgoing_webhook_bot,
        );
        if (page_params.embedded_bots_enabled) {
            allowed_bot_types.push(bot_types.embedded_bot);
        }
    } else if (can_create_incoming_webhooks()) {
        allowed_bot_types.push(bot_types.incoming_webhook_bot);
    }
    return allowed_bot_types;
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

export function add_a_new_bot(): void {
    const html_body = render_add_new_bot_form({
        bot_types: get_allowed_bot_types(),
        realm_embedded_bots: realm.realm_embedded_bots,
        realm_bot_domain: realm.realm_bot_domain,
    });

    let create_avatar_widget: UploadWidget;

    function create_a_new_bot(): void {
        const bot_type = $<HTMLSelectOneElement>("select:not([multiple])#create_bot_type").val()!;
        const full_name = $<HTMLInputElement>("input#create_bot_name").val()!;
        const short_name =
            $<HTMLInputElement>("input#create_bot_short_name").val() ??
            $("#create_bot_short_name").text();
        const payload_url = $("#create_payload_url").val();
        const interface_type = $<HTMLSelectOneElement>(
            "select:not([multiple])#create_interface_type",
        ).val()!;
        const service_name = $<HTMLSelectOneElement>(
            "select:not([multiple])#select_service_name",
        ).val()!;
        const formData = new FormData();
        assert(csrf_token !== undefined);
        formData.append("csrfmiddlewaretoken", csrf_token);
        formData.append("bot_type", bot_type);
        formData.append("full_name", full_name);
        formData.append("short_name", short_name);

        // If the selected bot_type is Outgoing webhook
        if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
            formData.append("payload_url", JSON.stringify(payload_url));
            formData.append("interface_type", interface_type);
        } else if (bot_type === EMBEDDED_BOT_TYPE) {
            formData.append("service_name", service_name);
            const config_data: Record<string, string> = {};
            $<HTMLInputElement>(
                `#config_inputbox [name*='${CSS.escape(service_name)}'] input`,
            ).each(function () {
                const key = $(this).attr("name")!;
                const value = $(this).val()!;
                config_data[key] = value;
            });
            formData.append("config_data", JSON.stringify(config_data));
        }
        const files = $<HTMLInputElement>("input#bot_avatar_file_input")[0]!.files;
        assert(files !== null);
        for (const [i, file] of [...files].entries()) {
            formData.append("file-" + i, file);
        }

        void channel.post({
            url: "/json/bots",
            data: formData,
            cache: false,
            processData: false,
            contentType: false,
            success() {
                create_avatar_widget.clear();
                dialog_widget.close();
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                dialog_widget.hide_dialog_spinner();
            },
        });
    }

    function set_up_form_fields(): void {
        $("#create_bot_type").val(INCOMING_WEBHOOK_BOT_TYPE);
        $("#payload_url_inputbox").hide();
        $("#create_payload_url").val("");
        $("#service_name_list").hide();
        $("#config_inputbox").hide();
        const selected_embedded_bot = "converter";
        $("#select_service_name").val(selected_embedded_bot); // TODO: Use 'select a bot'.
        $("#config_inputbox").children().hide();
        $(`[name*='${CSS.escape(selected_embedded_bot)}']`).show();

        create_avatar_widget = avatar.build_bot_create_widget();

        $("#create_bot_type").on("change", () => {
            const bot_type = $("#create_bot_type").val();
            // For "generic bot" or "incoming webhook" both these fields need not be displayed.
            $("#service_name_list").hide();
            $("#select_service_name").removeClass("required");
            $("#config_inputbox").hide();

            $("#payload_url_inputbox").hide();
            $("#create_payload_url").removeClass("required");
            if (bot_type === OUTGOING_WEBHOOK_BOT_TYPE) {
                $("#payload_url_inputbox").show();
                $("#create_payload_url").addClass("required");
            } else if (bot_type === EMBEDDED_BOT_TYPE) {
                $("#service_name_list").show();
                $("#select_service_name").addClass("required");
                $("#select_service_name").trigger("change");
                $("#config_inputbox").show();
            }
        });

        $("#select_service_name").on("change", () => {
            $("#config_inputbox").children().hide();
            const selected_bot = $<HTMLSelectOneElement>(
                "select:not([multiple])#select_service_name",
            ).val()!;
            $(`[name*='${CSS.escape(selected_bot)}']`).show();
        });
    }

    function validate_input(): boolean {
        const bot_short_name = $<HTMLInputElement>("input#create_bot_short_name").val()!;

        if (bot_helper.validate_bot_short_name(bot_short_name)) {
            return true;
        }
        ui_report.error(
            $t_html({
                defaultMessage: "Please only use characters that are valid in an email address",
            }),
            undefined,
            $("#dialog_error"),
        );
        return false;
    }

    dialog_widget.launch({
        form_id: "create_bot_form",
        help_link: "/help/add-a-bot-or-integration",
        html_body,
        html_heading: $t_html({defaultMessage: "Add a new bot"}),
        html_submit_button: $t_html({defaultMessage: "Add"}),
        loading_spinner: true,
        on_click: create_a_new_bot,
        on_shown: () => $("#create_bot_type").trigger("focus"),
        post_render: set_up_form_fields,
        validate_input,
    });
}

function bot_info(bot_user_id: number): BotInfo {
    const bot_user = people.get_by_user_id(bot_user_id);
    assert(bot_user.is_bot);

    const owner_id = bot_user.bot_owner_id;
    const owner_full_name = bot_owner_full_name(owner_id);

    const is_bot_owner = owner_id === current_user.user_id;
    const can_modify_bot = current_user.is_admin || is_bot_owner;

    return {
        is_bot: true,
        role: bot_user.role,
        is_active: people.is_person_active(bot_user.user_id),
        status_code: people.is_person_active(bot_user.user_id) ? 0 : 1,
        user_id: bot_user.user_id,
        full_name: bot_user.full_name,
        user_role_text: people.get_user_type(bot_user_id),
        img_src: people.small_avatar_url_for_person(bot_user),
        // Convert bot type id to string for viewing to the users.
        bot_type: settings_data.bot_type_id_to_string(bot_user.bot_type),
        bot_owner_full_name: owner_full_name ?? $t({defaultMessage: "No owner"}),
        no_owner: !owner_full_name,
        is_current_user: false,
        can_modify: can_modify_bot,
        cannot_deactivate: (bot_user.is_system_bot ?? false) || !can_modify_bot,
        cannot_edit: (bot_user.is_system_bot ?? false) || !can_modify_bot,
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
        show_download_zuliprc_button: is_bot_owner && bot_user.bot_type === GENERIC_BOT_TYPE,
        show_generate_integration_url_button:
            can_modify_bot && bot_user.bot_type === INCOMING_WEBHOOK_BOT_TYPE,
    };
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

function predicate_for_bot_filtering(item: BotInfo, section: BotSettingsSection): boolean {
    if (!item) {
        return false;
    }
    const search_query = section.filters.text_search.toLowerCase();
    const filter_searches =
        item.full_name.toLowerCase().includes(search_query) ||
        item.display_email.toLowerCase().includes(search_query);

    const filter_status = item.status_code === section.filters.status_code;
    return filter_searches && filter_status;
}

export function toggle_bot_config_download_container(): void {
    const bots = bot_data.get_all_bots_for_current_user().filter((elem: Bot) => {
        const is_active = people.is_person_active(elem.user_id);
        return elem.bot_type === OUTGOING_WEBHOOK_BOT_TYPE_INT && is_active;
    });
    $("#botserverrc-text-container").toggle(bots.length > 0);
}

export function redraw_all_bots_list(): void {
    // In order to properly redraw after a user may have been added,
    // we need to update the all_bots_section.list_widget with the new
    // set of bot user IDs to display.
    if (!all_bots_section.list_widget) {
        return;
    }

    const bot_user_ids = people.get_bot_ids();
    all_bots_section.list_widget.replace_list_data(bot_user_ids);
}

export function redraw_your_bots_list(): void {
    // In order to properly redraw after a user may have been added,
    // we need to update the your_bots_list_widget with the new set of bot
    // user IDs to display.
    if (!your_bots_section.list_widget) {
        return;
    }

    const bot_user_ids_for_current_owner = bot_data.get_all_bots_ids_for_current_user();
    your_bots_section.list_widget.replace_list_data(bot_user_ids_for_current_owner);
}

function add_value_to_filters(
    section: BotSettingsSection,
    key: "status_code" | "text_search",
    value: number | string,
): void {
    if (key === "status_code") {
        assert(typeof value === "number");
        section.filters.status_code = value;
    } else {
        assert(key === "text_search");
        assert(typeof value === "string");
        section.filters.text_search = value;
    }
    // This hard_redraw will rerun the relevant predicate function
    // and in turn apply the new filters.
    assert(section.list_widget !== undefined);
    section.list_widget.hard_redraw();
}

function handle_filter_change($tbody: JQuery, section: BotSettingsSection): void {
    // This duplicates the built-in search filter live-update logic in
    // ListWidget for the input.list_widget_filter event type, but we
    // can't use that, because we're also filtering on Role with our
    // custom predicate.
    $tbody
        .closest(".user-or-bot-settings-section")
        .find<HTMLInputElement>(".search")
        .on("input.list_widget_filter", function (this: HTMLInputElement) {
            add_value_to_filters(section, "text_search", this.value.toLocaleLowerCase());
        });
}

function get_bot_status_options(): {unique_id: number; name: string}[] {
    return [
        {unique_id: 0, name: $t({defaultMessage: "Active"})},
        {unique_id: 1, name: $t({defaultMessage: "Deactivated"})},
    ];
}

function status_selected_handler(
    event: JQuery.ClickEvent,
    dropdown: tippy.Instance,
    widget: dropdown_widget.DropdownWidget,
): void {
    event.preventDefault();
    event.stopPropagation();

    const status_code = Number($(event.currentTarget).attr("data-unique-id"));
    if (widget.widget_name === all_bots_section.dropdown_widget_name) {
        add_value_to_filters(all_bots_section, "status_code", status_code);
    } else if (widget.widget_name === your_bots_section.dropdown_widget_name) {
        add_value_to_filters(your_bots_section, "status_code", status_code);
    }
    dropdown.hide();
    widget.render();
}

function create_status_filter_dropdown(
    $events_container: JQuery,
    section: BotSettingsSection,
): void {
    new dropdown_widget.DropdownWidget({
        widget_name: section.dropdown_widget_name,
        unique_id_type: "number",
        get_options: get_bot_status_options,
        $events_container,
        item_click_callback: status_selected_handler,
        default_id: section.filters.status_code,
        hide_search_box: true,
        tippy_props: {
            offset: [0, 0],
        },
    }).setup();
}

function are_filters_active(
    filters: BotSettingsSection["filters"],
    $search_input: JQuery,
): boolean {
    const search_value = String($search_input.val()).trim();
    return Boolean(search_value) || filters.status_code !== 0;
}

function reset_scrollbar($sel: JQuery): () => void {
    return function () {
        scroll_util.reset_scrollbar($sel);
    };
}

function create_all_bots_table(): void {
    loading.make_indicator($("#admin_page_all_bots_loading_indicator"), {
        text: $t({defaultMessage: "Loading…"}),
    });
    const $all_bots_table = $("#admin_all_bots_table");
    $all_bots_table.hide();
    const bot_user_ids = people.get_bot_ids();

    all_bots_section.list_widget = ListWidget.create($all_bots_table, bot_user_ids, {
        name: "admin_bot_list",
        get_item: bot_info,
        modifier_html: render_settings_user_list_row,
        html_selector: (item) => $(`tr[data-user-id='${CSS.escape(item.user_id.toString())}']`),
        filter: {
            predicate(item) {
                return predicate_for_bot_filtering(item, all_bots_section);
            },
            is_active() {
                const $search_input = $("#admin-all-bots-list .search");
                return are_filters_active(all_bots_section.filters, $search_input);
            },
            onupdate: reset_scrollbar($all_bots_table),
        },
        $parent_container: $("#admin-all-bots-list").expectOne(),
        init_sort: "full_name_alphabetic",
        sort_fields: {
            email: sort_bot_email,
            bot_owner: sort_bot_owner,
            role: user_sort.sort_role,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name", "bot_type"]),
        },
        $simplebar_container: $("#admin-all-bots-list .progressive-table-wrapper"),
    });
    settings_users.set_text_search_value($all_bots_table, all_bots_section.filters.text_search);

    loading.destroy_indicator($("#admin_page_all_bots_loading_indicator"));
    $all_bots_table.show();
}

function create_your_bots_table(): void {
    loading.make_indicator($("#admin_page_your_bots_loading_indicator"), {
        text: $t({defaultMessage: "Loading…"}),
    });
    const $your_bots_table = $("#admin_your_bots_table");
    $your_bots_table.hide();
    const bot_user_ids = bot_data.get_all_bots_ids_for_current_user();
    your_bots_section.list_widget = ListWidget.create($your_bots_table, bot_user_ids, {
        name: "admin_your_bot_list",
        get_item: bot_info,
        modifier_html: render_settings_user_list_row,
        html_selector: (item) => $(`tr[data-user-id='${CSS.escape(item.user_id.toString())}']`),
        filter: {
            predicate(item) {
                return predicate_for_bot_filtering(item, your_bots_section);
            },
            is_active() {
                const $search_input = $("#admin-your-bots-list .search");
                return are_filters_active(your_bots_section.filters, $search_input);
            },
            onupdate: reset_scrollbar($your_bots_table),
        },
        $parent_container: $("#admin-your-bots-list").expectOne(),
        init_sort: "full_name_alphabetic",
        sort_fields: {
            email: sort_bot_email,
            bot_owner: sort_bot_owner,
            role: user_sort.sort_role,
            ...ListWidget.generic_sort_functions("alphabetic", ["full_name", "bot_type"]),
        },
        $simplebar_container: $("#admin-your-bots-list .progressive-table-wrapper"),
    });
    settings_users.set_text_search_value($your_bots_table, your_bots_section.filters.text_search);

    loading.destroy_indicator($("#admin_page_your_bots_loading_indicator"));
    $your_bots_table.show();
}

export function update_bot_data(bot_user_id: number): void {
    if (all_bots_section.list_widget) {
        all_bots_section.list_widget.render_item(bot_info(bot_user_id));
    }

    if (your_bots_section.list_widget) {
        your_bots_section.list_widget.render_item(bot_info(bot_user_id));
    }
}

function all_bots_handle_events(): void {
    const $tbody = $("#admin_all_bots_table").expectOne();

    handle_filter_change($tbody, all_bots_section);
    handle_bot_deactivation($tbody);
    settings_users.handle_reactivation($tbody);
    settings_users.handle_edit_form($tbody);
    settings_users.handle_clear_button_for_table_search_input($tbody);
}

function your_bots_handle_events(): void {
    const $tbody = $("#admin_your_bots_table").expectOne();

    handle_filter_change($tbody, your_bots_section);
    handle_bot_deactivation($tbody);
    settings_users.handle_reactivation($tbody);
    settings_users.handle_edit_form($tbody);
    settings_users.handle_clear_button_for_table_search_input($tbody);
}

export function set_up_bots(): void {
    all_bots_section.handle_events();
    your_bots_section.handle_events();
    all_bots_section.create_table();
    your_bots_section.create_table();

    $("#admin-bot-list .add-a-new-bot").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        add_a_new_bot();
    });
    create_status_filter_dropdown($("#admin-all-bots-list"), all_bots_section);
    create_status_filter_dropdown($("#admin-your-bots-list"), your_bots_section);

    $("#download-botserverrc-file").on("click", () => {
        let content = "";

        for (const bot of bot_data.get_all_bots_for_current_user()) {
            if (bot.is_active && bot.bot_type === OUTGOING_WEBHOOK_BOT_TYPE_INT) {
                const services = bot_data.get_services(bot.user_id);
                assert(services !== undefined);
                const service = services[0];
                assert(service && "token" in service);
                const bot_token = service.token;
                content += generate_botserverrc_content(bot.email, bot.api_key, bot_token);
            }
        }

        $("#hidden-botserverrc-download").attr(
            "href",
            "data:application/octet-stream;charset=utf-8," + encodeURIComponent(content),
        );
        $("#hidden-botserverrc-download")[0]?.click();
    });
    toggle_bot_config_download_container();

    $("#admin-bot-list").on("click", ".download-bot-zuliprc-button", (e) => {
        const $row = $(e.target).closest(".user_row");
        const $zuliprc_link = $row.find(".hidden-zuliprc-download");
        const bot_id = Number.parseInt($zuliprc_link.attr("data-user-id")!, 10);
        $zuliprc_link.attr("href", bot_helper.generate_zuliprc_url(bot_id));
        $zuliprc_link[0]?.click();
    });

    $("#admin-bot-list").on("click", ".generate-integration-url-button", (e) => {
        const $row = $(e.target).closest(".user_row");
        const bot_id = Number.parseInt($row.attr("data-user-id")!, 10);
        const current_bot_data = bot_data.get(bot_id);
        assert(current_bot_data !== undefined);
        integration_url_modal.show_generate_integration_url_modal(current_bot_data.api_key);
    });
}
