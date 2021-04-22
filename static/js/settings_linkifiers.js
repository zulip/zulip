import $ from "jquery";

import render_admin_linkifier_list from "../templates/settings/admin_linkifier_list.hbs";

import * as channel from "./channel";
import {$t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import {page_params} from "./page_params";
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

function compare_values(x, y) {
    if (x > y) {
        return 1;
    } else if (x === y) {
        return 0;
    }
    return -1;
}

function sort_pattern(a, b) {
    return compare_values(a.pattern, b.pattern);
}

function sort_url(a, b) {
    return compare_values(a.url_format, b.url_format);
}

function handle_linkifier_api_error(xhr, pattern_status, format_status, linkifier_status) {
    // The endpoint uses the Django ValidationError system for error
    // handling, which returns somewhat complicated error
    // dictionaries. This logic parses them.
    const errors = JSON.parse(xhr.responseText).errors;
    if (errors.pattern !== undefined) {
        xhr.responseText = JSON.stringify({msg: errors.pattern});
        ui_report.error($t_html({defaultMessage: "Failed"}), xhr, pattern_status);
    }
    if (errors.url_format_string !== undefined) {
        xhr.responseText = JSON.stringify({msg: errors.url_format_string});
        ui_report.error($t_html({defaultMessage: "Failed"}), xhr, format_status);
    }
    if (errors.__all__ !== undefined) {
        xhr.responseText = JSON.stringify({msg: errors.__all__});
        ui_report.error($t_html({defaultMessage: "Failed"}), xhr, linkifier_status);
    }
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
                    pattern: linkifier.pattern,
                    url_format_string: linkifier.url_format,
                    id: linkifier.id,
                },
                can_modify: page_params.is_admin,
            });
        },
        filter: {
            element: linkifiers_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                return (
                    item.pattern.toLowerCase().includes(value) ||
                    item.url_format.toLowerCase().includes(value)
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
}

export function set_up() {
    build_page();
    maybe_disable_widgets();
}

export function build_page() {
    meta.loaded = true;

    // Populate linkifiers table
    populate_linkifiers(page_params.realm_linkifiers);

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
                    ui_report.success(
                        $t_html({defaultMessage: "Custom linkifier added!"}),
                        linkifier_status,
                    );
                },
                error(xhr) {
                    add_linkifier_button.prop("disabled", false);
                    handle_linkifier_api_error(
                        xhr,
                        pattern_status,
                        format_status,
                        linkifier_status,
                    );
                },
            });
        });
}
