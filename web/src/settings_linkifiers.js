import $ from "jquery";
import {Sortable} from "sortablejs";

import render_confirm_delete_linkifier from "../templates/confirm_dialog/confirm_delete_linkifier.hbs";
import render_admin_linkifier_edit_form from "../templates/settings/admin_linkifier_edit_form.hbs";
import render_admin_linkifier_list from "../templates/settings/admin_linkifier_list.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import {page_params} from "./page_params";
import * as scroll_util from "./scroll_util";
import * as settings_ui from "./settings_ui";
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

function open_linkifier_edit_form(linkifier_id) {
    const linkifiers_list = page_params.realm_linkifiers;
    const linkifier = linkifiers_list.find((linkifier) => linkifier.id === linkifier_id);
    const html_body = render_admin_linkifier_edit_form({
        linkifier_id,
        pattern: linkifier.pattern,
        url_template: linkifier.url_template,
    });

    function submit_linkifier_form() {
        const $change_linkifier_button = $(".dialog_submit_button");
        $change_linkifier_button.prop("disabled", true);

        const $modal = $("#dialog_widget_modal");
        const url = "/json/realm/filters/" + encodeURIComponent(linkifier_id);
        const pattern = $modal.find("#edit-linkifier-pattern").val().trim();
        const url_template = $modal.find("#edit-linkifier-url-template").val().trim();
        const data = {pattern, url_template};
        const $pattern_status = $modal.find("#edit-linkifier-pattern-status").expectOne();
        const $template_status = $modal.find("#edit-linkifier-template-status").expectOne();
        const $dialog_error_element = $modal.find("#dialog_error").expectOne();
        const opts = {
            success_continuation() {
                $change_linkifier_button.prop("disabled", false);
                dialog_widget.close_modal();
            },
            error_continuation(xhr) {
                $change_linkifier_button.prop("disabled", false);
                if (xhr.responseJSON?.errors) {
                    handle_linkifier_api_error(
                        xhr,
                        $pattern_status,
                        $template_status,
                        $dialog_error_element,
                    );
                } else {
                    // This must be `Linkifier not found` error.
                    ui_report.error(
                        $t_html({defaultMessage: "Failed"}),
                        xhr,
                        $dialog_error_element,
                    );
                }
            },
            // Show the error message only on edit linkifier modal.
            $error_msg_element: $(),
        };
        settings_ui.do_settings_change(
            channel.patch,
            url,
            data,
            $("#linkifier-field-status"),
            opts,
        );
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Edit linkfiers"}),
        html_body,
        on_click: submit_linkifier_form,
    });
}

function update_linkifiers_order() {
    const order = [];
    $(".linkifier_row").each(function () {
        order.push(Number.parseInt($(this).attr("data-linkifier-id"), 10));
    });
    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/linkifiers",
        {ordered_linkifier_ids: JSON.stringify(order)},
        $("#linkifier-field-status").expectOne(),
    );
}

function handle_linkifier_api_error(xhr, pattern_status, template_status, linkifier_status) {
    // The endpoint uses the Django ValidationError system for error
    // handling, which returns somewhat complicated error
    // dictionaries. This logic parses them.
    const errors = xhr.responseJSON.errors;
    if (errors.pattern !== undefined) {
        xhr.responseJSON.msg = errors.pattern;
        ui_report.error($t_html({defaultMessage: "Failed"}), xhr, pattern_status);
    }
    if (errors.url_template !== undefined) {
        xhr.responseJSON.msg = errors.url_template;
        ui_report.error($t_html({defaultMessage: "Failed"}), xhr, template_status);
    }
    if (errors.__all__ !== undefined) {
        xhr.responseJSON.msg = errors.__all__;
        ui_report.error($t_html({defaultMessage: "Failed"}), xhr, linkifier_status);
    }
}

export function populate_linkifiers(linkifiers_data) {
    if (!meta.loaded) {
        return;
    }

    const $linkifiers_table = $("#admin_linkifiers_table").expectOne();
    ListWidget.create($linkifiers_table, linkifiers_data, {
        name: "linkifiers_list",
        get_item: ListWidget.default_get_item,
        modifier_html(linkifier, filter_value) {
            return render_admin_linkifier_list({
                linkifier: {
                    pattern: linkifier.pattern,
                    url_template: linkifier.url_template,
                    id: linkifier.id,
                },
                can_modify: page_params.is_admin,
                can_drag: filter_value.length === 0,
            });
        },
        filter: {
            $element: $linkifiers_table.closest(".settings-section").find(".search"),
            predicate(item, value) {
                return (
                    item.pattern.toLowerCase().includes(value) ||
                    item.url_template.toLowerCase().includes(value)
                );
            },
            onupdate() {
                scroll_util.reset_scrollbar($linkifiers_table);
            },
        },
        $parent_container: $("#linkifier-settings").expectOne(),
        $simplebar_container: $("#linkifier-settings .progressive-table-wrapper"),
    });

    if (page_params.is_admin) {
        Sortable.create($linkifiers_table[0], {
            onUpdate: update_linkifiers_order,
            filter: "input",
            preventOnFilter: false,
        });
    }
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
        const $btn = $(this);
        const html_body = render_confirm_delete_linkifier();
        const url = "/json/realm/filters/" + encodeURIComponent($btn.attr("data-linkifier-id"));

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete linkifier?"}),
            html_body,
            id: "confirm_delete_linkifiers_modal",
            on_click: () => dialog_widget.submit_api_request(channel.del, url),
            loading_spinner: true,
        });
    });

    $(".admin_linkifiers_table").on("click", ".edit", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const $btn = $(this);
        const linkifier_id = Number.parseInt($btn.attr("data-linkifier-id"), 10);
        open_linkifier_edit_form(linkifier_id);
    });

    $(".organization form.admin-linkifier-form")
        .off("submit")
        .on("submit", function (e) {
            e.preventDefault();
            e.stopPropagation();
            const $linkifier_status = $("#admin-linkifier-status");
            const $pattern_status = $("#admin-linkifier-pattern-status");
            const $template_status = $("#admin-linkifier-template-status");
            const $add_linkifier_button = $(".new-linkifier-form button");
            $add_linkifier_button.prop("disabled", true);
            $linkifier_status.hide();
            $pattern_status.hide();
            $template_status.hide();
            const linkifier = {};

            for (const obj of $(this).serializeArray()) {
                linkifier[obj.name] = obj.value;
            }

            channel.post({
                url: "/json/realm/filters",
                data: $(this).serialize(),
                success(data) {
                    $("#linkifier_pattern").val("");
                    $("#linkifier_template").val("");
                    $add_linkifier_button.prop("disabled", false);
                    linkifier.id = data.id;
                    ui_report.success(
                        $t_html({defaultMessage: "Custom linkifier added!"}),
                        $linkifier_status,
                    );
                },
                error(xhr) {
                    $add_linkifier_button.prop("disabled", false);
                    if (xhr.responseJSON?.errors) {
                        handle_linkifier_api_error(
                            xhr,
                            $pattern_status,
                            $template_status,
                            $linkifier_status,
                        );
                    }
                },
            });
        });
}
