var render_admin_export_list = require('../templates/admin_export_list.hbs');

var settings_exports = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.clear_success_banner = function () {
    var export_status = $('#export_status');
    if (export_status.hasClass('alert-success')) {
        // Politely remove our success banner if the export
        // finishes before the view is closed.
        export_status.fadeTo(200, 0);
        setTimeout(function () {
            export_status.hide();
        }, 205);
    }
};

exports.populate_exports_table = function (exports) {
    if (!meta.loaded) {
        return;
    }

    var exports_table = $('#admin_exports_table').expectOne();
    var exports_list = list_render.create(exports_table, Object.values(exports), {
        name: "admin_exports_list",
        modifier: function (data) {
            if (data.export_data.deleted_timestamp === undefined) {
                return render_admin_export_list({
                    realm_export: {
                        id: data.id,
                        acting_user: people.get_full_name(data.acting_user_id),
                        // Convert seconds -> milliseconds
                        event_time: timerender.last_seen_status_from_date(
                            new XDate(data.export_time * 1000)
                        ),
                        path: data.export_data.export_path,
                    },
                });
            }
            return "";
        },
        filter: {
            element: exports_table.closest(".settings-section").find(".search"),
            callback: function (item, value) {
                return people.get_full_name(item.acting_user_id).toLowerCase().indexOf(value) >= 0;
            },
            onupdate: function () {
                ui.reset_scrollbar(exports_table);
            },
        },
        parent_container: $("#data-exports").expectOne(),
    }).init();

    exports_list.add_sort_function("user", function (a, b) {
        var a_name = people.get_full_name(a.acting_user_id).toLowerCase();
        var b_name = people.get_full_name(b.acting_user_id).toLowerCase();
        if (a_name > b_name) {
            return 1;
        } else if (a_name === b_name) {
            return 0;
        }
        return -1;
    });

    exports_list.sort("user");
};

exports.set_up = function () {
    meta.loaded = true;

    $("#export-data").on('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var export_status = $('#export_status');

        channel.post({
            url: '/json/export/realm',
            success: function () {
                ui_report.success(i18n.t("Export started. Check back in a few minutes."), export_status);
            },
            error: function (xhr) {
                ui_report.error(i18n.t("Export failed"), xhr, export_status);
            },
        });
    });

    // Do an initial population of the table
    channel.get({
        url: '/json/export/realm',
        success: function (data) {
            exports.populate_exports_table(data.exports);
        },
    });

    $('.admin_exports_table').on('click', '.delete', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var btn = $(this);

        channel.del({
            url: '/json/export/realm/' + encodeURIComponent(btn.attr('data-export-id')),
            error: function (xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            // No success function, since UI updates are done via server_events
        });
    });
};

return exports;
}());
if (typeof modules !== 'undefined') {
    module.exports = settings_exports;
}
window.settings_exports = settings_exports;
