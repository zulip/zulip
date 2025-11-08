import $ from "jquery";
import assert from "minimalistic-assert";
import SortableJS from "sortablejs";
import * as z from "zod/mini";

import render_confirm_delete_linkifier from "../templates/confirm_dialog/confirm_delete_linkifier.hbs";
import render_admin_linkifier_edit_form from "../templates/settings/admin_linkifier_edit_form.hbs";
import render_admin_linkifier_list from "../templates/settings/admin_linkifier_list.hbs";

import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t_html} from "./i18n.ts";
import * as linkifiers from "./linkifiers.ts";
import * as ListWidget from "./list_widget.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_ui from "./settings_ui.ts";
import {current_user, realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";
import * as ui_util from "./ui_util.ts";
import * as util from "./util.ts";

type RealmLinkifiers = typeof realm.realm_linkifiers;

const meta = {
    loaded: false,
};

export function reset(): void {
    meta.loaded = false;
}

export function maybe_disable_widgets(): void {
    if (current_user.is_admin) {
        return;
    }
}

function open_linkifier_edit_form(linkifier_id: number): void {
    const linkifiers_list = realm.realm_linkifiers;
    const linkifier = linkifiers_list.find((linkifier) => linkifier.id === linkifier_id);
    assert(linkifier !== undefined);
    const html_body = render_admin_linkifier_edit_form({
        linkifier_id,
        pattern: linkifier.pattern,
        url_template: linkifier.url_template,
    });

    function submit_linkifier_form(dialog_widget_id: string): void {
        const $modal = $(`#${CSS.escape(dialog_widget_id)}`);
        const $change_linkifier_button = $modal.find(".dialog_submit_button");
        $change_linkifier_button.prop("disabled", true);

        const url = "/json/realm/filters/" + encodeURIComponent(linkifier_id);
        const pattern = $modal.find<HTMLInputElement>("input#edit-linkifier-pattern").val()!.trim();
        const url_template = $modal
            .find<HTMLInputElement>("input#edit-linkifier-url-template")
            .val()!
            .trim();
        const data = {pattern, url_template};
        const $pattern_status = $modal.find("#edit-linkifier-pattern-status").expectOne();
        const $template_status = $modal.find("#edit-linkifier-template-status").expectOne();
        const $dialog_error_element = $modal.find("#dialog_error").expectOne();
        const opts = {
            success_continuation() {
                $change_linkifier_button.prop("disabled", false);
                dialog_widget.close();
            },
            error_continuation(xhr: JQuery.jqXHR<unknown>) {
                $change_linkifier_button.prop("disabled", false);
                const parsed = z
                    .object({errors: z.record(z.string(), z.optional(z.array(z.string())))})
                    .safeParse(xhr.responseJSON);
                if (parsed.success) {
                    handle_linkifier_api_error(
                        parsed.data.errors,
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

    const dialog_widget_id = dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Edit linkfiers"}),
        html_body,
        on_click() {
            submit_linkifier_form(dialog_widget_id);
        },
        on_shown() {
            ui_util.place_caret_at_end(util.the($("#edit-linkifier-pattern")));
        },
    });
}

function update_linkifiers_order(): void {
    const order: number[] = [];
    $(".linkifier_row").each(function () {
        order.push(Number.parseInt($(this).attr("data-linkifier-id")!, 10));
    });
    settings_ui.do_settings_change(
        channel.patch,
        "/json/realm/linkifiers",
        {ordered_linkifier_ids: JSON.stringify(order)},
        $("#linkifier-field-status").expectOne(),
    );
}

function handle_linkifier_api_error(
    errors: Record<string, string[] | undefined>,
    pattern_status: JQuery,
    template_status: JQuery,
    linkifier_status: JQuery,
): void {
    // The endpoint uses the Django ValidationError system for error
    // handling, which returns somewhat complicated error
    // dictionaries. This logic parses them.
    if (errors.pattern !== undefined) {
        ui_report.error(
            $t_html({defaultMessage: "Failed: {error}"}, {error: errors.pattern[0]}),
            undefined,
            pattern_status,
        );
    }
    if (errors.url_template !== undefined) {
        ui_report.error(
            $t_html({defaultMessage: "Failed: {error}"}, {error: errors.url_template[0]}),
            undefined,
            template_status,
        );
    }
    if (errors.__all__ !== undefined) {
        ui_report.error(
            $t_html({defaultMessage: "Failed: {error}"}, {error: errors.__all__[0]}),
            undefined,
            linkifier_status,
        );
    }
}

export function populate_linkifiers(linkifiers_data: RealmLinkifiers): void {
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
                can_modify: current_user.is_admin,
                can_drag: filter_value.length === 0,
            });
        },
        filter: {
            $element: $linkifiers_table
                .closest(".settings-section")
                .find<HTMLInputElement>("input.search"),
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

    if (current_user.is_admin) {
        new SortableJS(util.the($linkifiers_table), {
            onUpdate: update_linkifiers_order,
            handle: ".move-handle",
            filter: "input",
            preventOnFilter: false,
        });
    }
}

export function set_up(): void {
    build_page();
    maybe_disable_widgets();
}

export function build_page(): void {
    meta.loaded = true;

    // Populate linkifiers table
    populate_linkifiers(realm.realm_linkifiers);

    $(".admin_linkifiers_table").on("click", ".delete", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const $button = $(this);
        const html_body = render_confirm_delete_linkifier();
        const url =
            "/json/realm/filters/" +
            encodeURIComponent($button.closest("tr").attr("data-linkifier-id")!);

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete linkifier?"}),
            html_body,
            id: "confirm_delete_linkifiers_modal",
            on_click() {
                dialog_widget.submit_api_request(channel.del, url, {});
            },
            loading_spinner: true,
        });
    });

    $(".admin_linkifiers_table").on("click", ".edit", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const $button = $(this);
        const linkifier_id = Number.parseInt($button.closest("tr").attr("data-linkifier-id")!, 10);
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

            const pattern = String($("#linkifier_pattern").val()).trim();
            const url_template = String($("#linkifier_template").val()).trim();

            try {
                linkifiers.python_to_js_linkifier(pattern, url_template);
            } catch {
                $add_linkifier_button.prop("disabled", false);
                ui_report.error(
                    $t_html({defaultMessage: "Failed: Invalid Pattern"}),
                    undefined,
                    $pattern_status,
                );
                return;
            }

            void channel.post({
                url: "/json/realm/filters",
                data: $(this).serialize(),
                success() {
                    $("#linkifier_pattern").val("");
                    $("#linkifier_template").val("");
                    $add_linkifier_button.prop("disabled", false);
                    ui_report.success(
                        $t_html({defaultMessage: "Custom linkifier added!"}),
                        $linkifier_status,
                    );
                },
                error(xhr) {
                    $add_linkifier_button.prop("disabled", false);
                    const parsed = z
                        .object({errors: z.record(z.string(), z.optional(z.array(z.string())))})
                        .safeParse(xhr.responseJSON);
                    if (parsed.success) {
                        handle_linkifier_api_error(
                            parsed.data.errors,
                            $pattern_status,
                            $template_status,
                            $linkifier_status,
                        );
                    }
                },
            });
        });
}
