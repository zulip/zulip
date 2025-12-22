import Uppy from "@uppy/core";
import type {Body, Meta} from "@uppy/core";
import ImageEditor from "@uppy/image-editor";
import assert from "minimalistic-assert";

import render_image_editor_modal from "../templates/image_editor_modal.hbs";

import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as util from "./util.ts";

export type UploadWidget = {
    clear: () => void;
    close: () => void;
};

export type UploadFunction = (file: File, night: boolean | null, icon: boolean) => void;

const default_max_file_size = 5;

let uppy_widget: Uppy<Meta, Body> | undefined;

// These formats do not need to be universally understood by clients; they are all
// converted, server-side, currently to PNGs.  This list should be kept in sync with
// the THUMBNAIL_ACCEPT_IMAGE_TYPES in zerver/lib/thumbnail.py
const supported_types = [
    "image/avif",
    "image/gif",
    "image/heic",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
];

const cropper_opts = {
    viewMode: 1,
    autoCropArea: 1,
    croppedCanvasOptions: {},
    dragMode: "move",
    minCropBoxHeight: 50,
    background: true,
};

function is_image_format(file: File): boolean {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
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
    max_file_upload_size = default_max_file_size,
): UploadWidget {
    function accept(file: File): void {
        $file_name_field.text(file.name);
        $input_error.hide();
        $clear_button.show();
        $upload_button.hide();
        if ($preview_text !== undefined && $preview_image !== undefined) {
            const image_blob = URL.createObjectURL(file);
            $preview_image.attr("src", image_blob);
            $preview_image.addClass("upload_widget_image_preview");
            $preview_text.show();
        }
    }

    function clear(): void {
        const $control = get_file_input();
        $control.val("");
        $file_name_field.text("");
        $clear_button.hide();
        $upload_button.show();
        if ($preview_text !== undefined) {
            $preview_text.hide();
        }
    }

    $clear_button.on("click", (e) => {
        clear();
        e.preventDefault();
    });

    $upload_button.on("drop", (e) => {
        const files = e.originalEvent?.dataTransfer?.files;
        if (files === null || files === undefined || files.length === 0) {
            return false;
        }
        util.the(get_file_input()).files = files;
        e.preventDefault();
        return false;
    });

    get_file_input().attr("accept", supported_types.toString());
    get_file_input().on("change", (e) => {
        if (e.target.files?.[0] === undefined) {
            $input_error.hide();
        } else if (e.target.files.length === 1) {
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
                accept(file);
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

function set_up_uppy_widget(): void {
    uppy_widget = new Uppy<Meta, Body>({
        restrictions: {
            allowedFileTypes: supported_types,
            maxNumberOfFiles: 1,
        },
    }).use(ImageEditor, {
        target: "#uppy-editor .image-cropper-container",
        id: "ImageEditor",
        quality: 1,
        actions: {
            cropSquare: false,
            cropWidescreen: false,
            cropWidescreenVertical: false,
            zoomIn: true,
            zoomOut: true,
            revert: false,
            rotate: false,
            granularRotate: false,
            flip: false,
        },
    });
}

function open_uppy_editor(
    file: File,
    property_name: "realm_icon" | "realm_logo" | "user_avatar",
    $file_input: JQuery<HTMLInputElement>,
    $upload_button: JQuery,
    upload_function: UploadFunction,
): void {
    const rendered_image_editor_modal = render_image_editor_modal();
    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Editing {file_name}"}, {file_name: file.name}),
        html_body: rendered_image_editor_modal,
        id: "uppy-editor",
        loading_spinner: true,
        on_click() {
            assert(uppy_widget !== undefined);
            uppy_widget.getPlugin<ImageEditor<Meta, Body>>("ImageEditor")!.save();
        },
        on_shown() {
            // Use requestAnimationFrame to ensure the modal is fully painted
            // before initializing the image editor. This prevents CropperJS
            // from calculating dimensions on an incompletely rendered container.
            requestAnimationFrame(() => {
                // Hide the loading placeholder
                $("#uppy-editor .loading-placeholder").hide();
                
                set_up_uppy_widget();
                assert(uppy_widget !== undefined);

                if (property_name === "realm_logo") {
                    uppy_widget.getPlugin("ImageEditor")!.setOptions({
                        cropperOptions: {...cropper_opts, aspectRatio: 8},
                    });
                } else {
                    uppy_widget.getPlugin("ImageEditor")!.setOptions({
                        cropperOptions: {...cropper_opts, aspectRatio: 1},
                    });
                }

                const uppy_file_id = uppy_widget.addFile({
                    name: file.name,
                    type: "image/png",
                    data: file,
                    source: "Local",
                    isRemote: false,
                });
                const uppy_file = uppy_widget.getFile(uppy_file_id);
                uppy_widget.getPlugin<ImageEditor<Meta, Body>>("ImageEditor")!.selectFile(uppy_file);

                uppy_widget.once("file-editor:complete", (file) => {
                    assert(file.data instanceof File);
                    if (property_name === "realm_logo") {
                        const $realm_logo_section = $upload_button.closest(".image_upload_widget");
                        const is_night =
                            $realm_logo_section.attr("id") === "realm-night-logo-upload-widget";
                        upload_function(file.data, is_night, false);
                    } else {
                        upload_function(file.data, null, true);
                    }
                });
            });
        },
        on_hidden() {
            assert(uppy_widget !== undefined);
            uppy_widget.destroy();
            $file_input.val("");
        },
    });
}

export function build_direct_upload_widget(
    // function returns a jQuery file input object
    get_file_input: () => JQuery<HTMLInputElement>,
    // jQuery object for error text
    $input_error: JQuery,
    // jQuery button to open file dialog
    $upload_button: JQuery,
    upload_function: UploadFunction,
    max_file_upload_size: number,
    property_name: "realm_icon" | "realm_logo" | "user_avatar",
): void {
    // default value of max uploaded file size
    function accept(): void {
        $input_error.hide();

        const $file_input = get_file_input();
        const files = util.the($file_input).files;
        assert(files !== null);
        assert(files[0] !== undefined);
        open_uppy_editor(files[0], property_name, $file_input, $upload_button, upload_function);
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
        util.the(get_file_input()).files = files;
        e.preventDefault();
        return false;
    });

    get_file_input().attr("accept", supported_types.toString());
    get_file_input().on("change", (e) => {
        if (e.target.files?.[0] === undefined) {
            $input_error.hide();
        } else if (e.target.files.length === 1) {
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
