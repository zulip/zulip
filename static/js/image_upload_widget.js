import $ from "jquery";

import * as channel from "./channel";
import {csrf_token} from "./csrf";
import {page_params} from "./page_params";
import * as ui_report from "./ui_report";

export class ImageUploadWidget {
    constructor(url, selector, night_param) {
        this.url = url;
        this.selector = selector;
        this.night_param = night_param;
    }

    image_upload(input_file) {
        const form_data = new FormData();
        const widget_selector = this.selector;
        const night_param = this.night_param;

        form_data.append("csrfmiddlewaretoken", csrf_token);
        form_data.append("night", JSON.stringify(night_param));
        for (const [i, file] of Array.prototype.entries.call(input_file[0].files)) {
            form_data.append("file-" + i, file);
        }
        const delete_button = $(`#${widget_selector}  .image-delete-button`).expectOne();
        const error_text = $(`#${widget_selector}  .image_file_input_error`).expectOne();
        const spinner = $(`#${widget_selector} .upload-spinner-background`).expectOne();
        const upload_text = $(`#${widget_selector}  .image-upload-text`).expectOne();

        image_upload_start(spinner, upload_text, delete_button);
        error_text.hide();
        channel.post({
            url: this.url,
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success() {
                image_upload_complete(spinner, upload_text, delete_button);
                error_text.hide();
                // Hides `Avatar from Gravatar` on a successful user-avatar upload.
                if (widget_selector === "user-avatar-upload-widget") {
                    $("#user-avatar-source").hide();
                }
            },
            error(xhr) {
                image_upload_complete(spinner, upload_text, delete_button);
                ui_report.error("", xhr, error_text);
                // Displays `Avatar from Gravatar` on user-avatar upload error.
                if (
                    widget_selector === "user-avatar-upload-widget" &&
                    page_params.avatar_source === "G"
                ) {
                    $("#user-avatar-source").show();
                }
            },
        });
    }
}

export function image_upload_start(spinner, upload_text, delete_button) {
    spinner.css({visibility: "visible"});
    upload_text.hide();
    delete_button.hide();
}

export function image_upload_complete(spinner, upload_text, delete_button) {
    spinner.css({visibility: "hidden"});
    upload_text.show();
    delete_button.show();
}
