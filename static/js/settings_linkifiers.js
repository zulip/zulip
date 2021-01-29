"use strict";

const render_admin_filter_list = require("../templates/admin_filter_list.hbs");

const meta = {
    loaded: false,
};

exports.reset = function () {
    meta.loaded = false;
};

exports.maybe_disable_widgets = function () {
    if (page_params.is_admin) {
        return;
    }
};

function compare_by_index(a, b, i) {
    if (a[i] > b[i]) {
        return 1;
    } else if (a[i] === b[i]) {
        return 0;
    }
    return -1;
}

function sort_pattern(a, b) {
    return compare_by_index(a, b, 0);
}

function sort_url(a, b) {
    return compare_by_index(a, b, 1);
}

exports.populate_filters = function (filters_data) {
    if (!meta.loaded) {
        return;
    }

    const filters_table = $("#admin_filters_table").expectOne();
    ListWidget.create(filters_table, filters_data, {
        name: "linkifiers_list",
        modifier(filter) {
            return render_admin_filter_list({
                filter: {
                    pattern: filter[0],
                    url_format_string: filter[1],
                    id: filter[2],
                },
                can_modify: page_params.is_admin,
            });
        },
        filter: {
            element: filters_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                return (
                    item[0].toLowerCase().includes(value) || item[1].toLowerCase().includes(value)
                );
            },
            onupdate() {
                ui.reset_scrollbar(filters_table);
            },
        },
        parent_container: $("#filter-settings").expectOne(),
        init_sort: [sort_pattern],
        sort_fields: {
            pattern: sort_pattern,
            url: sort_url,
        },
        simplebar_container: $("#filter-settings .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_filters_loading_indicator"));
};

exports.set_up = function () {
    exports.build_page();
    exports.maybe_disable_widgets();
};

exports.build_page = function () {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($("#admin_page_filters_loading_indicator"));

    // Populate filters table
    exports.populate_filters(page_params.realm_filters);

    $(".admin_filters_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = $(this);

        channel.del({
            url: "/json/realm/filters/" + encodeURIComponent(btn.attr("data-filter-id")),
            error(xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            success() {
                const row = btn.parents("tr");
                row.remove();
            },
        });
    });

    $(".organization form.admin-filter-form")
        .off("submit")
        .on("submit", function (e) {
            e.preventDefault();
            e.stopPropagation();
            const filter_status = $("#admin-filter-status");
            const pattern_status = $("#admin-filter-pattern-status");
            const format_status = $("#admin-filter-format-status");
            const add_filter_button = $(".new-filter-form button");
            add_filter_button.prop("disabled", true);
            filter_status.hide();
            pattern_status.hide();
            format_status.hide();
            const filter = {};

            for (const obj of $(this).serializeArray()) {
                filter[obj.name] = obj.value;
            }

            channel.post({
                url: "/json/realm/filters",
                data: $(this).serialize(),
                success(data) {
                    $("#filter_pattern").val("");
                    $("#filter_format_string").val("");
                    add_filter_button.prop("disabled", false);
                    filter.id = data.id;
                    ui_report.success(i18n.t("Custom filter added!"), filter_status);
                },
                error(xhr) {
                    const errors = JSON.parse(xhr.responseText).errors;
                    add_filter_button.prop("disabled", false);
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

window.settings_linkifiers = exports;
