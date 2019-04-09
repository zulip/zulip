var render_admin_export_list = require('../templates/admin_export_list.hbs');

var settings_exports = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.populate_exports_table = function (exports) {
    if (!meta.loaded) {
        return;
    }

    var exports_table = $('#admin_exports_table').expectOne();
    exports_table.find('tr.export_row').remove();
    _.each(exports, function (data) {
        if (data.export_data.deleted_timestamp === undefined) {
            exports_table.append(render_admin_export_list({
                realm_export: {
                    id: data.id,
                    acting_user: people.my_full_name(data.acting_user_id),
                    // Convert seconds -> milliseconds
                    event_time: timerender.last_seen_status_from_date(
                        new XDate(data.export_time * 1000)
                    ),
                    path: data.export_data.export_path,
                },
            }));
        }
    });
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
            success: function () {
                var row = btn.parents('tr');
                row.remove();
            },
        });
    });
};

return exports;
}());
if (typeof modules !== 'undefined') {
    module.exports = settings_exports;
}
window.settings_exports = settings_exports;
