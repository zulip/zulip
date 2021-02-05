"use strict";

const Uppy = require("@uppy/core");
const ProgressBar = require("@uppy/progress-bar");
const XHRUpload = require("@uppy/xhr-upload");

exports.make_upload_absolute = function (uri) {
    if (uri.startsWith(compose.uploads_path)) {
        // Rewrite the URI to a usable link
        return compose.uploads_domain + uri;
    }
    return uri;
};

// Show the upload button only if the browser supports it.
exports.feature_check = function (upload_button) {
    if (window.XMLHttpRequest && new XMLHttpRequest().upload) {
        upload_button.removeClass("notdisplayed");
    }
};
exports.get_translated_status = function (file) {
    const status = i18n.t("Uploading __filename__…", {filename: file.name});
    return "[" + status + "]()";
};

exports.get_item = function (key, config) {
    if (!config) {
        throw new Error("Missing config");
    }
    if (config.mode === "compose") {
        switch (key) {
            case "textarea":
                return $("#compose-textarea");
            case "send_button":
                return $("#compose-send-button");
            case "send_status_identifier":
                return "#compose-send-status";
            case "send_status":
                return $("#compose-send-status");
            case "send_status_close_button":
                return $(".compose-send-status-close");
            case "send_status_message":
                return $("#compose-error-msg");
            case "file_input_identifier":
                return "#file_input";
            case "source":
                return "compose-file-input";
            case "drag_drop_container":
                return $("#compose");
            case "markdown_preview_hide_button":
                return $("#undo_markdown_preview");
            default:
                throw new Error(`Invalid key name for mode "${config.mode}"`);
        }
    } else if (config.mode === "edit") {
        if (!config.row) {
            throw new Error("Missing row in config");
        }
        switch (key) {
            case "textarea":
                return $(`#message_edit_content_${CSS.escape(config.row)}`);
            case "send_button":
                return $(`#message_edit_content_${CSS.escape(config.row)}`)
                    .closest("#message_edit_form")
                    .find(".message_edit_save");
            case "send_status_identifier":
                return `#message-edit-send-status-${CSS.escape(config.row)}`;
            case "send_status":
                return $(`#message-edit-send-status-${CSS.escape(config.row)}`);
            case "send_status_close_button":
                return $(`#message-edit-send-status-${CSS.escape(config.row)}`).find(
                    ".send-status-close",
                );
            case "send_status_message":
                return $(`#message-edit-send-status-${CSS.escape(config.row)}`).find(".error-msg");
            case "file_input_identifier":
                return `#message_edit_file_input_${CSS.escape(config.row)}`;
            case "source":
                return "message-edit-file-input";
            case "drag_drop_container":
                return $("#message_edit_form");
            case "markdown_preview_hide_button":
                return $(`#undo_markdown_preview_${CSS.escape(config.row)}`);
            default:
                throw new Error(`Invalid key name for mode "${config.mode}"`);
        }
    } else {
        throw new Error("Invalid upload mode!");
    }
};

exports.hide_upload_status = function (config) {
    exports.get_item("send_button", config).prop("disabled", false);
    exports.get_item("send_status", config).removeClass("alert-info").hide();
};

exports.show_error_message = function (config, message) {
    if (!message) {
        message = i18n.t("An unknown error occurred.");
    }
    exports.get_item("send_button", config).prop("disabled", false);
    exports
        .get_item("send_status", config)
        .addClass("alert-error")
        .removeClass("alert-info")
        .show();
    exports.get_item("send_status_message", config).text(message);
};

exports.upload_files = function (uppy, config, files) {
    if (files.length === 0) {
        return;
    }
    if (page_params.max_file_upload_size_mib === 0) {
        exports.show_error_message(
            config,
            i18n.t("File and image uploads have been disabled for this organization."),
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
    if (exports.get_item("markdown_preview_hide_button", config).is(":visible")) {
        exports.get_item("markdown_preview_hide_button", config).trigger("click");
    }

    exports.get_item("send_button", config).prop("disabled", true);
    exports
        .get_item("send_status", config)
        .addClass("alert-info")
        .removeClass("alert-error")
        .show();
    exports.get_item("send_status_message", config).html($("<p>").text(i18n.t("Uploading…")));
    exports.get_item("send_status_close_button", config).one("click", () => {
        for (const file of uppy.getFiles()) {
            compose_ui.replace_syntax(
                exports.get_translated_status(file),
                "",
                exports.get_item("textarea", config),
            );
        }
        compose_ui.autosize_textarea(exports.get_item("textarea", config));
        uppy.cancelAll();
        exports.get_item("textarea", config).trigger("focus");
        setTimeout(() => {
            exports.hide_upload_status(config);
        }, 500);
    });

    for (const file of files) {
        try {
            compose_ui.insert_syntax_and_focus(
                exports.get_translated_status(file),
                exports.get_item("textarea", config),
            );
            compose_ui.autosize_textarea(exports.get_item("textarea", config));
            uppy.addFile({
                source: exports.get_item("source", config),
                name: file.name,
                type: file.type,
                data: file,
            });
        } catch {
            // Errors are handled by info-visible and upload-error event callbacks.
            break;
        }
    }
};

exports.setup_upload = function (config) {
    const uppy = new Uppy({
        debug: false,
        autoProceed: true,
        restrictions: {
            maxFileSize: page_params.max_file_upload_size_mib * 1024 * 1024,
        },
        locale: {
            strings: {
                exceedsSize: i18n.t("This file exceeds maximum allowed size of"),
                failedToUpload: i18n.t("Failed to upload %{file}"),
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
                timedOut: i18n.t("Upload stalled for %{seconds} seconds, aborting."),
            },
        },
    });

    uppy.use(ProgressBar, {
        target: exports.get_item("send_status_identifier", config),
        hideAfterFinish: false,
    });

    $("body").on("change", exports.get_item("file_input_identifier", config), (event) => {
        const files = event.target.files;
        exports.upload_files(uppy, config, files);
        event.target.value = "";
    });

    const drag_drop_container = exports.get_item("drag_drop_container", config);
    drag_drop_container.on("dragover", (event) => event.preventDefault());
    drag_drop_container.on("dragenter", (event) => event.preventDefault());

    drag_drop_container.on("drop", (event) => {
        event.preventDefault();
        const files = event.originalEvent.dataTransfer.files;
        exports.upload_files(uppy, config, files);
    });

    drag_drop_container.on("paste", (event) => {
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
        exports.upload_files(uppy, config, files);
    });

    uppy.on("upload-success", (file, response) => {
        const uri = response.body.uri;
        if (uri === undefined) {
            return;
        }
        const split_uri = uri.split("/");
        const filename = split_uri[split_uri.length - 1];
        if (config.mode === "compose" && !compose_state.composing()) {
            compose_actions.start("stream");
        }
        const absolute_uri = exports.make_upload_absolute(uri);
        const filename_uri = "[" + filename + "](" + absolute_uri + ")";
        compose_ui.replace_syntax(
            exports.get_translated_status(file),
            filename_uri,
            exports.get_item("textarea", config),
        );
        compose_ui.autosize_textarea(exports.get_item("textarea", config));
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

        const has_errors = exports.get_item("send_status", config).hasClass("alert-error");
        if (!uploads_in_progress && !has_errors) {
            setTimeout(() => {
                exports.hide_upload_status(config);
            }, 500);
        }
    });

    uppy.on("info-visible", () => {
        const info = uppy.getState().info;
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
            uppy.cancelAll();
            exports.show_error_message(config, info.message);
        }
    });

    uppy.on("upload-error", (file, error, response) => {
        const message = response ? response.body.msg : null;
        uppy.cancelAll();
        exports.show_error_message(config, message);
        compose_ui.replace_syntax(
            exports.get_translated_status(file),
            "",
            exports.get_item("textarea", config),
        );
        compose_ui.autosize_textarea(exports.get_item("textarea", config));
    });

    uppy.on("restriction-failed", (file) => {
        compose_ui.replace_syntax(
            exports.get_translated_status(file),
            "",
            exports.get_item("textarea", config),
        );
        compose_ui.autosize_textarea(exports.get_item("textarea", config));
    });

    return uppy;
};

window.upload = exports;
