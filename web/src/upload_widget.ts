import Uppy from "@uppy/core";
import type {Body, Meta} from "@uppy/core";
import ImageEditor from "@uppy/image-editor";
import type Cropper from "cropperjs";
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

function is_image_format(file: File): boolean {
    const type = file.type;
    if (!type) {
        return false;
    }
    return supported_types.includes(type);
}

function is_animated_gif(file: File): boolean {
    return file.type === "image/gif";
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
    let selected_file: File | null = null;
    let cropped_file: File | null = null;
    let last_crop_box: Cropper.CropBoxData | null = null;
    let last_canvas_data: Cropper.CanvasData | null = null;
    let uppy_widget: Uppy<Meta, Body> | undefined;

    const $preview_container = $(".emoji-upload-form-container");
    const $cropper_container = allow_cropping ? $(".emoji-cropper-container") : undefined;
    const $cancel_crop_button = allow_cropping ? $(".emoji-cancel-crop-button") : undefined;
    const $save_crop_button = allow_cropping ? $(".emoji-save-crop-button") : undefined;
    const $placeholder_icon = $("#emoji_placeholder_icon");

    function transition_to_cropping_state(): void {
        if (!allow_cropping || selected_file === null) {
            return;
        }

        const editor = uppy_widget?.getPlugin<ImageEditor<Meta, Body>>("ImageEditor");
        const cropper = editor?.cropper;

        // Restore last saved state
        if (cropper && last_canvas_data && last_crop_box) {
            cropper.setCanvasData(last_canvas_data);
            cropper.setCropBoxData(last_crop_box);
        }

        $preview_container?.hide().attr("data-state", "inactive");
        $cropper_container?.show().attr("data-state", "active");
        $save_crop_button?.show();
        $cancel_crop_button?.show();
        $("#add-custom-emoji-modal-container .modal__footer").hide();
    }

    function transition_to_preview_state(): void {
        $cropper_container?.hide().attr("data-state", "inactive");
        $preview_container?.show().attr("data-state", "active");

        $save_crop_button?.hide();
        $cancel_crop_button?.hide();
        $("#add-custom-emoji-modal-container .modal__footer").show();

        const preview_file = cropped_file ?? selected_file;

        if (preview_file) {
            $placeholder_icon.hide();
            $preview_image?.show();
            $preview_text?.show();
        } else {
            $preview_image?.hide().attr("src", "");
            $preview_text?.show();
            $placeholder_icon.show();
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
                    viewMode: 1,
                    background: true,
                    autoCropArea: 1,
                    croppedCanvasOptions: {},
                    minCropBoxHeight: 50,
                    responsive: true,
                    minCropBoxWidth: 0,
                    initialAspectRatio: cropping_aspect_ratio,
                    aspectRatio: cropping_aspect_ratio,
                },
            });
        }

        const uppy_file_id = uppy_widget.addFile({
            name: file.name,
            type: file.type,
            data: file,
            source: "Local",
            isRemote: false,
        });

        const uppy_file = uppy_widget.getFile(uppy_file_id);
        uppy_widget.getPlugin<ImageEditor<Meta, Body>>("ImageEditor")!.selectFile(uppy_file);

        $save_crop_button?.on("click", (e) => {
            e.preventDefault();

            const editor = uppy_widget?.getPlugin<ImageEditor<Meta, Body>>("ImageEditor");
            if (!editor) {
                return;
            }

            $file_name_field.text(file.name);
            editor.save();
        });

        uppy_widget.on("file-editor:complete", (edited_file) => {
            assert(edited_file.data instanceof File);

            const editor = uppy_widget?.getPlugin<ImageEditor<Meta, Body>>("ImageEditor");
            const cropper = editor?.cropper;

            if (cropper) {
                last_crop_box = cropper.getCropBoxData();
                last_canvas_data = cropper.getCanvasData();
            }

            cropped_file = edited_file.data;

            update_preview(cropped_file);
            $file_name_field.text(cropped_file.name);
            $preview_text?.show();

            transition_to_preview_state();
        });
    }

    function update_preview(file: File): void {
        if ($preview_image === undefined) {
            return;
        }

        const old_src = $preview_image.attr("src");
        if (old_src?.startsWith("blob:")) {
            URL.revokeObjectURL(old_src);
        }

        const image_blob = URL.createObjectURL(file);
        $preview_image.attr("src", image_blob);
        $preview_image.addClass("upload_widget_image_preview");
    }

    function accept(file: File): void {
        selected_file = file;
        cropped_file = null;

        $input_error.hide();
        $clear_button.show();
        $upload_button.hide();

        if (allow_cropping === true && !is_animated_gif(file)) {
            setup_uppy_cropper(selected_file);
            transition_to_cropping_state();
        } else {
            // Disable cropping for GIFs
            update_preview(file);
            $file_name_field.text(file.name);
            transition_to_preview_state();
        }
    }

    function clear(is_error_state = false): void {
        const $control = get_file_input();
        $control.val("");

        selected_file = null;
        cropped_file = null;
        last_canvas_data = null;
        last_crop_box = null;

        $file_name_field.text("");
        $clear_button.hide();
        $upload_button.show();

        uppy_widget?.destroy();
        uppy_widget = undefined;

        if (!is_error_state) {
            transition_to_preview_state();
        } else {
            $preview_image?.hide();
            $preview_text?.hide();
        }
    }

    if (allow_cropping === true) {
        $cancel_crop_button?.on("click", (e) => {
            e.preventDefault();

            $cropper_container?.hide();
            requestAnimationFrame(() => {
                if (cropped_file === null) {
                    clear();
                    return;
                }
                transition_to_preview_state();
            });
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
                clear(true);
            } else if (!is_image_format(file)) {
                $input_error.text($t({defaultMessage: "File type is not supported."}));
                $input_error.show();
                clear(true);
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
            $cancel_crop_button?.off("click");
        }

        if (uppy_widget !== undefined) {
            uppy_widget.destroy();
            uppy_widget = undefined;
        }
    }

    function get_file(): File | null {
        return cropped_file ?? selected_file;
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

function set_up_uppy_widget(property_name: "realm_icon" | "realm_logo" | "user_avatar"): void {
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
        cropperOptions: {
            viewMode: 1,
            autoCropArea: 1,
            croppedCanvasOptions: {},
            dragMode: "move",
            minCropBoxHeight: 50,
            background: true,
            aspectRatio: property_name === "realm_logo" ? 8 : 1,
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
            set_up_uppy_widget(property_name);
            assert(uppy_widget !== undefined);

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
