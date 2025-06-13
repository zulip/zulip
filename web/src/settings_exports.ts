import $ from "jquery";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_confirm_delete_data_export from "../templates/confirm_dialog/confirm_delete_data_export.hbs";
import render_allow_private_data_export_banner from "../templates/modal_banner/allow_private_data_export_banner.hbs";
import render_admin_export_consent_list from "../templates/settings/admin_export_consent_list.hbs";
import render_admin_export_list from "../templates/settings/admin_export_list.hbs";
import render_start_export_modal from "../templates/start_export_modal.hbs";

import * as channel from "./channel.ts";
import * as components from "./components.ts";
import * as compose_banner from "./compose_banner.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import type {DropdownWidget, Option} from "./dropdown_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as people from "./people.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_config from "./settings_config.ts";
import * as timerender from "./timerender.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import {user_settings} from "./user_settings.ts";

export const export_consent_schema = z.object({
    user_id: z.number(),
    consented: z.boolean(),
});
type ExportConsent = z.output<typeof export_consent_schema>;

export const realm_export_schema = z.object({
    id: z.number(),
    export_time: z.number(),
    acting_user_id: z.number(),
    export_url: z.nullable(z.string()),
    deleted_timestamp: z.nullable(z.number()),
    failed_timestamp: z.nullable(z.number()),
    pending: z.boolean(),
    export_type: z.number(),
});
type RealmExport = z.output<typeof realm_export_schema>;

const meta = {
    loaded: false,
};

let users_consented_for_export_count: number;
let total_users_count: number;

export function reset(): void {
    meta.loaded = false;
}

function sort_user(a: RealmExport, b: RealmExport): number {
    const a_name = people.get_full_name(a.acting_user_id).toLowerCase();
    const b_name = people.get_full_name(b.acting_user_id).toLowerCase();
    if (a_name > b_name) {
        return 1;
    } else if (a_name === b_name) {
        return 0;
    }
    return -1;
}

export function populate_exports_table(exports: RealmExport[]): void {
    if (!meta.loaded) {
        return;
    }

    const $exports_table = $("#admin_exports_table").expectOne();
    ListWidget.create($exports_table, Object.values(exports), {
        name: "admin_exports_list",
        get_item: ListWidget.default_get_item,
        modifier_html(data) {
            let failed_timestamp = null;
            let deleted_timestamp = null;

            if (data.failed_timestamp !== null) {
                failed_timestamp = timerender.relative_time_string_from_date(
                    new Date(data.failed_timestamp * 1000),
                );
            }

            if (data.deleted_timestamp !== null) {
                deleted_timestamp = timerender.relative_time_string_from_date(
                    new Date(data.deleted_timestamp * 1000),
                );
            }

            let export_type = settings_config.export_type_values.export_public.description;
            if (data.export_type !== settings_config.export_type_values.export_public.value) {
                export_type =
                    settings_config.export_type_values.export_full_with_consent.description;
            }

            return render_admin_export_list({
                realm_export: {
                    id: data.id,
                    acting_user: people.get_full_name(data.acting_user_id),
                    // Convert seconds -> milliseconds
                    event_time: timerender.relative_time_string_from_date(
                        new Date(data.export_time * 1000),
                    ),
                    url: data.export_url,
                    time_failed: failed_timestamp,
                    pending: data.pending,
                    time_deleted: deleted_timestamp,
                    export_type,
                },
            });
        },
        filter: {
            $element: $exports_table
                .closest(".settings-section")
                .find<HTMLInputElement>("input.search"),
            predicate(item, value) {
                return people.get_full_name(item.acting_user_id).toLowerCase().includes(value);
            },
            onupdate() {
                scroll_util.reset_scrollbar($exports_table);
            },
        },
        $parent_container: $('[data-export-section="data-exports"]').expectOne(),
        init_sort: sort_user,
        sort_fields: {
            user: sort_user,
            ...ListWidget.generic_sort_functions("numeric", ["export_time"]),
        },
        $simplebar_container: $('[data-export-section="data-exports"] .progressive-table-wrapper'),
    });

    const $spinner = $(".export_row .export_url_spinner");
    if ($spinner.length > 0) {
        loading.make_indicator($spinner);
    } else {
        loading.destroy_indicator($spinner);
    }
}

function sort_user_by_name(a: ExportConsent, b: ExportConsent): number {
    const a_name = people.get_full_name(a.user_id).toLowerCase();
    const b_name = people.get_full_name(b.user_id).toLowerCase();
    if (a_name > b_name) {
        return 1;
    } else if (a_name === b_name) {
        return 0;
    }
    return -1;
}

const export_consents = new Map<number, boolean>();
const queued_export_consents: (ExportConsent | number)[] = [];
let export_consent_list_widget: ListWidgetType<ExportConsent>;
let filter_by_consent_dropdown_widget: DropdownWidget;
const filter_by_consent_options: Option[] = [
    {
        unique_id: 0,
        name: $t({defaultMessage: "Granted"}),
    },
    {
        unique_id: 1,
        name: $t({defaultMessage: "Not granted"}),
    },
];

function get_export_consents_having_consent_value(consent: boolean): ExportConsent[] {
    const export_consent_list: ExportConsent[] = [];
    for (const [user_id, consented] of export_consents.entries()) {
        if (consent === consented) {
            export_consent_list.push({user_id, consented});
        }
    }
    return export_consent_list;
}

export function redraw_export_consents_list(): void {
    let new_list_data;
    if (filter_by_consent_dropdown_widget.value() === filter_by_consent_options[0]!.unique_id) {
        new_list_data = get_export_consents_having_consent_value(true);
    } else {
        new_list_data = get_export_consents_having_consent_value(false);
    }
    export_consent_list_widget.replace_list_data(new_list_data);
}

export function populate_export_consents_table(): void {
    if (!meta.loaded) {
        return;
    }

    const $export_consents_table = $("#admin_export_consents_table").expectOne();
    export_consent_list_widget = ListWidget.create(
        $export_consents_table,
        get_export_consents_having_consent_value(true),
        {
            name: "admin_export_consents_list",
            get_item: ListWidget.default_get_item,
            modifier_html(item) {
                const person = people.get_by_user_id(item.user_id);
                let consent = $t({defaultMessage: "Not granted"});
                if (item.consented) {
                    consent = $t({defaultMessage: "Granted"});
                }
                return render_admin_export_consent_list({
                    export_consent: {
                        user_id: person.user_id,
                        full_name: person.full_name,
                        img_src: people.small_avatar_url_for_person(person),
                        consent,
                    },
                });
            },
            filter: {
                $element: $export_consents_table
                    .closest(".export_section")
                    .find<HTMLInputElement>("input.search"),
                predicate(item, value) {
                    return people.get_full_name(item.user_id).toLowerCase().includes(value);
                },
                onupdate() {
                    scroll_util.reset_scrollbar($export_consents_table);
                },
            },
            $parent_container: $('[data-export-section="export-permissions"]').expectOne(),
            init_sort: sort_user_by_name,
            sort_fields: {
                full_name: sort_user_by_name,
            },
            $simplebar_container: $(
                '[data-export-section="export-permissions"] .progressive-table-wrapper',
            ),
        },
    );

    filter_by_consent_dropdown_widget = new dropdown_widget.DropdownWidget({
        widget_name: "filter_by_consent",
        unique_id_type: "number",
        get_options: () => filter_by_consent_options,
        item_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
            widget: dropdown_widget.DropdownWidget,
        ) {
            event.preventDefault();
            event.stopPropagation();

            redraw_export_consents_list();

            dropdown.hide();
            widget.render();
        },
        $events_container: $("#data-exports"),
        default_id: filter_by_consent_options[0]!.unique_id,
        hide_search_box: true,
    });
    filter_by_consent_dropdown_widget.setup();
}

function maybe_show_allow_private_data_export_banner(): void {
    if (!user_settings.allow_private_data_export) {
        const context = {
            banner_type: compose_banner.WARNING,
            classname: "allow_private_data_export_warning",
            hide_close_button: true,
        };
        $("#allow_private_data_export_banner_container").html(
            render_allow_private_data_export_banner(context),
        );
    }
}

export function refresh_allow_private_data_export_banner(): void {
    if (user_settings.allow_private_data_export) {
        $(".allow_private_data_export_warning").remove();
    } else if ($("#allow_private_data_export_banner_container").length > 0) {
        maybe_show_allow_private_data_export_banner();
        const $export_type = $<HTMLSelectOneElement>("select:not([multiple])#export_type");
        const selected_export_type = Number.parseInt($export_type.val()!, 10);
        if (selected_export_type === settings_config.export_type_values.export_public.value) {
            $(".allow_private_data_export_warning").hide();
        }
    }
}

function show_start_export_modal(): void {
    const html_body = render_start_export_modal({
        export_type_values: settings_config.export_type_values,
    });

    function start_export(): void {
        dialog_widget.show_dialog_spinner();
        const $export_status = $("#export_status");
        const export_type = Number.parseInt(
            $<HTMLSelectOneElement>("select:not([multiple])#export_type").val()!,
            10,
        );

        void channel.post({
            url: "/json/export/realm",
            data: {export_type},
            success() {
                dialog_widget.hide_dialog_spinner();
                ui_report.success(
                    $t_html({defaultMessage: "Export started. Check back in a few minutes."}),
                    $export_status,
                    4000,
                );
                dialog_widget.close();
            },
            error(xhr) {
                dialog_widget.hide_dialog_spinner();
                ui_report.error($t_html({defaultMessage: "Export failed"}), xhr, $export_status);
                dialog_widget.close();
            },
        });
    }

    function start_export_modal_post_render(): void {
        $("#allow_private_data_export_stats").text(
            $t(
                {
                    defaultMessage:
                        "Exporting private data for {users_consented_for_export_count} users ({total_users_count} users total).",
                },
                {users_consented_for_export_count, total_users_count},
            ),
        );

        maybe_show_allow_private_data_export_banner();

        const $export_type = $<HTMLSelectOneElement>("select:not([multiple])#export_type");
        $export_type.on("change", () => {
            const selected_export_type = Number.parseInt($export_type.val()!, 10);
            if (
                selected_export_type ===
                settings_config.export_type_values.export_full_with_consent.value
            ) {
                $("#allow_private_data_export_stats").show();
                $(".allow_private_data_export_warning").show();
            } else {
                $("#allow_private_data_export_stats").hide();
                $(".allow_private_data_export_warning").hide();
            }
        });
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Start export?"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Start export"}),
        id: "start-export-modal",
        loading_spinner: true,
        on_click: start_export,
        post_render: start_export_modal_post_render,
    });
}

export function set_up(): void {
    meta.loaded = true;

    const toggler = components.toggle({
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "Data exports"}), key: "data-exports"},
            {label: $t({defaultMessage: "Export permissions"}), key: "export-permissions"},
        ],
        callback(_name, key) {
            $(".export_section").hide();
            $(`[data-export-section="${CSS.escape(key)}"]`).show();
        },
    });

    toggler.get().prependTo($("#data-exports .tab-container"));
    toggler.goto("data-exports");

    // Do an initial population of the 'Export permissions' table
    void channel.get({
        url: "/json/export/realm/consents",
        success(raw_data) {
            const data = z
                .object({export_consents: z.array(export_consent_schema)})
                .parse(raw_data);

            for (const export_consent of data.export_consents) {
                export_consents.set(export_consent.user_id, export_consent.consented);
            }

            // Apply queued_export_consents on top of the received response.
            for (const item of queued_export_consents) {
                if (typeof item === "number") {
                    // user deactivated; item is user_id in this case.
                    export_consents.delete(item);
                    continue;
                }
                export_consents.set(item.user_id, item.consented);
            }
            queued_export_consents.length = 0;

            total_users_count = export_consents.size;
            users_consented_for_export_count =
                get_export_consents_having_consent_value(true).length;
            populate_export_consents_table();
        },
    });

    $("#start-export-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        show_start_export_modal();
    });

    // Do an initial population of the 'Data exports' table
    void channel.get({
        url: "/json/export/realm",
        success(raw_data) {
            const data = z.object({exports: z.array(realm_export_schema)}).parse(raw_data);
            populate_exports_table(data.exports);
        },
    });

    $(".admin_exports_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $button = $(this);
        const url =
            "/json/export/realm/" +
            encodeURIComponent($button.closest("tr").attr("data-export-id")!);
        const html_body = render_confirm_delete_data_export();

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete data export?"}),
            html_body,
            on_click() {
                dialog_widget.submit_api_request(channel.del, url, {});
            },
            loading_spinner: true,
        });
    });
}

function maybe_store_export_consent_data_and_return(export_consent: ExportConsent): boolean {
    // Handles a race where the client has requested the server for export consents
    // to populate 'Export permissions' table but hasn't received the response yet,
    // but received a few updated events which should be applied on top of the received
    // response to avoid outdated table.
    // We store the export_consent data received via events to apply them on top of
    // the received response.
    if (export_consents === undefined) {
        queued_export_consents.push(export_consent);
        return true;
    }
    return false;
}

function update_start_export_modal_stats(): void {
    total_users_count = export_consents.size;
    users_consented_for_export_count = get_export_consents_having_consent_value(true).length;
    if ($("#allow_private_data_export_stats").length > 0) {
        $("#allow_private_data_export_stats").text(
            $t(
                {
                    defaultMessage:
                        "Exporting private data for {users_consented_for_export_count} users ({total_users_count} users total).",
                },
                {users_consented_for_export_count, total_users_count},
            ),
        );
    }
}

export function remove_export_consent_data_and_redraw(user_id: number): void {
    if (!meta.loaded) {
        return;
    }

    if (export_consents === undefined) {
        queued_export_consents.push(user_id);
        return;
    }

    export_consents.delete(user_id);
    redraw_export_consents_list();
    update_start_export_modal_stats();
}

export function update_export_consent_data_and_redraw(export_consent: ExportConsent): void {
    if (!meta.loaded) {
        return;
    }

    if (maybe_store_export_consent_data_and_return(export_consent)) {
        return;
    }

    export_consents.set(export_consent.user_id, export_consent.consented);
    redraw_export_consents_list();
    update_start_export_modal_stats();
}
