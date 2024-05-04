import $ from "jquery";
import {z} from "zod";

import render_confirm_delete_attachment from "../templates/confirm_dialog/confirm_delete_attachment.hbs";
import render_settings_upload_space_stats from "../templates/settings/upload_space_stats.hbs";
import render_uploaded_files_list from "../templates/settings/uploaded_files_list.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as ListWidget from "./list_widget";
import * as loading from "./loading";
import * as scroll_util from "./scroll_util";
import {realm} from "./state_data";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";

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

const attachment_api_response_schema = z.object({
    attachments: z.array(
        z.object({
            id: z.number(),
            name: z.string(),
            path_id: z.string(),
            size: z.number(),
            create_time: z.number(),
            messages: z.array(
                z.object({
                    id: z.number(),
                    date_sent: z.number(),
                }),
            ),
        }),
    ),
    upload_space_used: z.number(),
});

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
    const args = {
        show_upgrade_message: realm.realm_plan_type === 2,
        percent_used: percentage_used_space(upload_space_used),
        upload_quota: bytes_to_size(mib_to_bytes(realm.realm_upload_quota_mib), true),
    };
    const rendered_upload_stats_html = render_settings_upload_space_stats(args);
    $("#attachment-stats-holder").html(rendered_upload_stats_html);
}

function delete_attachments(attachment: string, file_name: string): void {
    const html_body = render_confirm_delete_attachment({file_name});

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Delete file?"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Delete"}),
        id: "confirm_delete_file_modal",
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

function format_attachment_data(new_attachments: ServerAttachment[]): Attachment[] {
    return new_attachments.map((attachment) => ({
        ...attachment,
        create_time_str: timerender.render_now(new Date(attachment.create_time)).time_str,
        size_str: bytes_to_size(attachment.size),
    }));
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
        attachments.push(format_attachment_data([event.attachment])[0]);
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

    $("#uploaded_files_table").on("click", ".remove-attachment", (e) => {
        const file_name = $(e.target).closest(".uploaded_file_row").attr("id");
        delete_attachments(
            $(e.target).closest(".uploaded_file_row").attr("data-attachment-id")!,
            file_name!,
        );
    });

    void channel.get({
        url: "/json/attachments",
        success(data) {
            const clean_data = attachment_api_response_schema.parse(data);
            loading.destroy_indicator($("#attachments_loading_indicator"));
            attachments = format_attachment_data(clean_data.attachments);
            upload_space_used = clean_data.upload_space_used;
            render_attachments_ui();
        },
        error(xhr) {
            loading.destroy_indicator($("#attachments_loading_indicator"));
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $status);
        },
    });
}
