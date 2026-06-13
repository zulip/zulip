import $ from "jquery";

import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import {$t_html} from "./i18n.ts";
import * as modals from "./modals.ts";
import * as settings_data from "./settings_data.ts";
import {current_user, realm} from "./state_data.ts";
import * as upload_widget from "./upload_widget.ts";
import type {UploadFunction, UploadWidget} from "./upload_widget.ts";

export function build_bot_create_widget(): UploadWidget {
    // We have to do strange gyrations with the file input to clear it,
    // where we replace it wholesale, so we generalize the file input with
    // a callback function.
    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $("#bot_avatar_file_input");
    };

    const $file_name_field = $("#bot_avatar_file");
    const $input_error = $("#bot_avatar_file_input_error");
    const $clear_button = $("#bot_avatar_clear_button");
    const $upload_button = $("#bot_avatar_upload_button");
    const $preview_text = $("#add_bot_preview_text");
    const $preview_image = $("#add_bot_preview_image");
    return upload_widget.build_widget(
        get_file_input,
        $file_name_field,
        $input_error,
        $clear_button,
        $upload_button,
        $preview_text,
        $preview_image,
    );
}

export function build_bot_edit_widget(upload_function: UploadFunction): void {
    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $<HTMLInputElement>("#bot-avatar-upload-widget input.image_file_input").expectOne();
    };

    const $input_error = $(".edit_bot_avatar_error").expectOne();
    const $upload_button = $("#bot-avatar-upload-widget .image_upload_button").expectOne();

    get_file_input().on("change", (e) => {
        const file = e.target.files?.[0];
        if (!file) {
            return;
        }
        // Must be registered before build_direct_upload_widget's handler.
        e.stopImmediatePropagation();
        const $file_input = get_file_input();
        modals.close("user-profile-modal", {
            on_hidden() {
                upload_widget.open_uppy_editor(
                    file,
                    "bot_avatar",
                    $file_input,
                    $upload_button,
                    upload_function,
                );
            },
        });
    });

    upload_widget.build_direct_upload_widget(
        get_file_input,
        $input_error,
        $upload_button,
        upload_function,
        realm.max_avatar_file_size_mib,
        "bot_avatar",
    );
}

function display_avatar_delete_complete(): void {
    $("#user-avatar-upload-widget .upload-spinner-background").css({visibility: "hidden"});
    $("#user-avatar-upload-widget .image-upload-text").show();
}

function display_avatar_delete_started(): void {
    $("#user-avatar-upload-widget .upload-spinner-background").css({visibility: "visible"});
    $("#user-avatar-upload-widget .image-upload-text").hide();
    $("#user-avatar-upload-widget .image-delete-button").hide();
}

export function build_user_avatar_widget(upload_function: UploadFunction): void {
    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $<HTMLInputElement>("#user-avatar-upload-widget input.image_file_input").expectOne();
    };

    if (current_user.avatar_source !== "U") {
        $("#user-avatar-upload-widget .image-delete-button").hide();
    }

    if (current_user.avatar_source === "G") {
        $("#user-avatar-source").show();
    } else {
        $("#user-avatar-source").hide();
    }

    if (!settings_data.user_can_change_avatar()) {
        return;
    }

    $("#user-avatar-upload-widget .image-delete-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        function delete_user_avatar(): void {
            display_avatar_delete_started();
            void channel.del({
                url: "/json/users/me/avatar",
                success() {
                    display_avatar_delete_complete();

                    // Need to clear input because of a small edge case
                    // where you try to upload the same image you just deleted.
                    get_file_input().val("");
                    // Rest of the work is done via the user_events -> avatar_url event we will get
                },
                error() {
                    display_avatar_delete_complete();
                    $("#user-avatar-upload-widget .image-delete-button").show();
                },
            });
        }

        confirm_dialog.launch({
            modal_title_html: $t_html({defaultMessage: "Delete profile picture"}),
            modal_content_html: $t_html({
                defaultMessage: "Are you sure you want to delete your profile picture?",
            }),
            is_compact: true,
            on_click: delete_user_avatar,
        });
    });

    upload_widget.build_direct_upload_widget(
        get_file_input,
        $("#user-avatar-upload-widget-error").expectOne(),
        $("#user-avatar-upload-widget .image_upload_button").expectOne(),
        upload_function,
        realm.max_avatar_file_size_mib,
        "user_avatar",
    );
}
