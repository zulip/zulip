import {Uppy} from "@uppy/core";
import XHRUpload from "@uppy/xhr-upload";
import $ from "jquery";

import render_upload_banner from "../templates/compose_banner/upload_banner.hbs";

import * as compose_actions from "./compose_actions";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import {csrf_token} from "./csrf";
import {$t} from "./i18n";
import {page_params} from "./page_params";

// Show the upload button only if the browser supports it.
export function feature_check($upload_button) {
    if (window.XMLHttpRequest && new window.XMLHttpRequest().upload) {
        $upload_button.removeClass("notdisplayed");
    }
}

export function get_translated_status(file) {
    const status = $t({defaultMessage: "Uploading {filename}…"}, {filename: file.name});
    return "[" + status + "]()";
}

export function get_item(key, config) {
    if (!config) {
        throw new Error("Missing config");
    }
    if (config.mode === "compose") {
        switch (key) {
            case "textarea":
                return $("#compose-textarea");
            case "send_button":
                return $("#compose-send-button");
            case "banner_container":
                return $("#compose_banners");
            case "upload_banner_identifier":
                return "#compose_banners .upload_banner";
            case "upload_banner":
                return $("#compose_banners .upload_banner");
            case "upload_banner_close_button":
                return $("#compose_banners .upload_banner .compose_banner_close_button");
            case "upload_banner_message":
                return $("#compose_banners .upload_banner .upload_msg");
            case "file_input_identifier":
                return "#compose .file_input";
            case "source":
                return "compose-file-input";
            case "drag_drop_container":
                return $("#compose");
            case "markdown_preview_hide_button":
                return $("#compose .undo_markdown_preview");
            default:
                throw new Error(`Invalid key name for mode "${config.mode}"`);
        }
    } else if (config.mode === "edit") {
        if (!config.row) {
            throw new Error("Missing row in config");
        }
        switch (key) {
            case "textarea":
                return $(`#edit_form_${CSS.escape(config.row)} .message_edit_content`);
            case "send_button":
                return $(`#edit_form_${CSS.escape(config.row)} .message_edit_content`)
                    .closest(".message_edit_form")
                    .find(".message_edit_save");
            case "banner_container":
                return $(`#edit_form_${CSS.escape(config.row)} .banners`);
            case "upload_banner_identifier":
                return `#edit_form_${CSS.escape(config.row)} .upload_banner`;
            case "upload_banner":
                return $(`#edit_form_${CSS.escape(config.row)} .upload_banner`);
            case "upload_banner_close_button":
                return $(
                    `#edit_form_${CSS.escape(
                        config.row,
                    )} .upload_banner .compose_banner_close_button`,
                );
            case "upload_banner_message":
                return $(`#edit_form_${CSS.escape(config.row)} .upload_banner .upload_msg`);
            case "file_input_identifier":
                return `#edit_form_${CSS.escape(config.row)} .file_input`;
            case "source":
                return "message-edit-file-input";
            case "drag_drop_container":
                return $(`#zfilt${CSS.escape(config.row)} .message_edit_form`);
            case "markdown_preview_hide_button":
                return $(`#edit_form_${CSS.escape(config.row)} .undo_markdown_preview`);
            default:
                throw new Error(`Invalid key name for mode "${config.mode}"`);
        }
    } else {
        throw new Error("Invalid upload mode!");
    }
}

export function hide_upload_status(config) {
    get_item("send_button", config).prop("disabled", false);
    get_item("upload_banner", config).remove();
}

function show_upload_banner(config, banner_type, banner_text) {
    // We only show one upload banner at a time per compose box,
    // and all uploads are combined into the same progress bar.
    // TODO: It would be nice to separate the error banner into
    // a different element, so that we can show it at the same
    // time as the upload bar and other uploads can still continue
    // when an error occurs.
    const $upload_banner = get_item("upload_banner", config);
    if ($upload_banner.length) {
        if (banner_type === "error") {
            // Hide moving bar so that it doesn't do the 1s transition to 0
            const $moving_bar = $(`${get_item("upload_banner_identifier", config)} .moving_bar`);
            $moving_bar.hide();
            $upload_banner.removeClass("info").addClass("error");
            // Show it again once the animation is complete.
            setTimeout(() => $moving_bar.show(), 1000);
        } else {
            $upload_banner.removeClass("error").addClass("info");
        }
        get_item("upload_banner_message", config).text(banner_text);
        return;
    }
    const new_banner = render_upload_banner({
        banner_type,
        banner_text,
    });
    get_item("banner_container", config).append(new_banner);
}

export function show_error_message(
    config,
    message = $t({defaultMessage: "An unknown error occurred."}),
) {
    get_item("send_button", config).prop("disabled", false);
    show_upload_banner(config, "error", message);
}

export async function upload_files(uppy, config, files) {
    if (files.length === 0) {
        return;
    }
    if (page_params.max_file_upload_size_mib === 0) {
        show_error_message(
            config,
            $t({
                defaultMessage: "File and image uploads have been disabled for this organization.",
            }),
        );
        return;
    }

    // If we're looking at a markdown preview, switch back to the edit
    // UI.  This is important for all the later logic around focus
    // (etc.) to work correctly.
    //
    // We implement this transition through triggering a click on the
    // toggle button to take advantage of the existing plumbing for
    // handling the compose and edit UIs.
    if (get_item("markdown_preview_hide_button", config).is(":visible")) {
        get_item("markdown_preview_hide_button", config).trigger("click");
    }

    get_item("send_button", config).prop("disabled", true);
    show_upload_banner(config, "info", $t({defaultMessage: "Uploading…"}));
    get_item("upload_banner_close_button", config).one("click", () => {
        for (const file of uppy.getFiles()) {
            compose_ui.replace_syntax(
                get_translated_status(file),
                "",
                get_item("textarea", config),
            );
        }
        compose_ui.autosize_textarea(get_item("textarea", config));
        uppy.cancelAll();
        get_item("textarea", config).trigger("focus");
        hide_upload_status(config);
    });

    for (const file of files) {
        try {
            compose_ui.insert_syntax_and_focus(
                get_translated_status(file),
                get_item("textarea", config),
            );
            compose_ui.autosize_textarea(get_item("textarea", config));
            uppy.addFile({
                source: get_item("source", config),
                name: file.name,
                type: file.type,
                data: file,
            });
        } catch {
            // Errors are handled by info-visible and upload-error event callbacks.
            break;
        }
    }
}

export function setup_upload(config) {
    const uppy = new Uppy({
        debug: false,
        autoProceed: true,
        restrictions: {
            maxFileSize: page_params.max_file_upload_size_mib * 1024 * 1024,
        },
        locale: {
            strings: {
                exceedsSize: $t(
                    {
                        defaultMessage:
                            "%'{file}' exceeds the maximum file size for attachments ({variable} MB).",
                    },
                    {variable: `${page_params.max_file_upload_size_mib}`},
                ),
                failedToUpload: $t({defaultMessage: "Failed to upload %'{file}'"}),
            },
        },
    });
    uppy.setMeta({
        csrfmiddlewaretoken: csrf_token,
    });
    uppy.use(XHRUpload, {
        endpoint: "/json/user_uploads",
        formData: true,
        fieldName: "file",
        // Number of concurrent uploads
        limit: 5,
        locale: {
            strings: {
                timedOut: $t({
                    defaultMessage: "Upload stalled for %'{seconds}' seconds, aborting.",
                }),
            },
        },
    });

    uppy.on("progress", (progress) => {
        // When upload is complete, it resets to 0, but we want to see it at 100%.
        if (progress === 0) {
            return;
        }
        $(`${get_item("upload_banner_identifier", config)} .moving_bar`).css({
            width: `${progress}%`,
        });
    });

    $("body").on("change", get_item("file_input_identifier", config), (event) => {
        const files = event.target.files;
        upload_files(uppy, config, files);
        get_item("textarea", config).trigger("focus");
        event.target.value = "";
    });

    const $drag_drop_container = get_item("drag_drop_container", config);
    $drag_drop_container.on("dragover", (event) => event.preventDefault());
    $drag_drop_container.on("dragenter", (event) => event.preventDefault());

    $drag_drop_container.on("drop", (event) => {
        event.preventDefault();
        const files = event.originalEvent.dataTransfer.files;
        upload_files(uppy, config, files);
    });

    $drag_drop_container.on("paste", (event) => {
        const clipboard_data = event.clipboardData || event.originalEvent.clipboardData;
        if (!clipboard_data) {
            return;
        }
        const items = clipboard_data.items;
        const files = [];
        for (const item of items) {
            if (item.kind !== "file") {
                continue;
            }
            const file = item.getAsFile();
            files.push(file);
        }
        upload_files(uppy, config, files);
    });

    uppy.on("upload-success", (file, response) => {
        const uri = response.body.uri;
        if (uri === undefined) {
            return;
        }
        const split_uri = uri.split("/");
        const filename = split_uri.at(-1);
        if (config.mode === "compose" && !compose_state.composing()) {
            compose_actions.start("stream");
        }
        const filename_uri = "[" + filename + "](" + uri + ")";
        compose_ui.replace_syntax(
            get_translated_status(file),
            filename_uri,
            get_item("textarea", config),
        );
        compose_ui.autosize_textarea(get_item("textarea", config));
    });

    uppy.on("complete", () => {
        let uploads_in_progress = false;
        for (const file of uppy.getFiles()) {
            if (file.progress.uploadComplete) {
                // The uploaded files should be removed since uppy don't allow files in the store
                // to be re-uploaded again.
                uppy.removeFile(file.id);
            } else {
                // Happens when user tries to upload files when there is already an existing batch
                // being uploaded. So when the first batch of files complete, the second batch would
                // still be in progress.
                uploads_in_progress = true;
            }
        }

        const has_errors = get_item("upload_banner", config).hasClass("error");
        if (!uploads_in_progress && !has_errors) {
            // Hide upload status for 100ms after the 1s transition to 100%
            // so that the user can see the progress bar at 100%.
            setTimeout(() => {
                hide_upload_status(config);
            }, 1100);
        }
    });

    uppy.on("info-visible", () => {
        // Uppy's `info-visible` event is issued after prepending the
        // notice details into the list of event events accessed via
        // uppy.getState().info. Extract the notice details so that we
        // can potentially act on the error.
        //
        // TODO: Ideally, we'd be using the `.error()` hook or
        // something, not parsing error message strings.
        const info = uppy.getState().info[0];
        if (info.type === "error" && info.message === "No Internet connection") {
            // server_events already handles the case of no internet.
            return;
        }

        if (info.type === "error" && info.details === "Upload Error") {
            // The server errors come under 'Upload Error'. But we can't handle them
            // here because info object don't contain response.body.msg received from
            // the server. Server errors are hence handled by on('upload-error').
            return;
        }

        if (info.type === "error") {
            // The remaining errors are mostly frontend errors like file being too large
            // for upload.
            // TODO: It would be nice to keep the other uploads going if one fails,
            // and show both an error message and the upload bar.
            uppy.cancelAll();
            show_error_message(config, info.message);
        }
    });

    uppy.on("upload-error", (file, error, response) => {
        const message = response ? response.body.msg : undefined;
        uppy.cancelAll();
        show_error_message(config, message);
        compose_ui.replace_syntax(get_translated_status(file), "", get_item("textarea", config));
        compose_ui.autosize_textarea(get_item("textarea", config));
    });

    uppy.on("restriction-failed", (file) => {
        compose_ui.replace_syntax(get_translated_status(file), "", get_item("textarea", config));
        compose_ui.autosize_textarea(get_item("textarea", config));
    });

    return uppy;
}
