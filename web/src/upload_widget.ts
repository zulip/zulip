import Uppy from "@uppy/core";
import type {Body, Meta} from "@uppy/core";
import ImageEditor from "@uppy/image-editor";
import $ from "jquery";
import assert from "minimalistic-assert";

import render_image_editor_modal from "../templates/image_editor_modal.hbs";

import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";
import * as util from "./util.ts";

export type UploadWidget = {
    clear: () => void;
    close: () => void;
    get_file: () => File | null;
};

export type UploadFunction = (file: File, night: boolean | null, icon: boolean) => void;

const default_max_file_size = 5;

const default_cropping_aspect_ratio = 1;

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
    allow_cropping?: boolean,
    max_file_upload_size = default_max_file_size,
    cropping_aspect_ratio = default_cropping_aspect_ratio,
): UploadWidget {
    let current_file: File | null = null;
    let cropped_file: File | null = null;
    let uppy_widget: Uppy<Meta, Body> | undefined;
    let modal_state: "preview" | "cropping" = "preview";

    const $preview_container = $(".emoji-upload-form-container");
    const $cropper_container = allow_cropping ? $(".emoji-cropper-container") : undefined;
    const $edit_button = allow_cropping ? $(".emoji-edit-button") : undefined;
    const $cancel_crop_button = allow_cropping ? $(".emoji-cancel-crop-button") : undefined;
    const $save_crop_button = allow_cropping ? $(".emoji-save-crop-button") : undefined;

    function transition_to_cropping_state(): void {
        if (!allow_cropping || current_file === null) {
            return;
        }

        modal_state = "cropping";

        // Hide preview, show cropper
        $preview_container?.hide().attr("data-state", "inactive");
        $cropper_container?.show().attr("data-state", "active");
        $save_crop_button?.show();
        $cancel_crop_button?.show();
        $("#add-custom-emoji-modal-container .modal__footer").hide();

        // Initialize Uppy cropper
        setup_uppy_cropper(current_file);
    }

    function transition_to_preview_state(new_file?: File): void {
        modal_state = "preview";

        // Show preview, hide cropper
        $cropper_container?.hide().attr("data-state", "inactive");
        $preview_container?.show().attr("data-state", "active");
        $save_crop_button?.hide();
        $cancel_crop_button?.hide();
        $("#add-custom-emoji-modal-container .modal__footer").show();

        // If we have a newly cropped file, update everything
        if (new_file !== undefined) {
            cropped_file = new_file;
            current_file = new_file;
            update_preview(new_file);
            $file_name_field.text(new_file.name);
        }

        $save_crop_button?.off("click");

        if (uppy_widget !== undefined) {
            uppy_widget.destroy();
            uppy_widget = undefined;
        }
    }

    function setup_uppy_cropper(file: File): void {
        uppy_widget = new Uppy<Meta, Body>({
            restrictions: {
                allowedFileTypes: supported_types,
                maxNumberOfFiles: 1,
            },
        }).use(ImageEditor, {
            target: ".emoji-uppy-target",
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

        $cropper_container?.on("click", "button", (e) => {
            e.preventDefault();
            e.stopPropagation();
        });

        // Configure aspect ratio if provided
        if (cropping_aspect_ratio !== undefined && cropping_aspect_ratio !== null) {
            uppy_widget.getPlugin("ImageEditor")!.setOptions({
                cropperOptions: {
                    aspectRatio: cropping_aspect_ratio,
                    viewMode: 1,
                    autoCropArea: 1,
                },
            });
        }

        // Add file to Uppy
        const uppy_file_id = uppy_widget.addFile({
            name: file.name,
            type: file.type,
            data: file,
            source: "Local",
            isRemote: false,
        });

        const uppy_file = uppy_widget.getFile(uppy_file_id);
        uppy_widget.getPlugin<ImageEditor<Meta, Body>>("ImageEditor")!.selectFile(uppy_file);

        $save_crop_button?.one("click", (e) => {
            e.preventDefault();
            uppy_widget?.getPlugin<ImageEditor<Meta, Body>>("ImageEditor")!.save();
        });

        // Handle crop completion
        uppy_widget.once("file-editor:complete", (edited_file) => {
            assert(edited_file.data instanceof File);
            transition_to_preview_state(edited_file.data);
        });
    }

    function update_preview(file: File): void {
        if ($preview_image === undefined) {
            return;
        }

        // Revoke old object URL to prevent memory leaks
        const old_src = $preview_image.attr("src");
        if (old_src?.startsWith("blob:")) {
            URL.revokeObjectURL(old_src);
        }

        // Set new preview
        const image_blob = URL.createObjectURL(file);
        $preview_image.attr("src", image_blob);
        $preview_image.addClass("upload_widget_image_preview");
    }

    function accept(file: File): void {
        current_file = file;
        cropped_file = null;

        $file_name_field.text(file.name);
        $input_error.hide();
        $clear_button.show();
        $upload_button.hide();

        if ($preview_text !== undefined && $preview_image !== undefined) {
            update_preview(file);
            $preview_text.show();
        }

        if (allow_cropping === true) {
            $edit_button?.show();
        }
    }

    function clear(): void {
        const $control = get_file_input();
        $control.val("");
        $file_name_field.text("");
        $clear_button.hide();
        $upload_button.show();

        if (allow_cropping === true) {
            $edit_button?.hide();
        }

        if ($preview_image !== undefined) {
            const old_src = $preview_image.attr("src");
            if (old_src?.startsWith("blob:")) {
                URL.revokeObjectURL(old_src);
            }
            $preview_image.attr("src", "");
        }

        if ($preview_text !== undefined) {
            $preview_text.hide();
        }

        if (modal_state === "cropping") {
            transition_to_preview_state();
        }

        current_file = null;
        cropped_file = null;
    }

    if (allow_cropping === true) {
        $edit_button?.on("click", (e) => {
            e.preventDefault();
            transition_to_cropping_state();
        });

        $cancel_crop_button?.on("click", (e) => {
            e.preventDefault();
            transition_to_preview_state();
        });
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

        if (allow_cropping === true) {
            $edit_button?.off("click");
            $cancel_crop_button?.off("click");
        }

        if (uppy_widget !== undefined) {
            uppy_widget.destroy();
            uppy_widget = undefined;
        }
    }

    function get_file(): File | null {
        return cropped_file ?? current_file;
    }

    return {
        // Call back to clear() in situations like adding bots, when
        // we want to use the same widget over and over again.
        clear,
        // Call back to close() when you are truly done with the widget,
        // so you can release handlers.
        close,
        get_file,
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
        post_render() {
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
