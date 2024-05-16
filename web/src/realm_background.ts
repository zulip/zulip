import $ from "jquery";

import * as channel from "./channel";
import {current_user, realm} from "./state_data";
import * as upload_widget from "./upload_widget";
import type {UploadFunction} from "./upload_widget";

export function build_realm_background_widget(upload_function: UploadFunction): void {
    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $<HTMLInputElement>("#realm-background-upload-widget .image_file_input").expectOne();
    };

    if (!current_user.is_admin) {
        return;
    }
    if (realm.realm_background_source === "D") {
        $("#realm-background-upload-widget .image-delete-button").hide();
    } else {
        $("#realm-background-upload-widget .image-delete-button").show();
    }
    $("#realm-background-upload-widget .image-delete-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        void channel.del({
            url: "/json/realm/background",
        });
    });

    upload_widget.build_direct_upload_widget(
        get_file_input,
        $("#realm-background-upload-widget .image_file_input_error").expectOne(),
        $("#realm-background-upload-widget .image_upload_button").expectOne(),
        upload_function,
        realm.max_background_file_size_mib,
    );
}

export function rerender(): void {
    $("#realm-background-upload-widget .image-block").attr("src", realm.realm_background_url);
    if (realm.realm_background_source === "U") {
        $("#realm-background-upload-widget .image-delete-button").show();
    } else {
        $("#realm-background-upload-widget .image-delete-button").hide();
        // Need to clear input because of a small edge case
        // where you try to upload the same image you just deleted.
        const $file_input = $("#realm-background-upload-widget .image_file_input");
        $file_input.val("");
    }
}
