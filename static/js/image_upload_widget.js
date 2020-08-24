"use strict";

const default_max_file_size = 5;
const supported_types = ["image/jpeg", "image/png", "image/gif", "image/tiff"];

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

function is_image_format(file) {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
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

exports.build_direct_upload_widget = function (
    widget_id,
    url,
    max_file_upload_size,
    night_param = false,
    upload_function = undefined, // Function that should be run in a success case of
    // an image upload. In case it's undefined, the default function will run instead.
) {
    const get_file_input = function () {
        return $(widget_id + " .image_file_input").expectOne();
    };
    const input_error = $(widget_id + " .image_file_input_error").expectOne();
    const upload_button = $(widget_id + " .image_upload_button").expectOne();
    // default value of max uploaded file size
    max_file_upload_size = max_file_upload_size || default_max_file_size;
    function accept() {
        input_error.hide();
        const widget = upload_button.closest(".image_upload_widget").attr("id");
        const upload_widget = new ImageUploadWidget(widget, url, night_param);
        if (upload_function) {
            upload_function(get_file_input());
        } else {
            upload_widget.upload_image(get_file_input());
        }
    }

    function clear() {
        const control = get_file_input();
        control.val("");
    }

    upload_button.on("drop", (e) => {
        const files = e.dataTransfer.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        get_file_input().get(0).files = files;
        e.preventDefault();
        return false;
    });

    get_file_input().attr("accept", supported_types.toString());
    get_file_input().on("change", (e) => {
        if (e.target.files.length === 0) {
            input_error.hide();
        } else if (e.target.files.length === 1) {
            const file = e.target.files[0];
            if (file.size > max_file_upload_size * 1024 * 1024) {
                input_error.text(
                    i18n.t("File size must be < __max_file_size__Mb.", {
                        max_file_size: max_file_upload_size,
                    }),
                );
                input_error.show();
                clear();
            } else if (!is_image_format(file)) {
                input_error.text(i18n.t("File type is not supported."));
                input_error.show();
                clear();
            } else {
                accept();
            }
        } else {
            input_error.text(i18n.t("Please just upload one file."));
        }
    });

    upload_button.on("click", (e) => {
        get_file_input().trigger("click");
        e.preventDefault();
    });
};

module.exports = ImageUploadWidget;
window.image_upload_widget = exports;
