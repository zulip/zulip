var settings_filters = (function () {

var exports = {};

var meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.populate_filters = function (filters_data) {
    if (!meta.loaded) {
        return;
    }

    var filters_table = $("#admin_filters_table").expectOne();
    filters_table.find("tr.filter_row").remove();
    _.each(filters_data, function (filter) {
        filters_table.append(
            templates.render(
                "admin_filter_list", {
                    filter: {
                        pattern: filter[0],
                        url_format_string: filter[1],
                        id: filter[2],
                    },
                    can_modify: page_params.is_admin,
                }
            )
        );
    });
    loading.destroy_indicator($('#admin_page_filters_loading_indicator'));
};

exports.set_up = function () {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($('#admin_page_filters_loading_indicator'));

    // Populate filters table
    exports.populate_filters(page_params.realm_filters);

    $('.admin_filters_table').on('click', '.delete', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var btn = $(this);

        channel.del({
            url: '/json/realm/filters/' + encodeURIComponent(btn.attr('data-filter-id')),
            error: function (xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            success: function () {
                var row = btn.parents('tr');
                row.remove();
            },
        });
    });

    $(".organization form.admin-filter-form").off('submit').on('submit', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var filter_status = $('#admin-filter-status');
        var pattern_status = $('#admin-filter-pattern-status');
        var format_status = $('#admin-filter-format-status');
        var add_filter_button = $('.new-filter-form button');
        add_filter_button.attr("disabled", "disabled");
        filter_status.hide();
        pattern_status.hide();
        format_status.hide();
        var filter = {};
        _.each($(this).serializeArray(), function (obj) {
            filter[obj.name] = obj.value;
        });

        channel.post({
            url: "/json/realm/filters",
            data: $(this).serialize(),
            success: function (data) {
                $('#filter_pattern').val('');
                $('#filter_format_string').val('');
                add_filter_button.removeAttr("disabled");
                filter.id = data.id;
                ui_report.success(i18n.t("Custom filter added!"), filter_status);
            },
            error: function (xhr) {
                var errors = JSON.parse(xhr.responseText).errors;
                add_filter_button.removeAttr("disabled");
                if (errors.pattern !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.pattern});
                    ui_report.error(i18n.t("Failed"), xhr, pattern_status);
                }
                if (errors.url_format_string !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.url_format_string});
                    ui_report.error(i18n.t("Failed"), xhr, format_status);
                }
                if (errors.__all__ !== undefined) {
                    xhr.responseText = JSON.stringify({msg: errors.__all__});
                    ui_report.error(i18n.t("Failed"), xhr, filter_status);
                }
            },
        });
    });


};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings_filters;
}
