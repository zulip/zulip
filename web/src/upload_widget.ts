import {Uppy} from "@uppy/core";
import type {DashboardOptions} from "@uppy/dashboard";
import Dashboard from "@uppy/dashboard";
import type {ImageEditorOptions} from "@uppy/image-editor";
import ImageEditor from "@uppy/image-editor";
import $ from "jquery";

import * as dialog_widget from "./dialog_widget";
import {$t, $t_html} from "./i18n";
import * as settings_data from "./settings_data";

const default_max_file_size = 5;

const supported_types = ["image/jpeg", "image/png", "image/gif", "image/tiff"];

let cropfile: File;

export function get_cropped_file(): File {
    return cropfile;
}

function is_image_format(file: File): boolean {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
}

let uppy: Uppy;

const uppy_dashboard_options: DashboardOptions = {
    id: "Dashboard",
    inline: true,
    hideCancelButton: true,
    hideUploadButton: true,
    height: 450,
    autoOpenFileEditor: true,
    proudlyDisplayPoweredByUppy: false,
};

const uppy_image_editor_options: ImageEditorOptions = {
    id: "ImageEditor",
    quality: 1,
    cropperOptions: {
        viewMode: 0,
        background: true,
        autoCropArea: 1,
        aspectRatio: 1,
        responsive: true,
        croppedCanvasOptions: {},
        zoomOnTouch: false,
        zoomOnWheel: false,
    },
    actions: {
        revert: false,
        rotate: true,
        granularRotate: true,
        flip: true,
        zoomIn: true,
        zoomOut: true,
        cropSquare: true,
        cropWidescreen: false,
        cropWidescreenVertical: false,
    },
};

function set_custom_uppy_options(target: string): void {
    uppy_dashboard_options.target = target;
    uppy_dashboard_options.theme = settings_data.using_dark_theme() ? "dark" : "light";
    uppy_image_editor_options.target = Dashboard;
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
    $preview_text?: JQuery,
    $preview_image?: JQuery,
    $select_button?: JQuery,
    $all_elements_to_hide?: JQuery,
    $placeholder_icon?: JQuery,
    max_file_upload_size = default_max_file_size,
): {clear(): void; close(): void} {
    function accept(file: File): void {
        $file_name_field.text(file.name);
        $file_name_field.attr("title", file.name);
        $input_error.hide();
        $all_elements_to_hide?.hide();
        $clear_button.show();
        $select_button?.show();
        $upload_button.hide();

        if ($preview_text !== undefined && $preview_image !== undefined) {
            $preview_image.addClass("upload_widget_image_preview");
            $placeholder_icon?.hide();
            $preview_image.hide();
            $preview_text.show();

            set_custom_uppy_options("#" + String($preview_text.attr("id")));
            // opening uppy Image Editor
            uppy = new Uppy({
                id: "emoji-uppy",
                allowMultipleUploadBatches: false,
                restrictions: {
                    allowedFileTypes: supported_types,
                    maxNumberOfFiles: 1,
                    maxFileSize: max_file_upload_size * 1024 * 1024,
                },
            })
                .use(Dashboard, uppy_dashboard_options)
                .use(ImageEditor, uppy_image_editor_options)
                .on("file-added", (file) => {
                    if (file.type === "image/jpeg") {
                        file.type = "image/png";
                    }
                    if (
                        file.type === "image/gif" &&
                        $input_error.attr("id") === "emoji_file_input_error"
                    ) {
                        const file = uppy.getFiles()[0];
                        uppy.close();
                        cropfile = new File([file.data], file.name);
                        const url = URL.createObjectURL(file.data);
                        $preview_image?.attr("src", url);
                        $all_elements_to_hide?.show();
                        $upload_button.hide();
                        $select_button?.hide();
                        $preview_image?.show();
                        $input_error.html(
                            () =>
                                $("<div>").text(
                                    $t({defaultMessage: "GIFs can not be edited yet."}),
                                )[0],
                        );
                        $input_error.show();
                    }
                })
                .on("file-editor:complete", () => {
                    const file = uppy.getFiles()[0];
                    uppy.close();
                    cropfile = new File([file.data], file.name);
                    $all_elements_to_hide?.show();
                    const url = URL.createObjectURL(file.data);
                    $preview_image?.attr("src", url);
                    $upload_button.hide();
                    $select_button?.hide();
                    $preview_image?.show();
                });
        }
    }

    function clear(): void {
        const $control = get_file_input();
        $control.val("");
        $all_elements_to_hide?.show();
        $preview_image?.hide();
        $file_name_field.text("");
        $clear_button.hide();
        $upload_button.show();
        $select_button?.hide();
        $input_error.hide();
        if ($preview_text !== undefined && uppy) {
            uppy.close();
        }
    }

    $select_button?.on("click", (e) => {
        $(".uppy-DashboardContent-save").trigger("click");
        e.preventDefault();
    });

    $clear_button.on("click", (e) => {
        clear();
        e.preventDefault();
    });

    $upload_button.on("drop", (e) => {
        const files = e.originalEvent?.dataTransfer?.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        get_file_input()[0].files = files;
        e.preventDefault();
        return false;
    });

    get_file_input().attr("accept", supported_types.toString());
    get_file_input().on("change", (e) => {
        if (e.target.files?.length === 0) {
            $input_error.hide();
        } else if (e.target.files?.length === 1) {
            const file = e.target.files[0];
            if (file.size > max_file_upload_size * 1024 * 1024) {
                $input_error.text(
                    $t(
                        {defaultMessage: "File size must be at most {max_file_size} MiB."},
                        {max_file_size: max_file_upload_size},
                    ),
                );
                $input_error.show();
                $preview_text?.hide();
            } else if (!is_image_format(file)) {
                $input_error.text($t({defaultMessage: "File type is not supported."}));
                $input_error.show();
                $preview_text?.hide();
            } else {
                accept(file);
                uppy.addFile({
                    source: "file input",
                    name: file.name,
                    type: file.type,
                    data: file,
                });
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
    upload_function: (
        $file_input: JQuery<HTMLInputElement>,
        night: boolean | null,
        icon: boolean,
    ) => void,
    max_file_upload_size = default_max_file_size,
): void {
    // default value of max uploaded file size
    function accept(): void {
        $input_error.hide();
        const $realm_logo_section = $upload_button.closest(".image_upload_widget");
        if ($realm_logo_section.attr("id") === "realm-night-logo-upload-widget") {
            upload_function(get_file_input(), true, false);
        } else if ($realm_logo_section.attr("id") === "realm-day-logo-upload-widget") {
            upload_function(get_file_input(), false, false);
        } else {
            upload_function(get_file_input(), null, true);
        }
    }

    function clear(): void {
        const $control = get_file_input();
        $control.val("");
    }

    $upload_button.on("drop", (e) => {
        const files = e.originalEvent?.dataTransfer?.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        get_file_input()[0].files = files;
        e.preventDefault();
        return false;
    });

    get_file_input().attr("accept", supported_types.toString());
    get_file_input().on("change", (e) => {
        if (e.target.files?.length === 0) {
            $input_error.hide();
        } else if (e.target.files?.length === 1) {
            const file = e.target.files[0];
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
                accept();
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
