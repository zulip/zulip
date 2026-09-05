import {$} from "jquery";
import assert from "minimalistic-assert";

import * as channel from "./channel.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import {csrf_token} from "./csrf.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t_html} from "./i18n.ts";
import * as people from "./people.ts";
import * as settings_data from "./settings_data.ts";
import {current_user, realm} from "./state_data.ts";
import * as ui_report from "./ui_report.ts";
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

export function build_bot_edit_widget($target: JQuery): UploadWidget {
    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $target.find<HTMLInputElement>(".edit_bot_avatar_file_input");
    };

    const $file_name_field = $target.find(".edit_bot_avatar_file");
    const $input_error = $target.find(".edit_bot_avatar_error");
    const $clear_button = $target.find(".edit_bot_avatar_clear_button");
    const $upload_button = $target.find(".edit_bot_avatar_upload_button");
    const $preview_text = $target.find(".edit_bot_avatar_preview_text");
    const $preview_image = $target.find(".edit_bot_avatar_preview_image");

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

export function hide_avatar_spinner(): void {
    $("#user-avatar-upload-widget .upload-spinner-background").css({visibility: "hidden"});
    $("#user-avatar-upload-widget .image-upload-text").show();
}

export function show_avatar_spinner(): void {
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
            // Start the spinner early because popup closes before success is received.
            show_avatar_spinner();
            void channel.del({
                url: "/json/users/me/avatar",
                success() {
                    // Need to clear input because of a small edge case
                    // where you try to upload the same image you just deleted.
                    get_file_input().val("");
                    // Rest of the work is done via the user_events -> avatar_url event we will get
                },
                error() {
                    hide_avatar_spinner();
                    $("#user-avatar-upload-widget .image-delete-button").toggle(
                        current_user.avatar_source === "U",
                    );
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

// This widget lives inside the Manage user modal, and only one modal can be
// open at a time. So opening the confirm dialog or the image cropper
// closes it. Both reopen the profile when they close, the closing animation must
// fully play before the modal can reopen, which creates the timing constraints
// handled below:
//
// * The avatar_url event can arrive while the widget is closed, ex:
//   while the cropper or confirm dialog is open or is closing.
//   update_admin_user_avatar_widget does nothing then, which is safe: the
//   reopened modal renders current data from people.
//
// * The event can arrive before we decide whether to show a spinner. We
//   compare avatar_version to detect that, since a spinner shown after the
//   update has already landed would never be hidden.
//
// * The request can fail before the modal finishes closing, so in_transit
//   tracks whether one is still outstanding.
//
// * The spinner is hidden by a load listener on the avatar img, attached after
//   the src is assigned so it waits on the new avatar.
export function build_admin_user_avatar_widget(
    user_id: number,
    on_hidden_callback: () => void,
): void {
    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $<HTMLInputElement>(
            "#admin-user-avatar-upload-widget input.image_file_input",
        ).expectOne();
    };

    const user = people.get_by_user_id(user_id);

    if (user.avatar_source !== "U") {
        $("#admin-user-avatar-upload-widget .image-delete-button").hide();
    }
    $("#admin-user-avatar-upload-widget .image-delete-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        let previous_version: number;
        let in_transit = false;
        confirm_dialog.launch({
            modal_title_html: $t_html({defaultMessage: "Delete profile picture"}),
            modal_content_html: $t_html({
                defaultMessage: "Are you sure you want to delete this profile picture?",
            }),
            is_compact: true,
            on_click() {
                in_transit = true;
                previous_version = user.avatar_version;
                // delete_admin_user_avatar cannot see in_transit,
                // so the caller passes in the flag to run on failure.
                delete_admin_user_avatar(user_id, () => {
                    in_transit = false;
                    // The failure can also arrive after on_hidden already
                    // showed the spinner, and no event will come to hide it.
                    hide_admin_user_spinner(user.avatar_source);
                });
            },
            on_hidden() {
                on_hidden_callback();
                // Skip the spinner if the event already arrived
                // or the request already failed (nothing will arrive).
                if (previous_version === user.avatar_version && in_transit) {
                    show_admin_user_spinner();
                }
            },
        });
    });

    upload_widget.build_direct_upload_widget(
        get_file_input,
        $("#admin-user-avatar-upload-widget-error").expectOne(),
        $("#admin-user-avatar-upload-widget .image_upload_button").expectOne(),
        (file) => {
            upload_admin_user_avatar(user_id, file);
        },
        realm.max_avatar_file_size_mib,
        "user_avatar",
        on_hidden_callback,
    );
}

function hide_admin_user_spinner(avatar_source: string | undefined): void {
    $("#admin-user-avatar-upload-widget .upload-spinner-background").css({visibility: "hidden"});
    $("#admin-user-avatar-upload-widget .image-upload-text").show();
    if (avatar_source === "U") {
        $("#admin-user-avatar-upload-widget .image-delete-button").show();
    }
}

function show_admin_user_spinner(): void {
    const $avatar_img = $<HTMLImageElement>("#admin-user-avatar-upload-widget .image-block");
    $avatar_img.off(".avatar_img");
    $("#admin-user-avatar-upload-widget .upload-spinner-background").css({visibility: "visible"});
    $("#admin-user-avatar-upload-widget .image-upload-text").hide();
    $("#admin-user-avatar-upload-widget .image-delete-button").hide();
}

function upload_admin_user_avatar(user_id: number, file: File): void {
    const form_data = new FormData();

    assert(csrf_token !== undefined);
    form_data.append("csrfmiddlewaretoken", csrf_token);
    form_data.append("file", file);
    $("#admin-user-avatar-upload-widget-error").hide();

    const user = people.get_by_user_id(user_id);
    const previous_version = user.avatar_version;

    channel.post({
        url: "/json/users/" + encodeURIComponent(user_id) + "/avatar",
        data: form_data,
        cache: false,
        processData: false,
        contentType: false,
        success() {
            dialog_widget.close(() => {
                // If the event already landed, the widget is correct and a
                // spinner would never be hidden.
                if (previous_version === user.avatar_version) {
                    show_admin_user_spinner();
                    // Matches settings_account.upload_avatar, which reveals
                    // the delete button on success.
                    $("#admin-user-avatar-upload-widget .image-delete-button").show();
                }
            });
        },
        error(xhr) {
            ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
            dialog_widget.hide_dialog_spinner();
        },
    });
}

function delete_admin_user_avatar(user_id: number, error_callback: () => void): void {
    channel.del({
        url: "/json/users/" + encodeURIComponent(user_id) + "/avatar",
        error: error_callback,
    });
}

export function update_admin_user_avatar_widget(
    avatar_url_medium: string,
    avatar_source: string | undefined,
    user_id: number,
): void {
    if (
        $("#admin-user-avatar-upload-widget").length === 1 &&
        $("#edit-user-form").attr("data-user-id") === user_id.toString()
    ) {
        // Use a listener to remove the loading spinner when we update the image src it 
        // disappears when the image is ready to actually show.
        $("#admin-user-avatar-upload-widget .image-block").attr("src", avatar_url_medium);
        $("#admin-user-avatar-upload-widget .image-delete-button").toggle(avatar_source === "U");
        const $avatar_img = $<HTMLImageElement>("#admin-user-avatar-upload-widget .image-block");
        $avatar_img.off(".avatar_img");
        $avatar_img.one("load.avatar_img error.avatar_img", () => {
            hide_admin_user_spinner(avatar_source);
        });
    }
}
