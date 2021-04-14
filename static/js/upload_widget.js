import {$t} from "./i18n";
import {ImageUploadWidget} from "./image_upload_widget";

const default_max_file_size = 5;
const supported_types = ["image/jpeg", "image/png", "image/gif", "image/tiff"];

function is_image_format(file) {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
}

export function build_widget(
    // function returns a jQuery file input object
    get_file_input,
    // jQuery object to show file name
    file_name_field,
    // jQuery object for error text
    input_error,
    // jQuery button to clear last upload choice
    clear_button,
    // jQuery button to open file dialog
    upload_button,
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
                    $t(
                        {defaultMessage: "File size must be at most {max_file_size} MiB."},
                        {max_file_size: max_file_upload_size},
                    ),
                );
                input_error.show();
                clear();
            } else if (!is_image_format(file)) {
                input_error.text($t({defaultMessage: "File type is not supported."}));
                input_error.show();
                clear();
            } else {
                accept(file);
            }
        } else {
            input_error.text($t({defaultMessage: "Please just upload one file."}));
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
}

export function build_direct_upload_widget(
    // function returns a jQuery file input object
    get_file_input,
    // jQuery object for error text
    input_error,
    // jQuery button to open file dialog
    upload_button,
    max_file_upload_size,
) {
    // default value of max uploaded file size
    max_file_upload_size = max_file_upload_size || default_max_file_size;

    function accept() {
        input_error.hide();
        let url;
        const widget_selector = upload_button.closest(".image_upload_widget").attr("id");
        let night_param = false;
        if (widget_selector === "realm-icon-upload-widget") {
            url = "/json/realm/icon";
        } else if (widget_selector === "user-avatar-upload-widget") {
            url = "/json/users/me/avatar";
        }
        // Set url for realm-logo
        else {
            // Change night_param to true if night logo.
            if (widget_selector === "realm-night-logo-upload-widget") {
                night_param = true;
            }
            // Else night_param remains false and url is assigned regardless.
            url = "/json/realm/logo";
        }

        const image_upload_widget = new ImageUploadWidget(url, widget_selector, night_param);
        image_upload_widget.image_upload(get_file_input());
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
                    $t(
                        {defaultMessage: "File size must be at most {max_file_size} MiB."},
                        {max_file_size: max_file_upload_size},
                    ),
                );
                input_error.show();
                clear();
            } else if (!is_image_format(file)) {
                input_error.text($t({defaultMessage: "File type is not supported."}));
                input_error.show();
                clear();
            } else {
                accept();
            }
        } else {
            input_error.text($t({defaultMessage: "Please just upload one file."}));
        }
    });

    upload_button.on("click", (e) => {
        get_file_input().trigger("click");
        e.preventDefault();
    });
}
