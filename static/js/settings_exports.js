"use strict";

const XDate = require("xdate");

const render_admin_export_list = require("../templates/admin_export_list.hbs");

const people = require("./people");

const meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

function sort_user(a, b) {
    const a_name = people.get_full_name(a.acting_user_id).toLowerCase();
    const b_name = people.get_full_name(b.acting_user_id).toLowerCase();
    if (a_name > b_name) {
        return 1;
    } else if (a_name === b_name) {
        return 0;
    }
    return -1;
}

exports.populate_exports_table = function (exports) {
    if (!meta.loaded) {
        return;
    }

    const exports_table = $("#admin_exports_table").expectOne();
    list_render.create(exports_table, Object.values(exports), {
        name: "admin_exports_list",
        modifier(data) {
            let failed_timestamp = data.failed_timestamp;
            let deleted_timestamp = data.deleted_timestamp;

            if (failed_timestamp !== null) {
                failed_timestamp = timerender.last_seen_status_from_date(
                    new XDate(failed_timestamp * 1000),
                );
            }

            if (deleted_timestamp !== null) {
                deleted_timestamp = timerender.last_seen_status_from_date(
                    new XDate(deleted_timestamp * 1000),
                );
            }

            return render_admin_export_list({
                realm_export: {
                    id: data.id,
                    acting_user: people.get_full_name(data.acting_user_id),
                    // Convert seconds -> milliseconds
                    event_time: timerender.last_seen_status_from_date(
                        new XDate(data.export_time * 1000),
                    ),
                    url: data.export_url,
                    time_failed: failed_timestamp,
                    pending: data.pending,
                    time_deleted: deleted_timestamp,
                },
            });
        },
        filter: {
            element: exports_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                return people.get_full_name(item.acting_user_id).toLowerCase().includes(value);
            },
            onupdate() {
                ui.reset_scrollbar(exports_table);
            },
        },
        parent_container: $("#data-exports").expectOne(),
        init_sort: [sort_user],
        sort_fields: {
            user: sort_user,
        },
        simplebar_container: $("#data-exports .progressive-table-wrapper"),
    });

    const spinner = $(".export_row .export_url_spinner");
    if (spinner.length) {
        loading.make_indicator(spinner);
    } else {
        loading.destroy_indicator(spinner);
    }
};

exports.set_up = function () {
    meta.loaded = true;

    $("#export-data").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const export_status = $("#export_status");

        channel.post({
            url: "/json/export/realm",
            success() {
                ui_report.success(
                    i18n.t("Export started. Check back in a few minutes."),
                    export_status,
                    4000,
                );
            },
            error(xhr) {
                ui_report.error(i18n.t("Export failed"), xhr, export_status);
            },
        });
    });

    // Do an initial population of the table
    channel.get({
        url: "/json/export/realm",
        success(data) {
            exports.populate_exports_table(data.exports);
        },
    });

    $(".admin_exports_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = $(this);

        channel.del({
            url: "/json/export/realm/" + encodeURIComponent(btn.attr("data-export-id")),
            error(xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            // No success function, since UI updates are done via server_events
        });
    });
};

window.settings_exports = exports;
