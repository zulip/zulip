import $ from "jquery";
import {z} from "zod";

import render_confirm_delete_data_export from "../templates/confirm_dialog/confirm_delete_data_export.hbs";
import render_admin_export_list from "../templates/settings/admin_export_list.hbs";
import render_start_export_modal from "../templates/start_export_modal.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as settings_config from "./settings_config";
import * as timerender from "./timerender";
import type {HTMLSelectOneElement} from "./types";
import * as ui_report from "./ui_report";

const export_consent_schema = z.object({
    user_id: z.number(),
    consented: z.boolean(),
});

const realm_export_schema = z.object({
    id: z.number(),
    export_time: z.number(),
    acting_user_id: z.number(),
    export_url: z.string().nullable(),
    deleted_timestamp: z.number().nullable(),
    failed_timestamp: z.number().nullable(),
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
        $parent_container: $("#data-exports").expectOne(),
        init_sort: sort_user,
        sort_fields: {
            user: sort_user,
            ...ListWidget.generic_sort_functions("numeric", ["export_time"]),
        },
        $simplebar_container: $("#data-exports .progressive-table-wrapper"),
    });

    const $spinner = $(".export_row .export_url_spinner");
    if ($spinner.length) {
        loading.make_indicator($spinner);
    } else {
        loading.destroy_indicator($spinner);
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
        const $export_type = $<HTMLSelectOneElement>("select:not([multiple])#export_type");
        $export_type.on("change", () => {
            const selected_export_type = Number.parseInt($export_type.val()!, 10);
            if (
                selected_export_type ===
                settings_config.export_type_values.export_full_with_consent.value
            ) {
                $("#allow_private_data_export_stats").show();
            } else {
                $("#allow_private_data_export_stats").hide();
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

    void channel.get({
        url: "/json/export/realm/consents",
        success(raw_data) {
            const data = z
                .object({export_consents: z.array(export_consent_schema)})
                .parse(raw_data);
            total_users_count = data.export_consents.length;
            users_consented_for_export_count = data.export_consents.filter(
                (export_consent) => export_consent.consented,
            ).length;
        },
    });

    $("#start-export-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        show_start_export_modal();
    });

    // Do an initial population of the table
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
        const $btn = $(this);
        const url = "/json/export/realm/" + encodeURIComponent($btn.attr("data-export-id")!);
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
