import $ from "jquery";

import render_code_block_lightbox_overlay from "../templates/code_block_lightbox_overlay.hbs";

import {$t} from "./i18n.ts";
import * as overlays from "./overlays.ts";

let is_open = false;
let active_code = "";
let edit_mode = false;
let source_code_element: HTMLElement | undefined;

function get_current_code(): string {
    if (edit_mode) {
        return $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? "";
    }
    return active_code;
}

function has_unsaved_edits(): boolean {
    if (!edit_mode) {
        return false;
    }
    const editor_code =
        $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? "";
    return editor_code !== active_code;
}

function set_edit_mode(enabled: boolean): void {
    edit_mode = enabled;
    const $overlay = $("#code_block_lightbox_overlay");
    $overlay.toggleClass("code-block-lightbox-edit-mode", edit_mode);
    $overlay.find(".edit-code-in-lightbox").toggleClass("active", edit_mode);
    $overlay
        .find(".edit-code-in-lightbox")
        .attr("aria-label", edit_mode ? $t({defaultMessage: "Done editing"}) : $t({defaultMessage: "Edit code"}));
    if (edit_mode) {
        const $editor = $overlay.find(".code-block-lightbox-editor");
        $editor.val(active_code);
        $editor.trigger("focus");
    }
}

function close_lightbox(save_changes: boolean): void {
    if (save_changes && edit_mode) {
        active_code =
            $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? "";
        $("#code_block_lightbox_overlay code").text(active_code);
        if (source_code_element !== undefined) {
            $(source_code_element).text(active_code);
        }
    }
    $("#code_block_lightbox_overlay").removeClass("show-close-prompt");
    set_edit_mode(false);
    overlays.close_overlay("code-block-lightbox");
}

function maybe_confirm_close(): void {
    if (!has_unsaved_edits()) {
        close_lightbox(false);
        return;
    }
    $("#code_block_lightbox_overlay").addClass("show-close-prompt");
}

function clear_overlay(): void {
    $("#code_block_lightbox_overlay .code-block-lightbox-title").text("");
    $("#code_block_lightbox_overlay code").text("");
    $("#code_block_lightbox_overlay .code-block-lightbox-editor").val("");
    $("#code_block_lightbox_overlay").removeClass("show-close-prompt");
    active_code = "";
    source_code_element = undefined;
    set_edit_mode(false);
}

function open_code_block_lightbox(
    language: string | undefined,
    code: string,
    code_element: HTMLElement | undefined,
): void {
    const title = language
        ? $t({defaultMessage: "Code Block ({language})"}, {language})
        : $t({defaultMessage: "Code Block"});
    $("#code_block_lightbox_overlay .code-block-lightbox-title").text(title);
    $("#code_block_lightbox_overlay code").text(code);
    $("#code_block_lightbox_overlay .code-block-lightbox-editor").val(code);
    active_code = code;
    source_code_element = code_element;
    set_edit_mode(false);

    if (is_open) {
        return;
    }

    if (overlays.any_active()) {
        overlays.close_active();
    }

    overlays.open_overlay({
        name: "code-block-lightbox",
        $overlay: $("#code_block_lightbox_overlay"),
        on_close() {
            clear_overlay();
            is_open = false;
        },
    });
    is_open = true;
}

function open_code_in_new_tab(): void {
    const code = get_current_code();
    if (code === "") {
        return;
    }

    const popup = window.open("about:blank", "_blank");
    if (popup === null) {
        return;
    }

    popup.document.open();
    popup.document.write("<!DOCTYPE html><html><head><meta charset='utf-8'><title>Zulip code block</title></head><body></body></html>");
    popup.document.close();

    const pre = popup.document.createElement("pre");
    pre.textContent = code;
    pre.style.whiteSpace = "pre";
    pre.style.overflowX = "auto";
    pre.style.margin = "0";
    pre.style.padding = "16px";
    pre.style.fontFamily =
        'ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';
    popup.document.body.append(pre);

    // Prevent the new tab from retaining a live opener handle.
    popup.opener = null;
}

async function copy_code_in_lightbox(): Promise<void> {
    const code = get_current_code();
    if (code === "") {
        return;
    }

    try {
        await navigator.clipboard.writeText(code);
        return;
    } catch {
        // Fallback for browsers/contexts where clipboard API is unavailable.
    }

    const textarea = document.createElement("textarea");
    textarea.value = code;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
}

export function initialize(): void {
    $("body").append($(render_code_block_lightbox_overlay()));

    $("#main_div, #preview_content, #message-history").on(
        "click",
        ".expand_codeblock, .view_code_block_lightbox",
        function (e) {
            e.preventDefault();
            e.stopPropagation();
            const $codehilite_div = $(this).closest(".codehilite");
            const language = $codehilite_div.attr("data-code-language");
            const $code_element = $codehilite_div.find("code").first();
            const code = $code_element.text();
            open_code_block_lightbox(language, code, $code_element.get(0));
        },
    );

    $("#code_block_lightbox_overlay").on("click", ".open-code-in-new-tab", (e) => {
        e.preventDefault();
        open_code_in_new_tab();
    });

    $("#code_block_lightbox_overlay").on("click", ".copy-code-in-new-tab", (e) => {
        e.preventDefault();
        void copy_code_in_lightbox();
    });

    $("#code_block_lightbox_overlay").on("click", ".edit-code-in-lightbox", (e) => {
        e.preventDefault();
        if (edit_mode) {
            active_code =
                $("#code_block_lightbox_overlay .code-block-lightbox-editor").val()?.toString() ?? "";
            $("#code_block_lightbox_overlay code").text(active_code);
        }
        set_edit_mode(!edit_mode);
    });

    $("#code_block_lightbox_overlay").on("click", ".exit", (e) => {
        e.preventDefault();
        e.stopPropagation();
        maybe_confirm_close();
    });

    $("#code_block_lightbox_overlay").on("click", ".prompt-save", (e) => {
        e.preventDefault();
        close_lightbox(true);
    });

    $("#code_block_lightbox_overlay").on("click", ".prompt-discard", (e) => {
        e.preventDefault();
        close_lightbox(false);
    });

    $("#code_block_lightbox_overlay").on("click", ".prompt-cancel", (e) => {
        e.preventDefault();
        $("#code_block_lightbox_overlay").removeClass("show-close-prompt");
    });

    $("#code_block_lightbox_overlay").on("click", (e) => {
        if ($(e.target).is("#code_block_lightbox_overlay")) {
            e.preventDefault();
            e.stopPropagation();
            maybe_confirm_close();
        }
    });
}
