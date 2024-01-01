import $ from "jquery";

import * as channel from "./channel";
import {state_data} from "./state_data";
import * as upload_widget from "./upload_widget";
import type {UploadFunction} from "./upload_widget";

export function build_realm_icon_widget(upload_function: UploadFunction): void {
    const get_file_input = function (): JQuery<HTMLInputElement> {
        return $<HTMLInputElement>("#realm-icon-upload-widget .image_file_input").expectOne();
    };

    if (!state_data.is_admin) {
        return;
    }
    if (state_data.realm_icon_source === "G") {
        $("#realm-icon-upload-widget .image-delete-button").hide();
    } else {
        $("#realm-icon-upload-widget .image-delete-button").show();
    }
    $("#realm-icon-upload-widget .image-delete-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        void channel.del({
            url: "/json/realm/icon",
        });
    });

    upload_widget.build_direct_upload_widget(
        get_file_input,
        $("#realm-icon-upload-widget .image_file_input_error").expectOne(),
        $("#realm-icon-upload-widget .image_upload_button").expectOne(),
        upload_function,
        state_data.max_icon_file_size_mib,
    );
}

export function rerender(): void {
    $("#realm-icon-upload-widget .image-block").attr("src", state_data.realm_icon_url);
    if (state_data.realm_icon_source === "U") {
        $("#realm-icon-upload-widget .image-delete-button").show();
    } else {
        $("#realm-icon-upload-widget .image-delete-button").hide();
        // Need to clear input because of a small edge case
        // where you try to upload the same image you just deleted.
        const $file_input = $("#realm-icon-upload-widget .image_file_input");
        $file_input.val("");
    }
}
