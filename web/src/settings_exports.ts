import $ from "jquery";
import {z} from "zod";

import render_confirm_delete_data_export from "../templates/confirm_dialog/confirm_delete_data_export.hbs";
import render_admin_export_list from "../templates/settings/admin_export_list.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";

const realm_export_schema = z.object({
    id: z.number(),
    export_time: z.number(),
    acting_user_id: z.number(),
    export_url: z.string().nullable(),
    deleted_timestamp: z.number().nullable(),
    failed_timestamp: z.number().nullable(),
    pending: z.boolean(),
});
type RealmExport = z.output<typeof realm_export_schema>;

const meta = {
    loaded: false,
};

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

export function set_up(): void {
    meta.loaded = true;

    $("#export-data").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const $export_status = $("#export_status");

        void channel.post({
            url: "/json/export/realm",
            success() {
                ui_report.success(
                    $t_html({defaultMessage: "Export started. Check back in a few minutes."}),
                    $export_status,
                    4000,
                );
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Export failed"}), xhr, $export_status);
            },
        });
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
