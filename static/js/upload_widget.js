/* eslint-disable no-console */
"use strict";
const Cropper = require("cropperjs");
const {reset} = require("./color_data");

const default_max_file_size = 5;

const supported_types = ["image/jpeg", "image/png", "image/gif", "image/tiff"];

function is_image_format(file) {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
}

function dataURItoBlob(dataURI) {
    // convert base64/URLEncoded data component to raw binary data held in a string
    let byteString;
    if (dataURI.split(",")[0].includes("base64")) {
        byteString = atob(dataURI.split(",")[1]);
    } else {
        byteString = unescape(dataURI.split(",")[1]);
    }

    // separate out the mime component
    const mimeString = dataURI.split(",")[0].split(":")[1].split(";")[0];

    // write the bytes of the string to a typed array
    const ia = new Uint8Array(byteString.length);
    for (let i = 0; i < byteString.length; i += 1) {
        ia[i] = byteString.charCodeAt(i);
    }

    return new Blob([ia], {type: mimeString});
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
    function accept(file) {
        input_error.hide();
        const realm_logo_section = upload_button.closest(".image_upload_widget");
        if (realm_logo_section.attr("id") === "realm-night-logo-upload-widget") {
            upload_function(get_file_input(), true, false);
        } else if (realm_logo_section.attr("id") === "realm-day-logo-upload-widget") {
            upload_function(get_file_input(), false, false);
        } else {
            // We can call this function like this once this is complete.
            // upload_function(get_file_input(), file, null, true);
            upload_function(get_file_input(), null, true);
        }
    }

    function handle_image_edit(image_file) {
        const url = URL.createObjectURL(image_file);
        overlays.open_modal("#image_edit_modal");
        const image_ele = document.querySelector("#uploaded-image");
        image_ele.src = url;
        // these variables are to be used in many functions below.
        let cropper = null;
        let croppedData = null;
        let canvasData = null;
        let cropBoxData = null;
        let cropping = false;
        let cropped = true;
        let croppedDataURI = null;
        start();

        function start() {
            // set display of toolbar
            cropper = new Cropper(image_ele, {
                autoCrop: false,
                dragMode: "move",
                background: false,
                ready: () => {
                    // We crop only once.
                    if (croppedData) {
                        cropper
                            .crop()
                            .setData(croppedData)
                            .setCanvasData(canvasData)
                            .setCropBoxData(cropBoxData);
                        croppedData = null;
                        canvasData = null;
                        cropBoxData = null;
                    }
                },
                crop: ({detail}) => {
                    if (detail.width > 0 && detail.height > 0 && !cropping) {
                        cropping = true;
                    }
                },
            });
        }

        function stop() {
            if (cropper) {
                // hide display of toolbar here.
                cropper.destroy();
                cropper = null;
            }
        }

        function crop() {
            // here we simply update cropping data and state to be used by other functions.
            if (cropping) {
                croppedData = cropper.getData();
                canvasData = cropper.getCanvasData();
                cropBoxData = cropper.getCropBoxData();
                cropped = true;
                cropping = false;
                croppedDataURI = cropper.getCroppedCanvas().toDataURL(image_file.type);
                stop();
            }
        }

        function clear_cropper() {
            if (cropping) {
                cropper.clear();
                cropping = false;
            }
        }

        function restore() {
            // nothing need to be done if we have not done cropping atleast once.
            if (cropped) {
                cropped = false;
                croppedDataURI = "";
                image_ele.src = url;
            }
        }

        function reset() {
            // probably not of my use.
            stop();
            cropped = false;
            cropping = false;
        }

        const toolbar_buttons = document.querySelectorAll(".edit__toolbar__button");

        function handle_toolbar_events(event) {
            const action =
                event.target.getAttribute("data-action") ||
                event.target.parentElement.getAttribute("data-action");

            switch (action) {
                case "move":
                case "crop":
                    cropper.setDragMode(action);
                    break;
                case "zoom-in":
                    cropper.zoom(0.1);
                    break;
                case "zoom-out":
                    cropper.zoom(-0.1);
                    break;
                case "rotate-left":
                    cropper.rotate(-90);
                    break;
                case "rotate-right":
                    cropper.rotate(90);
                    break;
                case "flip-horizontal":
                    cropper.scaleX(-cropper.getData().scaleX || -1);
                    break;

                case "flip-vertical":
                    cropper.scaleY(-cropper.getData().scaleY || -1);
                    break;
                default:
            }
        }

        for (const button of toolbar_buttons) {
            button.addEventListener("click", (e) => {
                handle_toolbar_events(e);
            });
        }
        $("#confirm_edit_button").on("click", () => {
            const cropped_image = cropper.getCroppedCanvas().toDataURL(image_file.type);
            const blob = dataURItoBlob(cropped_image);
            console.log("blob =", blob);
            console.log("cropped_image =", cropped_image);
            console.log("get_file_input() =", get_file_input()[0]);
            get_file_input()[0].files[0] = cropped_image;
            overlays.close_modal("#image_edit_modal");
            accept(blob);
        });
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
                handle_image_edit(file);
                console.log("reached the commented line");
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
