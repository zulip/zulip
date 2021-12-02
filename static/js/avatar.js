import $ from "jquery";

import render_confirm_delete_user_avatar from "../templates/confirm_dialog/confirm_delete_user_avatar.hbs";

import * as channel from "./channel";
import * as confirm_dialog from "./confirm_dialog";
import {$t_html} from "./i18n";
import {page_params} from "./page_params";
import * as settings_data from "./settings_data";
import * as upload_widget from "./upload_widget";

export function build_bot_create_widget() {
    // We have to do strange gyrations with the file input to clear it,
    // where we replace it wholesale, so we generalize the file input with
    // a callback function.
    const get_file_input = function () {
        return $("#bot_avatar_file_input");
    };

    const file_name_field = $("#bot_avatar_file");
    const input_error = $("#bot_avatar_file_input_error");
    const clear_button = $("#bot_avatar_clear_button");
    const upload_button = $("#bot_avatar_upload_button");

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button,
    );
}

export function build_bot_edit_widget(target) {
    const get_file_input = function () {
        return target.find(".edit_bot_avatar_file_input");
    };

    const file_name_field = target.find(".edit_bot_avatar_file");
    const input_error = target.find(".edit_bot_avatar_error");
    const clear_button = target.find(".edit_bot_avatar_clear_button");
    const upload_button = target.find(".edit_bot_avatar_upload_button");

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button,
    );
}

function display_avatar_delete_complete() {
    $("#user-avatar-upload-widget .upload-spinner-background").css({visibility: "hidden"});
    $("#user-avatar-upload-widget .image-upload-text").show();
    $("#user-avatar-source").show();
}

function display_avatar_delete_started() {
    $("#user-avatar-upload-widget .upload-spinner-background").css({visibility: "visible"});
    $("#user-avatar-upload-widget .image-upload-text").hide();
    $("#user-avatar-upload-widget .image-delete-button").hide();
}

export function build_user_avatar_widget(upload_function) {
    const get_file_input = function () {
        return $("#user-avatar-upload-widget .image_file_input").expectOne();
    };

    if (page_params.avatar_source === "G") {
        $("#user-avatar-upload-widget .image-delete-button").hide();
        $("#user-avatar-source").show();
    } else {
        $("#user-avatar-source").hide();
    }

    $("#user-avatar-upload-widget .image-delete-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        function delete_user_avatar() {
            display_avatar_delete_started();
            channel.del({
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
        const html_body = render_confirm_delete_user_avatar();

        confirm_dialog.launch({
            html_heading: $t_html({defaultMessage: "Delete profile picture"}),
            html_body,
            on_click: delete_user_avatar,
        });
    });

    if (settings_data.user_can_change_avatar()) {
        return upload_widget.build_direct_upload_widget(
            get_file_input,
            $("#user-avatar-upload-widget .image_file_input_error").expectOne(),
            $("#user-avatar-upload-widget .image_upload_button").expectOne(),
            upload_function,
            page_params.max_avatar_file_size_mib,
        );
    }

    return undefined;
}
