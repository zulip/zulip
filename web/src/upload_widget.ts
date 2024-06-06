import {Uppy} from "@uppy/core";
import Dashboard from "@uppy/dashboard";
import type {DashboardOptions} from "@uppy/dashboard";
import type {ImageEditorOptions} from "@uppy/image-editor";
import ImageEditor from "@uppy/image-editor";
import $ from "jquery";

import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import {any_active} from "./modals";
import * as settings_data from "./settings_data";

const supported_types = ["image/jpeg", "image/png", "image/gif", "image/tiff"];

const default_max_file_size = 5;

let uppy: Uppy;
let edited_file: File;

export function get_edited_file(): File {
    return edited_file;
}

export type UploadWidget = {
    clear: () => void;
    close: () => void;
};

export type UploadFunction = (
    $file_input: {files: File[]},
    night: boolean | null,
    icon: boolean,
) => void;

function upload_direct_widget(
    file: File,
    upload_function: UploadFunction,
    $upload_button: JQuery,
): void {
    const $realm_logo_section = $upload_button.closest(".image_upload_widget");
    if ($realm_logo_section.attr("id") === "realm-night-logo-upload-widget") {
        upload_function({files: [file]}, true, false);
    } else if ($realm_logo_section.attr("id") === "realm-day-logo-upload-widget") {
        upload_function({files: [file]}, false, false);
    } else {
        upload_function({files: [file]}, null, true);
    }
    if (any_active()) {
        dialog_widget.close();
    }
}

function is_image_format(file: File): boolean {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
}

const dashboard_options: DashboardOptions = {
    id: "Dashboard",
    inline: true,
    autoOpenFileEditor: true,
    animateOpenClose: false,
};

const image_editor_options: ImageEditorOptions = {
    id: "ImageEditor",
    quality: 1,
    target: Dashboard,
    cropperOptions: {
        viewMode: 1,
        aspectRatio: 1,
        background: true,
        cropBoxResizable: true,
        movable: true,
        restore: true,
        responsive: false,
        zoomOnWheel: false,
        croppedCanvasOptions: {},
        dragMode: "none",
    },
    actions: {
        cropSquare: true,
        cropWidescreen: false,
        cropWidescreenVertical: false,
        zoomIn: false,
        zoomOut: false,
        revert: false,
        rotate: false,
        granularRotate: false,
        flip: false,
    },
    locale : {
        strings: {
            aspectRatioSquare: 'Reset',
        }
    }
};

async function scale_image(file: File): Promise<File> {
    return new Promise((resolve, reject) => {
        const image = new Image();

        image.addEventListener("load", function () {
            const image_width = this.width;
            const image_height = this.height;

            const canvas = document.createElement("canvas");
            if (image_editor_options.cropperOptions?.aspectRatio === 1) {
                canvas.width = 1000;
                canvas.height = 1000;
            } else {
                // aspect ratio is 4
                canvas.width = 1000;
                canvas.height = 250;
            }

            // draw the scaled image on the canvas
            const context = canvas.getContext("2d");
            if (context) {
                context.drawImage(
                    image,
                    0,
                    0,
                    image_width,
                    image_height,
                    0,
                    0,
                    canvas.width,
                    canvas.height,
                );
            }

            // convert the canvas to a blob and return it
            canvas.toBlob((blob) => {
                if (blob) {
                    resolve(new File([blob], file.name));
                } else {
                    reject(new Error("Failed to scale image"));
                }
            });
        });

        image.src = URL.createObjectURL(file);
    });
}

export function build_widget(
    // function returns a jQuery file input object
    get_file_input: () => JQuery<HTMLInputElement>,
    // jQuery object to show file name
    $file_name_field: JQuery,
    // jQuery object for error text
    $input_error: JQuery,
    // jQuery button to clear last upload choice
    $clear_button: JQuery,
    // jQuery button to open file dialog
    $upload_button: JQuery,
    $save_button: JQuery,
    $scale_to_fit_button: JQuery,
    $preview_text?: JQuery,
    $preview_image?: JQuery,
    $other_elements_to_hide?: JQuery,
    max_file_upload_size = default_max_file_size,
): UploadWidget {
    let scaled = false;
    function accept(file: File): void {
        // this is needed in case we uploaded a logo before
        if (image_editor_options.cropperOptions && image_editor_options.actions) {
            image_editor_options.cropperOptions.aspectRatio = 1;
            image_editor_options.actions.cropSquare = true;
        }
        $file_name_field.text(file.name);
        if ($preview_text && $preview_image) {
            $preview_image.addClass("upload_widget_image_preview");
            // uppy does not allow cropping of giffs, the emoji would become an image
            if (file.type === "image/gif" && $file_name_field.is("#emoji-file-name")) {
                const image_blob = URL.createObjectURL(file);
                $preview_image.attr("src", image_blob);
                $upload_button.hide();
                $clear_button.show();
            } else {
                $file_name_field.hide();
                $input_error.hide();
                $upload_button.hide();
                $preview_image?.hide();
                $other_elements_to_hide?.hide();
                $preview_text.show();
                $save_button.show();
                $scale_to_fit_button.show();
                $clear_button.show();

                uppy = new Uppy({
                    restrictions: {
                        allowedFileTypes: supported_types,
                        maxNumberOfFiles: 1,
                        maxFileSize: max_file_upload_size * 1024 * 1024,
                    },
                })
                    .use(Dashboard, {
                        ...dashboard_options,
                        target: "#" + $preview_text.attr("id"),
                        theme: settings_data.using_dark_theme() ? "dark" : "light",
                    })
                    .use(ImageEditor, image_editor_options)
                    .on("file-editor:complete", () => {
                        if (scaled) {
                            void scale_image(file).then((scaled_file) => {
                                edited_file = scaled_file;
                                scaled = false;
                                const image_blob = URL.createObjectURL(edited_file);
                                $preview_image.attr("src", image_blob);
                            });
                        } else {
                            const file = uppy.getFiles()[0];
                            if (file) {
                                edited_file = new File([file.data], file.name);
                                const image_blob = URL.createObjectURL(edited_file);
                                $preview_image.attr("src", image_blob);
                            }
                        }
                        uppy.close();
                        $input_error.hide();
                        $save_button.hide();
                        $scale_to_fit_button.hide();
                        $preview_image?.show();
                        $file_name_field.show();
                        $other_elements_to_hide?.show();
                        if (!$file_name_field.closest("#emoji-file-name").length) {
                            $clear_button.hide();
                        }
                    });

                uppy.addFile({
                    source: "file input",
                    name: file.name,
                    type: file.type,
                    data: file,
                });
            }
        }
    }

    function clear(): void {
        if (uppy) {
            uppy.close();
        }
        const $control = get_file_input();
        $control.val("");
        $file_name_field.text("");
        $save_button.hide();
        $scale_to_fit_button.hide();
        $input_error.hide();
        $other_elements_to_hide?.show();
        $clear_button.hide();
        $upload_button.show();
    }

    $clear_button.on("click", (e) => {
        clear();
        e.preventDefault();
    });

    $save_button.on("click", (e) => {
        $(".uppy-DashboardContent-save").trigger("click");
        e.preventDefault();
    });

    $scale_to_fit_button.on("click", (e) => {
        $(".uppy-DashboardContent-save").trigger("click");
        scaled = true;
        e.preventDefault();
    });

    $upload_button.on("drop", (e) => {
        const files = e.originalEvent?.dataTransfer?.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        const $file_input = get_file_input();
        if ($file_input[0]) {
            $file_input[0].files = files;
        }
        e.preventDefault();
        return false;
    });

    get_file_input().attr("accept", supported_types.toString());
    get_file_input().on("change", (e) => {
        if (e.target.files?.length === 0) {
            $input_error.hide();
        } else if (e.target.files?.length === 1) {
            const file = e.target.files[0];
            if (file) {
                if (file.size > max_file_upload_size * 1024 * 1024) {
                    $input_error.text(
                        $t(
                            {defaultMessage: "File size must be at most {max_file_size} MiB."},
                            {max_file_size: max_file_upload_size},
                        ),
                    );
                    $input_error.show();
                    clear();
                } else if (!is_image_format(file)) {
                    $input_error.text($t({defaultMessage: "File type is not supported."}));
                    $input_error.show();
                    clear();
                } else {
                    accept(file);
                }
            }
        } else {
            $input_error.text($t({defaultMessage: "Please just upload one file."}));
        }
    });

    $upload_button.on("click", (e) => {
        get_file_input().trigger("click");
        e.preventDefault();
    });

    function close(): void {
        clear();
        $clear_button.off("click");
        $upload_button.off("drop");
        get_file_input().off("change");
        $upload_button.off("click");
        $save_button.off("click");
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
    get_file_input: () => JQuery<HTMLInputElement>,
    // jQuery object for error text
    $input_error: JQuery,
    // jQuery button to open file dialog
    $upload_button: JQuery,
    upload_function: UploadFunction,
    // default value of max uploaded file size
    max_file_upload_size: number,
    // New profile picture or New organization logo or New organization icon
    heading: string,
): void {
    let scaled = false;
    function submit(): void {
        $(".uppy-DashboardContent-save").trigger("click");
    }

    function clear(): void {
        if (uppy) {
            uppy.close();
        }
        const $control = get_file_input();
        $control.val("");
    }

    function accept(file: File): void {
        $input_error.hide();
        dialog_widget.launch({
            html_heading: heading,
            html_body: "<div id='ImageEditorDiv'></div>",
            html_submit_button: `${$t_html({
                defaultMessage: "Save changes",
            })} <button class='modal__btn dialog_submit_button' id='scale_to_fit'>Scale to fit</button>`,
            on_click: submit,
            on_hidden: clear,
        });

        if (image_editor_options.cropperOptions && image_editor_options.actions) {
            if (heading === $t({defaultMessage: "New organization logo"})) {
                // rectangle shape for organization logo
                image_editor_options.cropperOptions.aspectRatio = 4;
                image_editor_options.actions.cropSquare = false;
            } else {
                // this is needed in case we upload a logo first and then a non logo
                image_editor_options.cropperOptions.aspectRatio = 1;
                image_editor_options.actions.cropSquare = true;
            }
        }

        uppy = new Uppy({
            restrictions: {
                allowedFileTypes: supported_types,
                maxNumberOfFiles: 1,
                maxFileSize: max_file_upload_size * 1024 * 1024,
            },
        })
            .use(Dashboard, {
                ...dashboard_options,
                target: "#ImageEditorDiv",
                theme: settings_data.using_dark_theme() ? "dark" : "light",
            })
            .use(ImageEditor, image_editor_options)
            .on("file-editor:complete", () => {
                if (scaled) {
                    void scale_image(file).then((scaled_file) => {
                        upload_direct_widget(scaled_file, upload_function, $upload_button);
                        scaled = false;
                    });
                } else {
                    const file = uppy.getFiles()[0];
                    if (file) {
                        const edited_file = new File([file.data], file.name);
                        upload_direct_widget(edited_file, upload_function, $upload_button);
                    }
                }
                clear();
                $input_error.hide();
            });

        uppy.addFile({
            name: file.name,
            type: file.type,
            data: file,
        });

        const scaleButton = document.querySelector("#scale_to_fit");
        if (scaleButton) {
            scaleButton.addEventListener("click", () => {
                scaled = true;
            });
        }
    }

    $upload_button.on("drop", (e) => {
        const files = e.originalEvent?.dataTransfer?.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        const $file_input = get_file_input();
        if ($file_input[0]) {
            $file_input[0].files = files;
        }
        e.preventDefault();
        return false;
    });

    get_file_input().attr("accept", supported_types.toString());
    get_file_input().on("change", (e) => {
        if (e.target.files?.length === 0) {
            $input_error.hide();
        } else if (e.target.files?.length === 1) {
            const file = e.target.files[0];
            if (file) {
                if (file.size > max_file_upload_size * 1024 * 1024) {
                    $input_error.text(
                        $t(
                            {defaultMessage: "File size must be at most {max_file_size} MiB."},
                            {max_file_size: max_file_upload_size},
                        ),
                    );
                    $input_error.show();
                    clear();
                } else if (!is_image_format(file)) {
                    $input_error.text($t({defaultMessage: "File type is not supported."}));
                    $input_error.show();
                    clear();
                } else {
                    accept(file);
                }
            }
        } else {
            $input_error.text($t({defaultMessage: "Please just upload one file."}));
        }
    });

    $upload_button.on("click", (e) => {
        get_file_input().trigger("click");
        e.preventDefault();
    });
}
