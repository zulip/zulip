import type {Meta} from "@uppy/core";
import {Uppy} from "@uppy/core";
import Tus, {type TusBody} from "@uppy/tus";
import {getSafeFileId} from "@uppy/utils/lib/generateFileID";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_upload_banner from "../templates/compose_banner/upload_banner.hbs";

import * as blueslip from "./blueslip.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_reply from "./compose_reply.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as compose_validate from "./compose_validate.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as rows from "./rows.ts";
import {realm} from "./state_data.ts";

type ZulipMeta = {
    zulip_url: string;
} & Meta;

let drag_drop_img: HTMLElement | null = null;
let compose_upload_object: Uppy<ZulipMeta, TusBody>;
const upload_objects_by_message_edit_row = new Map<number, Uppy<ZulipMeta, TusBody>>();

export function compose_upload_cancel(): void {
    compose_upload_object.cancelAll();
}

export function feature_check(): XMLHttpRequestUpload {
    // Show the upload button only if the browser supports it.
    return window.XMLHttpRequest && new window.XMLHttpRequest().upload;
}

export function get_translated_status(filename: string): string {
    const status = $t({defaultMessage: "Uploading {filename}…"}, {filename});
    return "[" + status + "]()";
}

type Config = ({mode: "compose"} | {mode: "edit"; row: number}) & {
    textarea: () => JQuery<HTMLTextAreaElement>;
    send_button: () => JQuery;
    banner_container: () => JQuery;
    upload_banner_identifier: (file_id: string) => string;
    upload_banner: (file_id: string) => JQuery;
    upload_banner_cancel_button: (file_id: string) => JQuery;
    upload_banner_hide_button: (file_id: string) => JQuery;
    upload_banner_message: (file_id: string) => JQuery;
    file_input_identifier: () => string;
    source: () => string;
    drag_drop_container: () => JQuery;
    markdown_preview_hide_button: () => JQuery;
};

export const compose_config: Config = {
    mode: "compose",
    textarea: () => $<HTMLTextAreaElement>("textarea#compose-textarea"),
    send_button: () => $("#compose-send-button"),
    banner_container: () => $("#compose_banners"),
    upload_banner_identifier: (file_id) =>
        `#compose_banners .upload_banner.file_${CSS.escape(file_id)}`,
    upload_banner: (file_id) => $(`#compose_banners .upload_banner.file_${CSS.escape(file_id)}`),
    upload_banner_cancel_button: (file_id) =>
        $(
            `#compose_banners .upload_banner.file_${CSS.escape(
                file_id,
            )} .upload_banner_cancel_button`,
        ),
    upload_banner_hide_button: (file_id) =>
        $(
            `#compose_banners .upload_banner.file_${CSS.escape(
                file_id,
            )} .main-view-banner-close-button`,
        ),
    upload_banner_message: (file_id) =>
        $(`#compose_banners .upload_banner.file_${CSS.escape(file_id)} .upload_msg`),
    file_input_identifier: () => "#compose input.file_input",
    source: () => "compose-file-input",
    drag_drop_container: () => $("#compose"),
    markdown_preview_hide_button: () => $("#compose .undo_markdown_preview"),
};

export function edit_config(row: number): Config {
    return {
        mode: "edit",
        row,
        textarea: () =>
            $<HTMLTextAreaElement>(
                `#edit_form_${CSS.escape(`${row}`)} textarea.message_edit_content`,
            ),
        send_button: () => $(`#edit_form_${CSS.escape(`${row}`)}`).find(".message_edit_save"),
        banner_container: () => $(`#edit_form_${CSS.escape(`${row}`)} .edit_form_banners`),
        upload_banner_identifier: (file_id) =>
            `#edit_form_${CSS.escape(`${row}`)} .upload_banner.file_${CSS.escape(file_id)}`,
        upload_banner: (file_id) =>
            $(`#edit_form_${CSS.escape(`${row}`)} .upload_banner.file_${CSS.escape(file_id)}`),
        upload_banner_cancel_button: (file_id) =>
            $(
                `#edit_form_${CSS.escape(`${row}`)} .upload_banner.file_${CSS.escape(
                    file_id,
                )} .upload_banner_cancel_button`,
            ),
        upload_banner_hide_button: (file_id) =>
            $(
                `#edit_form_${CSS.escape(`${row}`)} .upload_banner.file_${CSS.escape(
                    file_id,
                )} .main-view-banner-close-button`,
            ),
        upload_banner_message: (file_id) =>
            $(
                `#edit_form_${CSS.escape(`${row}`)} .upload_banner.file_${CSS.escape(
                    file_id,
                )} .upload_msg`,
            ),
        file_input_identifier: () => `#edit_form_${CSS.escape(`${row}`)} input.file_input`,
        source: () => "message-edit-file-input",
        drag_drop_container() {
            assert(message_lists.current !== undefined);
            return $(
                `#message-row-${message_lists.current.id}-${CSS.escape(`${row}`)} .message_edit_form`,
            );
        },
        markdown_preview_hide_button: () =>
            $(`#edit_form_${CSS.escape(`${row}`)} .undo_markdown_preview`),
    };
}

export let hide_upload_banner = (
    uppy: Uppy<ZulipMeta, TusBody>,
    config: Config,
    file_id: string,
    delay = 0,
): void => {
    if (delay > 0) {
        setTimeout(() => {
            config.upload_banner(file_id).remove();
        }, delay);
    } else {
        config.upload_banner(file_id).remove();
    }

    // Allow sending the message if all uploads are complete or cancelled.
    if (
        uppy.getFiles().every((e) => e.progress.uploadComplete) ||
        Object.keys(uppy.getState().currentUploads).length === 0
    ) {
        if (config.mode === "compose") {
            compose_validate.set_upload_in_progress(false);
        } else {
            config.send_button().prop("disabled", false);
        }
    }
};

export function rewire_hide_upload_banner(value: typeof hide_upload_banner): void {
    hide_upload_banner = value;
}

function add_upload_banner(
    config: Config,
    banner_type: string,
    banner_text: string,
    file_id: string,
    is_upload_process_tracker = false,
): void {
    const new_banner_html = render_upload_banner({
        banner_type,
        is_upload_process_tracker,
        banner_text,
        file_id,
    });
    compose_banner.append_compose_banner_to_banner_list(
        $(new_banner_html),
        config.banner_container(),
    );
}

export function show_error_message(
    config: Config,
    message = $t({defaultMessage: "An unknown error occurred."}),
    file_id: string | null = null,
): void {
    if (file_id) {
        $(`${config.upload_banner_identifier(file_id)} .moving_bar`).hide();
        config.upload_banner(file_id).removeClass("info").addClass("error");
        config.upload_banner_message(file_id).text(message);
    } else {
        // We still use a "file_id" (that's not actually related to a file)
        // to differentiate this banner from banners that *are* associated
        // with files. This is notably relevant for the close click handler.
        add_upload_banner(config, "error", message, "generic_error");
    }
}

export let upload_files = (
    uppy: Uppy<ZulipMeta, TusBody>,
    config: Config,
    files: File[] | FileList,
): void => {
    if (files.length === 0) {
        return;
    }
    if (realm.max_file_upload_size_mib === 0) {
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
    if (config.markdown_preview_hide_button().css("display") !== "none") {
        config.markdown_preview_hide_button().trigger("click");
    }

    for (const file of files) {
        let file_id;
        try {
            compose_ui.insert_syntax_and_focus(
                get_translated_status(file.name),
                config.textarea(),
                "block",
                1,
            );
            compose_ui.autosize_textarea(config.textarea());
            file_id = uppy.addFile({
                source: config.source(),
                name: file.name,
                type: file.type,
                data: file,
            });
        } catch {
            // Errors are handled by info-visible and upload-error event callbacks.
            continue;
        }

        if (config.mode === "compose") {
            compose_validate.set_upload_in_progress(true);
        } else {
            config.send_button().prop("disabled", true);
        }
        add_upload_banner(
            config,
            "info",
            $t({defaultMessage: "Uploading {filename}…"}, {filename: file.name}),
            file_id,
            true,
        );
        // eslint-disable-next-line @typescript-eslint/no-loop-func
        config.upload_banner_cancel_button(file_id).on("click", () => {
            compose_ui.replace_syntax(get_translated_status(file.name), "", config.textarea());
            compose_ui.autosize_textarea(config.textarea());
            config.textarea().trigger("focus");

            uppy.removeFile(file_id);
            hide_upload_banner(uppy, config, file_id);
        });
        // eslint-disable-next-line @typescript-eslint/no-loop-func
        config.upload_banner_hide_button(file_id).on("click", () => {
            hide_upload_banner(uppy, config, file_id);
        });
    }
};

export function rewire_upload_files(value: typeof upload_files): void {
    upload_files = value;
}

export function upload_pasted_file(textarea: HTMLTextAreaElement, pasted_file: File): void {
    if (textarea.id === "compose-textarea") {
        upload_files(compose_upload_object, compose_config, [pasted_file]);
        return;
    }
    const row = rows.get_message_id(textarea);
    const edit_uploader = upload_objects_by_message_edit_row.get(row);
    assert(edit_uploader !== undefined);
    upload_files(edit_uploader, edit_config(row), [pasted_file]);
}

// Borrowed from tus-js-client code at
// https://github.com/tus/tus-js-client/blob/ca63ba254ea8766438b9d422f6f94284911f1fa5/lib/index.d.ts#L79
// The library does not export this type, hence requiring a copy here.
type PreviousUpload = {
    size: number | null;
    metadata: Record<string, string>;
    creationTime: string;
    urlStorageKey: string;
    uploadUrl: string | null;
    parallelUploadUrls: string[] | null;
};

// Parts of it are inspired from WebStorageUrlStorage at
// https://github.com/tus/tus-js-client/blob/ca63ba254ea8766438b9d422f6f94284911f1fa5/lib/browser/urlStorage.js#L27
// While there are no async actions happening in any of the methods in
// this class, UrlStorage interface for tus-js-client requires a Promise
// to be returned for each of these methods.
class InMemoryUrlStorage {
    urlStorage: Map<string, PreviousUpload>;

    constructor() {
        this.urlStorage = new Map();
    }

    async findAllUploads(): Promise<PreviousUpload[]> {
        return await Promise.resolve([...this.urlStorage.values()]);
    }

    async findUploadsByFingerprint(fingerprint: string): Promise<PreviousUpload[]> {
        const results = [];

        for (const [key, value] of this.urlStorage) {
            if (!key.startsWith(`${fingerprint}::`)) {
                continue;
            }
            results.push(value);
        }

        return await Promise.resolve(results);
    }

    async removeUpload(urlStorageKey: string): Promise<void> {
        this.urlStorage.delete(urlStorageKey);
        await Promise.resolve();
    }

    async addUpload(fingerprint: string, upload: PreviousUpload): Promise<string> {
        const id = Math.round(Math.random() * 1e12);
        const key = `${fingerprint}::${id}`;

        upload.urlStorageKey = key;
        this.urlStorage.set(key, upload);
        return await Promise.resolve(key);
    }
}

const zulip_upload_response_schema = z.object({
    url: z.string(),
    filename: z.string(),
});

export function setup_upload(config: Config): Uppy<ZulipMeta, TusBody> {
    const uppy = new Uppy<ZulipMeta, TusBody>({
        debug: false,
        autoProceed: true,
        restrictions: {
            maxFileSize: realm.max_file_upload_size_mib * 1024 * 1024,
        },
        locale: {
            strings: {
                exceedsSize: $t(
                    {
                        defaultMessage:
                            "%'{file}' exceeds the maximum file size for attachments ({variable} MB).",
                    },
                    {variable: `${realm.max_file_upload_size_mib}`},
                ),
                failedToUpload: $t({defaultMessage: "Failed to upload %'{file}'"}),
            },
            pluralize: (_n) => 0,
        },
        onBeforeFileAdded(file, files) {
            const file_id = getSafeFileId(file, uppy.getID());

            if (files[file_id]) {
                // We have a duplicate file upload on our hands.
                // Since we don't get a response with a body back from
                // the server, pull the values that we got the last
                // time around.
                file.meta.zulip_url = files[file_id].meta.zulip_url!;
                file.name = files[file_id].name!;
            }

            return file;
        }, // Allow duplicate file uploads
    });
    uppy.use(Tus, {
        // https://uppy.io/docs/tus/#options
        endpoint: "/api/v1/tus/",
        // The tus-js-client fingerprinting feature stores metadata on
        // previously uploaded files by default in browser local storage.
        // Since these local storage entries are never garbage-collected,
        // they can be accessed via the browser console even after
        // logging out, and contain some metadata about previously
        // uploaded files, which seems like a security risk for
        // using Zulip on a public computer.

        // We use our own implementation of url storage that saves urls
        // in memory instead. We won't be able to retain this history
        // across reloads unlike local storage, which is a tradeoff we
        // are willing to make.
        urlStorage: new InMemoryUrlStorage(),
        // Number of concurrent uploads
        limit: 5,
    });

    if (config.mode === "edit") {
        upload_objects_by_message_edit_row.set(config.row, uppy);
    }

    uppy.on("upload-progress", (file, progress) => {
        assert(file !== undefined);
        assert(progress.bytesTotal !== null);
        const percent_complete = (100 * progress.bytesUploaded) / progress.bytesTotal;
        $(`${config.upload_banner_identifier(file.id)} .moving_bar`).css({
            width: `${percent_complete}%`,
        });
    });

    $<HTMLInputElement>(config.file_input_identifier()).on("change", (event) => {
        const files = event.target.files;
        assert(files !== null);
        upload_files(uppy, config, files);
        config.textarea().trigger("focus");
        event.target.value = "";
    });

    const $banner_container = config.banner_container();
    $banner_container.on(
        "click",
        ".upload_banner.file_generic_error .main-view-banner-close-button",
        (event) => {
            event.preventDefault();
            $(event.target).parents(".upload_banner").remove();
        },
    );

    const $drag_drop_container = config.drag_drop_container();
    $drag_drop_container.on("dragover", (event) => {
        event.preventDefault();
    });
    $drag_drop_container.on("dragenter", (event) => {
        event.preventDefault();
    });

    $drag_drop_container.on("drop", (event) => {
        event.preventDefault();
        event.stopPropagation();
        assert(event.originalEvent !== undefined);
        assert(event.originalEvent.dataTransfer !== null);
        const files = event.originalEvent.dataTransfer.files;
        if (config.mode === "compose" && !compose_state.composing()) {
            compose_reply.respond_to_message({
                trigger: "file drop or paste",
                keep_composebox_empty: true,
            });
        }
        upload_files(uppy, config, files);
    });

    $drag_drop_container.on("paste", (event) => {
        assert(event.originalEvent instanceof ClipboardEvent);
        const clipboard_data = event.originalEvent.clipboardData;
        if (!clipboard_data) {
            return;
        }
        const items = clipboard_data.items;
        const files = [];
        for (const item of items) {
            const file = item.getAsFile();
            if (file === null) {
                continue;
            }
            files.push(file);
        }
        if (files.length === 0) {
            // Exit when there are no files from the clipboard
            return;
        }
        // Halt the normal browser paste event, which would otherwise
        // present a plain-text version of the file name.
        event.preventDefault();
        if (config.mode === "compose" && !compose_state.composing()) {
            compose_reply.respond_to_message({
                trigger: "file drop or paste",
                keep_composebox_empty: true,
            });
        }
        upload_files(uppy, config, files);
    });

    uppy.on("upload-success", (file, response) => {
        assert(file !== undefined);
        if (response.status !== 200) {
            blueslip.warn("Tus server returned an error, expected a 200 OK response code.", {
                response,
            });
            return;
        }

        // We do not receive response text if the file has already
        // been uploaded. For an existing upload, TUS js client sends
        // a HEAD request to the TUS server to check `Upload-Offset`
        // and if some part of the upload is left to be done -- and
        // when the upload offset is the same as the file length, it
        // will not send any further requests, meaning we will not
        // have a response body.  See the beforeUpload hook, above.
        if (response.body!.xhr.responseText === "") {
            if (!file.meta.zulip_url) {
                blueslip.warn("No zulip_url retrieved from previous upload", {file});
                return;
            }
        } else {
            try {
                const upload_response = zulip_upload_response_schema.parse(
                    JSON.parse(response.body!.xhr.responseText),
                );
                uppy.setFileState(file.id, {
                    name: upload_response.filename,
                });
                uppy.setFileMeta(file.id, {
                    zulip_url: upload_response.url,
                });
                file = uppy.getFile(file.id);
            } catch {
                blueslip.warn("Invalid JSON response from the tus server", {
                    body: response.body!.xhr.responseText,
                });
                return;
            }
        }

        const filtered_filename = file.name!.replaceAll("[", "").replaceAll("]", "");
        const syntax_to_insert = "[" + filtered_filename + "](" + file.meta.zulip_url + ")";
        const $text_area = config.textarea();
        const replacement_successful = compose_ui.replace_syntax(
            // We need to replace the original file name, and not the
            // possibly modified filename returned in the response by
            // the server. file.meta.name remains unchanged by us
            // unlike file.name
            get_translated_status(file.meta.name),
            syntax_to_insert,
            $text_area,
        );
        if (!replacement_successful) {
            compose_ui.insert_syntax_and_focus(syntax_to_insert, $text_area);
        }

        compose_ui.autosize_textarea($text_area);

        // Hide upload status after waiting 100ms after the 1s transition to 100%
        // so that the user can see the progress bar at 100%.
        hide_upload_banner(uppy, config, file.id, 1100);
    });

    uppy.on("info-visible", () => {
        // Uppy's `info-visible` event is issued after appending the
        // notice details into the list of event events accessed via
        // uppy.getState().info. Extract the notice details so that we
        // can potentially act on the error.
        //
        // TODO: Ideally, we'd be using the `.error()` hook or
        // something, not parsing error message strings.
        const infoList = uppy.getState().info;
        assert(infoList !== undefined);
        const info = infoList.at(-1);
        assert(info !== undefined);
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
            show_error_message(config, info.message);
        }
    });

    uppy.on("upload-error", (file, _error, response) => {
        assert(file !== undefined);
        // The files with failed upload should be removed since uppy doesn't allow files in the store
        // to be re-uploaded again.
        uppy.removeFile(file.id);

        let parsed;
        const message =
            response !== undefined &&
            (parsed = z.object({msg: z.string()}).safeParse(response.body)).success
                ? parsed.data.msg
                : undefined;
        // Hide the upload status banner on error so only the error banner shows
        hide_upload_banner(uppy, config, file.id);
        show_error_message(config, message, file.id);
        compose_ui.replace_syntax(get_translated_status(file.name!), "", config.textarea());
        compose_ui.autosize_textarea(config.textarea());
    });

    uppy.on("restriction-failed", (file) => {
        assert(file !== undefined);
        compose_ui.replace_syntax(get_translated_status(file.name!), "", config.textarea());
        compose_ui.autosize_textarea(config.textarea());
    });

    uppy.on("cancel-all", () => {
        if (config.mode === "compose") {
            compose_validate.set_upload_in_progress(false);
        }
    });

    return uppy;
}

export function deactivate_upload(config: Config): void {
    // Remove event listeners added for handling uploads.
    $(config.file_input_identifier()).off("change");
    config.banner_container().off("click");
    config.drag_drop_container().off("dragover dragenter drop paste");

    let uppy;

    if (config.mode === "edit") {
        uppy = upload_objects_by_message_edit_row.get(config.row);
    } else if (config.mode === "compose") {
        uppy = compose_upload_object;
    }

    if (!uppy) {
        return;
    }

    try {
        // Uninstall all plugins and close down the Uppy instance.
        // Also runs uppy.cancelAll() before uninstalling - which
        // cancels all uploads, resets progress and removes all files.
        uppy.destroy();
    } catch (error) {
        blueslip.error("Failed to close upload object.", {config}, error);
    }

    if (config.mode === "edit") {
        // Since we removed all the uploads from the row, we should
        // now remove the corresponding upload object from the store.
        upload_objects_by_message_edit_row.delete(config.row);
    }
}

export function initialize(): void {
    compose_upload_object = setup_upload(compose_config);

    $(".app, #navbar-fixed-container").on("dragstart", (event) => {
        if (event.target.nodeName === "IMG") {
            drag_drop_img = event.target;
        } else {
            drag_drop_img = null;
        }
    });

    // Allow the app panel to receive drag/drop events.
    $(".app, #navbar-fixed-container").on("dragover", (event) => {
        event.preventDefault();
    });

    // TODO: Do something visual to hint that drag/drop will work.
    $(".app, #navbar-fixed-container").on("dragenter", (event) => {
        event.preventDefault();
    });

    $(".app, #navbar-fixed-container").on("drop", (event) => {
        event.preventDefault();

        if (event.target.nodeName === "IMG" && event.target === drag_drop_img) {
            drag_drop_img = null;
            return;
        }

        const $drag_drop_edit_containers = $(".message_edit_form form");
        assert(event.originalEvent !== undefined);
        assert(event.originalEvent.dataTransfer !== null);
        const files = event.originalEvent.dataTransfer.files;
        const $last_drag_drop_edit_container = $drag_drop_edit_containers.last();

        // Handlers registered on individual inputs will ensure that
        // drag/dropping directly onto a compose/edit input will put
        // the upload there. Here, we handle drag/drop events that
        // land somewhere else in the center pane.

        if (compose_state.composing()) {
            // Compose box is open; drop there.
            upload_files(compose_upload_object, compose_config, files);
        } else if ($last_drag_drop_edit_container[0] !== undefined) {
            // A message edit box is open; drop there.
            const row_id = rows.get_message_id($last_drag_drop_edit_container[0]);
            const $drag_drop_container = edit_config(row_id).drag_drop_container();
            if ($drag_drop_container.closest("html").length === 0) {
                return;
            }
            const edit_upload_object = upload_objects_by_message_edit_row.get(row_id);
            assert(edit_upload_object !== undefined);

            upload_files(edit_upload_object, edit_config(row_id), files);
        } else if (message_lists.current?.selected_message()) {
            // Start a reply to selected message, if viewing a message feed.
            compose_reply.respond_to_message({
                trigger: "drag_drop_file",
                keep_composebox_empty: true,
            });
            upload_files(compose_upload_object, compose_config, files);
        } else {
            // Start a new message in other views.
            compose_actions.start({
                message_type: "stream",
                trigger: "drag_drop_file",
                keep_composebox_empty: true,
            });
            upload_files(compose_upload_object, compose_config, files);
        }
    });
}
