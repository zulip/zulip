"use strict";

const default_max_file_size = 5;

const supported_types = ["image/jpeg", "image/png", "image/gif", "image/tiff"];

function is_image_format(file) {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
}

exports.build_widget = function (
    get_file_input, // function returns a jQuery file input object
    file_name_field, // jQuery object to show file name
    input_error, // jQuery object for error text
    clear_button, // jQuery button to clear last upload choice
    upload_button, // jQuery button to open file dialog
    preview_text = null,
    preview_image = null,
    max_file_upload_size,
) {
    // default value of max uploaded file size
    max_file_upload_size = max_file_upload_size || default_max_file_size;

    function accept(file) {
        file_name_field.text(file.name);
        input_error.hide();
        clear_button.show();
        upload_button.hide();
        if (preview_text !== null) {
            const image_blob = URL.createObjectURL(file);
            preview_image.attr("src", image_blob);
            preview_text.show();
        }
    }

    function clear() {
        const control = get_file_input();
        control.val("");
        file_name_field.text("");
        clear_button.hide();
        upload_button.show();
        if (preview_text !== null) {
            preview_text.hide();
        }
    }

    clear_button.on("click", (e) => {
        clear();
        e.preventDefault();
    });

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
                accept(file);
            }
        } else {
            input_error.text(i18n.t("Please just upload one file."));
        }
    });

    upload_button.on("click", (e) => {
        get_file_input().trigger("click");
        e.preventDefault();
    });

    function close() {
        clear();
        clear_button.off("click");
        upload_button.off("drop");
        get_file_input().off("change");
        upload_button.off("click");
    }

    return {
        // Call back to clear() in situations like adding bots, when
        // we want to use the same widget over and over again.
        clear,
        // Call back to close() when you are truly done with the widget,
        // so you can release handlers.
        close,
    };
};
exports.build_direct_upload_widget = function (
    get_file_input, // function returns a jQuery file input object
    input_error, // jQuery object for error text
    upload_button, // jQuery button to open file dialog
    upload_function,
    max_file_upload_size,
) {
    // default value of max uploaded file size
    max_file_upload_size = max_file_upload_size || default_max_file_size;
    function accept() {
        input_error.hide();
        const realm_logo_section = upload_button.closest(".image_upload_widget");
        if (realm_logo_section.attr("id") === "realm-night-logo-upload-widget") {
            upload_function(get_file_input(), true, false);
        } else if (realm_logo_section.attr("id") === "realm-day-logo-upload-widget") {
            upload_function(get_file_input(), false, false);
        } else {
            upload_function(get_file_input(), null, true);
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

window.upload_widget = exports;
