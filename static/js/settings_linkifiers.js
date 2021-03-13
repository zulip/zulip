import $ from "jquery";

import render_admin_linkifier_list from "../templates/admin_linkifier_list.hbs";

import * as channel from "./channel";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as ui from "./ui";
import * as ui_report from "./ui_report";

const meta = {
    loaded: false,
};

export function reset() {
    meta.loaded = false;
}

export function maybe_disable_widgets() {
    if (page_params.is_admin) {
        return;
    }
}

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

export function populate_linkifiers(linkifiers_data) {
    if (!meta.loaded) {
        return;
    }

    const linkifiers_table = $("#admin_linkifiers_table").expectOne();
    ListWidget.create(linkifiers_table, linkifiers_data, {
        name: "linkifiers_list",
        modifier(linkifier) {
            return render_admin_linkifier_list({
                linkifier: {
                    pattern: linkifier[0],
                    url_format_string: linkifier[1],
                    id: linkifier[2],
                },
                can_modify: page_params.is_admin,
            });
        },
        filter: {
            element: linkifiers_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                return (
                    item[0].toLowerCase().includes(value) || item[1].toLowerCase().includes(value)
                );
            },
            onupdate() {
                ui.reset_scrollbar(linkifiers_table);
            },
        },
        parent_container: $("#linkifier-settings").expectOne(),
        init_sort: [sort_pattern],
        sort_fields: {
            pattern: sort_pattern,
            url: sort_url,
        },
        simplebar_container: $("#linkifier-settings .progressive-table-wrapper"),
    });

    loading.destroy_indicator($("#admin_page_filters_loading_indicator"));
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

export function build_page() {
    meta.loaded = true;

    // create loading indicators
    loading.make_indicator($("#admin_page_filters_loading_indicator"));

    // Populate linkifiers table
    populate_linkifiers(page_params.realm_filters);

    $(".admin_linkifiers_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const btn = $(this);

        channel.del({
            url: "/json/realm/filters/" + encodeURIComponent(btn.attr("data-linkifier-id")),
            error(xhr) {
                ui_report.generic_row_button_error(xhr, btn);
            },
            success() {
                const row = btn.parents("tr");
                row.remove();
            },
        });
    });

    $(".organization form.admin-linkifier-form")
        .off("submit")
        .on("submit", function (e) {
            e.preventDefault();
            e.stopPropagation();
            const linkifier_status = $("#admin-linkifier-status");
            const pattern_status = $("#admin-linkifier-pattern-status");
            const format_status = $("#admin-linkifier-format-status");
            const add_linkifier_button = $(".new-linkifier-form button");
            add_linkifier_button.prop("disabled", true);
            linkifier_status.hide();
            pattern_status.hide();
            format_status.hide();
            const linkifier = {};

            for (const obj of $(this).serializeArray()) {
                linkifier[obj.name] = obj.value;
            }

            channel.post({
                url: "/json/realm/filters",
                data: $(this).serialize(),
                success(data) {
                    $("#linkifier_pattern").val("");
                    $("#linkifier_format_string").val("");
                    add_linkifier_button.prop("disabled", false);
                    linkifier.id = data.id;
                    ui_report.success(i18n.t("Custom linkifier added!"), linkifier_status);
                },
                error(xhr) {
                    const errors = JSON.parse(xhr.responseText).errors;
                    add_linkifier_button.prop("disabled", false);
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
                        ui_report.error(i18n.t("Failed"), xhr, linkifier_status);
                    }
                },
            });
        });
}
