"use strict";

function image_upload_complete(spinner, upload_text, delete_button) {
    spinner.css({visibility: "hidden"});
    upload_text.show();
    delete_button.show();
}

function image_upload_start(spinner, upload_text, delete_button) {
    spinner.css({visibility: "visible"});
    upload_text.hide();
    delete_button.hide();
}

class ImageUploadWidget {
    constructor(selector, url, night_param) {
        this.selector = selector;
        this.url = url;
        this.night_param = night_param;
    }

    upload_image(file_input) {
        const form_data = new FormData();
        const night_param = this.night_param;
        const widget = this.selector;
        const url = this.url;
        form_data.append("night", JSON.stringify(night_param));
        form_data.append("csrfmiddlewaretoken", csrf_token);
        for (const [i, file] of Array.prototype.entries.call(file_input[0].files)) {
            form_data.append("file-" + i, file);
        }

        const spinner = $(`#${widget} .upload-spinner-background`).expectOne();
        const upload_text = $(`#${widget}  .image-upload-text`).expectOne();
        const delete_button = $(`#${widget}  .image-delete-button`).expectOne();
        const error_field = $(`#${widget}  .image_file_input_error`).expectOne();
        image_upload_start(spinner, upload_text, delete_button);
        error_field.hide();
        channel.post({
            url,
            data: form_data,
            cache: false,
            processData: false,
            contentType: false,
            success() {
                image_upload_complete(spinner, upload_text, delete_button);
                error_field.hide();
                if (widget === "user-avatar-upload-widget") {
                    $("#user-avatar-source").hide();
                }
            },
            error(xhr) {
                image_upload_complete(spinner, upload_text, delete_button);
                ui_report.error("", xhr, error_field);
                if (widget === "user-avatar-upload-widget") {
                    if (page_params.avatar_source === "G") {
                        $("#user-avatar-source").show();
                    }
                }
            },
        });
    }
}

module.exports = ImageUploadWidget;
window.ImageUploadWidget = ImageUploadWidget;
