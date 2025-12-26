import $ from "jquery";
import type * as z from "zod/mini";

import render_confirm_delete_attachment from "../templates/confirm_dialog/confirm_delete_attachment.hbs";
import render_confirm_delete_detached_attachments_modal from "../templates/confirm_dialog/confirm_delete_detached_attachments.hbs";
import render_uploaded_files_list from "../templates/settings/uploaded_files_list.hbs";

import {attachment_api_response_schema} from "./attachments.ts";
import * as banners from "./banners.ts";
import type {ActionButton} from "./buttons.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as ListWidget from "./list_widget.ts";
import * as loading from "./loading.ts";
import * as scroll_util from "./scroll_util.ts";
import {message_edit_history_visibility_policy_values} from "./settings_config.ts";
import * as settings_config from "./settings_config.ts";
import {current_user, realm} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";

type ServerAttachment = z.infer<typeof attachment_api_response_schema>["attachments"][number];

type Attachment = ServerAttachment & {
    create_time_str: string;
    size_str: string;
};

type AttachmentEvent =
    | {
          op: "add" | "update";
          attachment: ServerAttachment;
          upload_space_used: number;
      }
    | {
          op: "remove";
          attachment: {id: number};
          upload_space_used: number;
      };

let attachments: Attachment[];
let upload_space_used: z.infer<typeof attachment_api_response_schema>["upload_space_used"];

export function bytes_to_size(bytes: number, kb_with_1024_bytes = false): string {
    const kb_size = kb_with_1024_bytes ? 1024 : 1000;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    if (bytes === 0) {
        return "0 B";
    }
    const i = Math.trunc(Math.log(bytes) / Math.log(kb_size));
    let size = Math.round(bytes / Math.pow(kb_size, i));
    if (i > 0 && size < 10) {
        size = Math.round((bytes / Math.pow(kb_size, i)) * 10) / 10;
    }
    return size + " " + sizes[i];
}

export function mib_to_bytes(mib: number): number {
    return mib * 1024 * 1024;
}

export function percentage_used_space(uploads_size: number): string | null {
    if (realm.realm_upload_quota_mib === null) {
        return null;
    }
    return ((100 * uploads_size) / mib_to_bytes(realm.realm_upload_quota_mib)).toFixed(1);
}

function set_upload_space_stats(): void {
    if (realm.realm_upload_quota_mib === null) {
        return;
    }
    if (current_user.is_guest) {
        return;
    }

    const show_upgrade_message =
        realm.realm_plan_type === settings_config.realm_plan_types.limited.code &&
        current_user.is_admin;
    const $container = $("#attachment-stats-holder");

    if (!$container) {
        return;
    }

    let buttons: ActionButton[] = [];
    if (show_upgrade_message) {
        buttons = [
            ...buttons,
            {
                label: $t({defaultMessage: "Upgrade"}),
                custom_classes: "request-upgrade",
                attention: "quiet",
            },
        ];
    }

    const UPLOAD_STATS_BANNER: banners.Banner = {
        intent: show_upgrade_message ? "info" : "neutral",
        label: $t(
            {
                defaultMessage:
                    "Your organization is using {percent_used}% of your {upload_quota} file storage quota. Upgrade for more space.",
            },
            {
                percent_used: percentage_used_space(upload_space_used),
                upload_quota: bytes_to_size(mib_to_bytes(realm.realm_upload_quota_mib), true),
            },
        ),
        buttons,
        close_button: false,
    };

    banners.open(UPLOAD_STATS_BANNER, $container);
}

function delete_attachments(attachment: string, file_name: string): void {
    const html_body = render_confirm_delete_attachment({file_name});

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Delete file?"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Delete"}),
        focus_submit_on_open: true,
        on_click() {
            dialog_widget.submit_api_request(channel.del, "/json/attachments/" + attachment, {});
        },
        loading_spinner: true,
    });
}

function sort_mentioned_in(a: Attachment, b: Attachment): number {
    const a_m = a.messages[0];
    const b_m = b.messages[0];

    if (!a_m) {
        return 1;
    }
    if (!b_m) {
        return -1;
    }

    if (a_m.id > b_m.id) {
        return 1;
    } else if (a_m.id === b_m.id) {
        return 0;
    }

    return -1;
}

function render_attachments_ui(): void {
    set_upload_space_stats();

    const $uploaded_files_table = $("#uploaded_files_table").expectOne();
    const $search_input = $<HTMLInputElement>("input#upload_file_search");

    ListWidget.create<Attachment>($uploaded_files_table, attachments, {
        name: "uploaded-files-list",
        get_item: ListWidget.default_get_item,
        modifier_html(attachment) {
            return render_uploaded_files_list({attachment});
        },
        filter: {
            $element: $search_input,
            predicate(item, value) {
                return item.name.toLocaleLowerCase().includes(value);
            },
            onupdate() {
                scroll_util.reset_scrollbar(
                    $uploaded_files_table.closest(".progressive-table-wrapper"),
                );
            },
        },
        $parent_container: $("#attachments-settings").expectOne(),
        init_sort: "create_time_numeric",
        initially_descending_sort: true,
        sort_fields: {
            mentioned_in: sort_mentioned_in,
            ...ListWidget.generic_sort_functions("alphabetic", ["name"]),
            ...ListWidget.generic_sort_functions("numeric", ["create_time", "size"]),
        },
        $simplebar_container: $("#attachments-settings .progressive-table-wrapper"),
    });

    scroll_util.reset_scrollbar($uploaded_files_table.closest(".progressive-table-wrapper"));
}

function format_attachment_data(attachment: ServerAttachment): Attachment {
    return {
        ...attachment,
        create_time_str: timerender.render_now(new Date(attachment.create_time * 1000)).time_str,
        size_str: bytes_to_size(attachment.size),
    };
}

export function update_attachments(event: AttachmentEvent): void {
    if (attachments === undefined) {
        // If we haven't fetched attachment data yet, there's nothing to do.
        return;
    }
    if (event.op === "remove" || event.op === "update") {
        attachments = attachments.filter((a) => a.id !== event.attachment.id);
    }
    if (event.op === "add" || event.op === "update") {
        attachments.push(format_attachment_data(event.attachment));
    }
    upload_space_used = event.upload_space_used;
    // TODO: This is inefficient and we should be able to do some sort
    // of incremental ListWidget update instead.
    render_attachments_ui();
}

export function set_up_attachments(): void {
    // The settings page must be rendered before this function gets called.

    const $status = $("#delete-upload-status");
    loading.make_indicator($("#attachments_loading_indicator"), {
        text: $t({defaultMessage: "Loading…"}),
    });

    $("#uploaded_files_table").on("click", ".download-attachment", function () {
        $(this).siblings(".hidden-attachment-download")[0]?.click();
    });

    $("#uploaded_files_table").on("click", ".remove-attachment", (e) => {
        const file_name = $(e.target).closest(".uploaded_file_row").attr("data-attachment-name");
        delete_attachments(
            $(e.target).closest(".uploaded_file_row").attr("data-attachment-id")!,
            file_name!,
        );
    });

    void channel.get({
        url: "/json/attachments",
        success(raw_data) {
            const data = attachment_api_response_schema.parse(raw_data);
            loading.destroy_indicator($("#attachments_loading_indicator"));
            attachments = data.attachments.map((attachment) => format_attachment_data(attachment));
            upload_space_used = data.upload_space_used;
            render_attachments_ui();
        },
        error(xhr) {
            loading.destroy_indicator($("#attachments_loading_indicator"));
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $status);
        },
    });
}

export function suggest_delete_detached_attachments(attachments_list: ServerAttachment[]): void {
    const html_body = render_confirm_delete_detached_attachments_modal({
        attachments_list,
        realm_message_edit_history_is_visible:
            realm.realm_message_edit_history_visibility_policy !==
            message_edit_history_visibility_policy_values.never.code,
    });

    // Since we want to delete multiple attachments, we want to be
    // able to keep track of attachments to delete and which ones to
    // retry if it fails.
    const attachments_map = new Map<number, ServerAttachment>();
    for (const attachment of attachments_list) {
        attachments_map.set(attachment.id, attachment);
    }

    function do_delete_attachments(): void {
        dialog_widget.show_dialog_spinner();
        for (const [id, attachment] of attachments_map.entries()) {
            void channel.del({
                url: "/json/attachments/" + attachment.id,
                success() {
                    attachments_map.delete(id);
                    if (attachments_map.size === 0) {
                        dialog_widget.hide_dialog_spinner();
                        dialog_widget.close();
                    }
                },
                error() {
                    dialog_widget.hide_dialog_spinner();
                    ui_report.error(
                        $t_html({defaultMessage: "One or more files could not be deleted."}),
                        undefined,
                        $("#dialog_error"),
                    );
                },
            });
        }
        // This is to open "Manage uploaded files" link.
        $("#confirm_delete_attachments_modal .uploaded_files_settings_link").on("click", (e) => {
            e.stopPropagation();
            dialog_widget.close();
        });
    }

    dialog_widget.launch({
        id: "confirm_delete_attachments_modal",
        html_heading: $t_html({defaultMessage: "Delete uploaded files?"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Delete"}),
        html_exit_button: $t_html({defaultMessage: "Don't delete"}),
        loading_spinner: true,
        on_click: do_delete_attachments,
    });
}
