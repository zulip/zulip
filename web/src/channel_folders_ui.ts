import $ from "jquery";
import * as z from "zod/mini";

import render_confirm_archive_channel_folder from "../templates/confirm_dialog/confirm_archive_channel_folder.hbs";
import render_create_channel_folder_modal from "../templates/stream_settings/create_channel_folder_modal.hbs";
import render_edit_channel_folder_modal from "../templates/stream_settings/edit_channel_folder_modal.hbs";

import * as channel from "./channel.ts";
import * as channel_folders from "./channel_folders.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t_html} from "./i18n.ts";
import * as people from "./people.ts";
import {realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";

export function add_channel_folder(): void {
    const html_body = render_create_channel_folder_modal({
        max_channel_folder_name_length: realm.max_channel_folder_name_length,
        max_channel_folder_description_length: realm.max_channel_folder_description_length,
    });

    function create_channel_folder(): void {
        const close_on_success = true;
        const data = {
            name: $<HTMLInputElement>("input#new_channel_folder_name").val()!.trim(),
            description: $<HTMLTextAreaElement>("textarea#new_channel_folder_description")
                .val()!
                .trim(),
        };
        dialog_widget.submit_api_request(
            channel.post,
            "/json/channel_folders/create",
            data,
            {
                success_continuation(response_data) {
                    const id = z
                        .object({channel_folder_id: z.number()})
                        .parse(response_data).channel_folder_id;
                    // This is a temporary channel folder object added
                    // to channel folders data, so that the folder is
                    // immediately visible in the dropdown.
                    // This will be replaced with the actual object once
                    // the client receives channel_folder/add event.
                    const channel_folder = {
                        id,
                        name: data.name,
                        description: data.description,
                        is_archived: false,
                        rendered_description: "",
                        date_created: 0,
                        creator_id: people.my_current_user_id(),
                        order: id,
                    };
                    channel_folders.add(channel_folder);
                },
            },
            close_on_success,
        );
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Create channel folder"}),
        html_body,
        id: "create_channel_folder",
        html_submit_button: $t_html({defaultMessage: "Create"}),
        on_click: create_channel_folder,
        loading_spinner: true,
        on_shown: () => $("#new_channel_folder_name").trigger("focus"),
    });
}

function archive_folder(folder_id: number): void {
    const stream_ids = channel_folders.get_stream_ids_in_folder(folder_id);
    let successful_requests = 0;

    function make_archive_folder_request(): void {
        const url = "/json/channel_folders/" + folder_id.toString();
        const data = {
            is_archived: JSON.stringify(true),
        };
        const opts = {
            success_continuation() {
                // Update the channel folders data so that
                // the folder dropdown shows only non-archived
                // folders immediately even if client receives
                // the update event after some delay.
                channel_folders.update_channel_folder(folder_id, "is_archived", true);
            },
        };
        dialog_widget.submit_api_request(channel.patch, url, data, opts);
    }

    if (stream_ids.length === 0) {
        make_archive_folder_request();
        return;
    }

    function remove_channel_from_folder(stream_id: number): void {
        const url = "/json/streams/" + stream_id.toString();
        const data = {
            folder_id: JSON.stringify(null),
        };
        void channel.patch({
            url,
            data,
            success() {
                successful_requests = successful_requests + 1;

                if (successful_requests === stream_ids.length) {
                    // Make request to archive folder only after all channels
                    // are removed from the folder.
                    make_archive_folder_request();
                }
            },
            error(xhr) {
                ui_report.error(
                    $t_html({
                        defaultMessage: "Failed removing one or more channels from the folder",
                    }),
                    xhr,
                    $("#dialog_error"),
                );
                dialog_widget.hide_dialog_spinner();
            },
        });
    }

    for (const stream_id of stream_ids) {
        remove_channel_from_folder(stream_id);
    }
}

export function handle_archiving_channel_folder(folder_id: number): void {
    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Delete channel folder?"}),
        html_body: render_confirm_archive_channel_folder(),
        on_click() {
            archive_folder(folder_id);
        },
        close_on_submit: false,
        loading_spinner: true,
    });
}

export function handle_editing_channel_folder(folder_id: number): void {
    const folder = channel_folders.get_channel_folder_by_id(folder_id);

    const html_body = render_edit_channel_folder_modal({
        name: folder.name,
        description: folder.description,
        max_channel_folder_name_length: realm.max_channel_folder_name_length,
        max_channel_folder_description_length: realm.max_channel_folder_description_length,
    });

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Edit channel folder"}),
        html_body,
        id: "edit_channel_folder",
        on_click() {
            const url = "/json/channel_folders/" + folder_id.toString();
            const new_name = $<HTMLInputElement>("input#edit_channel_folder_name").val()!.trim();
            const new_description = $<HTMLTextAreaElement>(
                "textarea#edit_channel_folder_description",
            )
                .val()!
                .trim();
            const data = {
                name: new_name,
                description: new_description,
            };
            const opts = {
                success_continuation() {
                    // Update the channel folders data so that
                    // the folder dropdown shows updated folder
                    // names immediately even if client receives
                    // the update event after some delay.
                    channel_folders.update_channel_folder(folder_id, "name", new_name);
                    channel_folders.update_channel_folder(
                        folder_id,
                        "description",
                        new_description,
                    );
                },
            };
            dialog_widget.submit_api_request(channel.patch, url, data, opts);
        },
        loading_spinner: true,
        on_shown: () => $("#edit_channel_folder_name").trigger("focus"),
        update_submit_disabled_state_on_change: true,
    });
}
